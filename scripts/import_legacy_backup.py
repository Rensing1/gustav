#!/usr/bin/env python3
"""
Legacy backup importer for GUSTAV Alpha2.

This script restores the legacy Supabase dump into a dedicated schema and
executes the ETL pipeline described in docs/migration/legacy-import.md.
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse
import json
import uuid

try:  # Optional dependency guard
    import psycopg
    from psycopg import sql
except Exception:  # pragma: no cover - handled at runtime
    psycopg = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]

LOG = logging.getLogger("legacy_import")


@dataclass
class DumpInfo:
    path: Path
    format: str  # "custom" or "plain"
    size_bytes: int


@dataclass
class PhaseResult:
    name: str
    status: str
    inserted: int = 0
    skipped: int = 0
    warnings: list[str] | None = None
    errors: list[str] | None = None
    details: Dict[str, Any] | None = None


@dataclass
class KeycloakConfig:
    base_url: str
    host_header: str
    realm: str
    admin_user: str
    admin_pass: str
    timeout: float = 10.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy Supabase backup into Alpha2 schema")
    parser.add_argument("--dump", required=True, help="Path to legacy dump (.tar.gz/.tar/.sql)")
    parser.add_argument("--dsn", help="Postgres connection string; falls back to SERVICE_ROLE_DSN env")
    parser.add_argument("--legacy-schema", default="legacy_raw", help="Target schema for legacy objects")
    parser.add_argument(
        "--workdir",
        default=".tmp/migration_run",
        help="Temporary work directory for unpacked dumps and logs",
    )
    parser.add_argument("--report", help="Path to JSON report (default docs/migration/reports/...) ")
    parser.add_argument("--storage-root", default="/tmp/legacy_storage", help="Path to legacy storage blobs")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing transformed data")
    parser.add_argument("--keep-temp", action="store_true", help="Keep extracted dump files")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--kc-base-url", help="Keycloak admin base URL (optional)")
    parser.add_argument("--kc-host-header", help="Host header for Keycloak requests")
    parser.add_argument("--kc-realm", default="gustav", help="Keycloak realm name")
    parser.add_argument("--kc-admin-user", help="Keycloak admin username")
    parser.add_argument("--kc-admin-pass", help="Keycloak admin password")
    parser.add_argument("--kc-timeout", type=float, default=10.0, help="Keycloak admin API timeout (seconds)")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def resolve_dsn(args: argparse.Namespace) -> str:
    if args.dsn:
        return args.dsn
    env_dsn = os.environ.get("SERVICE_ROLE_DSN")
    if env_dsn:
        return env_dsn
    raise RuntimeError("SERVICE_ROLE_DSN not set and --dsn missing; run `supabase status` and export the DSN")


def prepare_workdir(path_str: str, keep_temp: bool) -> Path:
    workdir = Path(path_str).resolve()
    if workdir.exists() and not keep_temp:
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def extract_dump(dump_path: Path, workdir: Path) -> DumpInfo:
    if not dump_path.exists():
        raise FileNotFoundError(f"Dump file {dump_path} not found")

    if dump_path.suffix == ".sql":
        size = dump_path.stat().st_size
        return DumpInfo(path=dump_path, format="plain", size_bytes=size)

    if dump_path.suffixes[-2:] == [".tar", ".gz"]:
        target_dir = workdir / dump_path.stem
        target_dir.mkdir(exist_ok=True)
        with tarfile.open(dump_path, "r:gz") as tar:
            tar.extractall(target_dir, filter="data")
        inner_dump = next(target_dir.glob("**/db_all.dump"), None)
        if inner_dump is None:
            raise RuntimeError("db_all.dump not found inside archive")
        size = inner_dump.stat().st_size
        return DumpInfo(path=inner_dump, format="custom", size_bytes=size)

    if dump_path.suffix == ".tar":
        target_dir = workdir / dump_path.stem
        target_dir.mkdir(exist_ok=True)
        with tarfile.open(dump_path, "r:") as tar:
            tar.extractall(target_dir, filter="data")
        inner_dump = next(target_dir.glob("**/db_all.dump"), None)
        if inner_dump is None:
            raise RuntimeError("db_all.dump not found inside archive")
        size = inner_dump.stat().st_size
        return DumpInfo(path=inner_dump, format="custom", size_bytes=size)

    raise ValueError(f"Unsupported dump format: {dump_path}")


def ensure_psycopg() -> None:
    if psycopg is None:  # pragma: no cover - defensive guard
        raise RuntimeError("psycopg (v3) is required. Install dependencies via `pip install -r requirements.txt`.")


def run_command_capture(cmd: list[str]) -> str:
    LOG.debug("Executing command (capture): %s", " ".join(cmd))
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        LOG.debug("stdout:\n%s", result.stdout)
        LOG.debug("stderr:\n%s", result.stderr)
        raise RuntimeError(f"Command {' '.join(cmd)} failed with exit code {result.returncode}")
    return result.stdout


def run_command_input(cmd: list[str], data: str) -> None:
    LOG.debug("Executing command (input stream): %s", " ".join(cmd))
    result = subprocess.run(cmd, text=True, input=data, capture_output=True)
    if result.returncode != 0:
        LOG.debug("stdout:\n%s", result.stdout)
        LOG.debug("stderr:\n%s", result.stderr)
        raise RuntimeError(f"Command {' '.join(cmd)} failed with exit code {result.returncode}")


def rewrite_schema_sql(sql_text: str, legacy_schema: str) -> str:
    replacements = {
        "SET search_path = public": f"SET search_path = {legacy_schema}",
        "SET search_path = public, pg_temp": f"SET search_path = {legacy_schema}, pg_temp",
        "public.": f"{legacy_schema}.",
        "ALTER SCHEMA public": f"ALTER SCHEMA {legacy_schema}",
    }
    for old, new in replacements.items():
        sql_text = sql_text.replace(old, new)
    return sql_text


def rewrite_data_sql(sql_text: str, legacy_schema: str) -> str:
    replacements = {
        "COPY public.": f"COPY {legacy_schema}.",
        "'public.": f"'{legacy_schema}.",
        '"public".': f'"{legacy_schema}".',
    }
    for old, new in replacements.items():
        sql_text = sql_text.replace(old, new)
    return sql_text


def phase_to_dict(result: PhaseResult) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "name": result.name,
        "status": result.status,
        "inserted": result.inserted,
        "skipped": result.skipped,
    }
    if result.details:
        data["details"] = result.details
    if result.warnings:
        data["warnings"] = result.warnings
    if result.errors:
        data["errors"] = result.errors
    return data


def ensure_app_login_role(dry_run: bool) -> PhaseResult:
    """Ensure the app login role (e.g. gustav_app) exists and inherits gustav_limited."""
    ensure_psycopg()

    app_user = (os.getenv("APP_DB_USER") or "gustav_app").strip()
    app_password = os.getenv("APP_DB_PASSWORD") or "CHANGE_ME_DEV"
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "54322")
    database_name = os.getenv("APP_DB_NAME", "postgres")
    db_superuser = os.getenv("DB_SUPERUSER", "postgres")
    db_superpassword = os.getenv("DB_SUPERPASSWORD", "postgres")
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "create_login_user.sql"

    if not app_user:
        return PhaseResult(
            name="app_login_role",
            status="failed",
            errors=["APP_DB_USER environment variable is empty; cannot provision login role."],
        )

    app_dsn = os.getenv("DATABASE_URL")
    if not app_dsn:
        app_dsn = f"postgresql://{app_user}:{app_password}@{db_host}:{db_port}/{database_name}"

    def _login_ready() -> tuple[bool, Optional[str]]:
        try:
            with psycopg.connect(app_dsn) as conn:  # type: ignore[call-arg]
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute("select pg_has_role(current_user, 'gustav_limited', 'member')")
                    row = cur.fetchone()
                    return bool(row and row[0]), None
        except Exception as exc:  # pragma: no cover - diagnostic path
            return False, str(exc)

    ready, reason = _login_ready()
    if ready:
        return PhaseResult(
            name="app_login_role",
            status="success",
            details={"app_user": app_user, "action": "already_present"},
            skipped=1,
        )

    if dry_run:
        warnings = ["Dry-run mode: skipped provisioning of app DB login role."]
        details = {"app_user": app_user, "action": "skipped", "reason": "dry_run"}
        if reason:
            details["check_error"] = reason
        return PhaseResult(
            name="app_login_role",
            status="partial",
            warnings=warnings,
            details=details,
            skipped=1,
        )

    if not script_path.exists():
        errors = [
            f"Provisioning script not found at {script_path}. Run `make db-login-user` manually."
        ]
        return PhaseResult(
            name="app_login_role",
            status="failed",
            errors=errors,
            details={"app_user": app_user, "action": "script_missing"},
        )

    env = os.environ.copy()
    # Provide secrets via environment rather than command-line arguments to
    # avoid leaking in process listings.
    env["PGPASSWORD"] = db_superpassword
    env["APP_DB_USER"] = app_user
    env["APP_DB_PASSWORD"] = app_password
    cmd = [
        "psql",
        "-h",
        db_host,
        "-p",
        str(db_port),
        "-U",
        db_superuser,
        "-d",
        database_name,
        "-v",
        "ON_ERROR_STOP=1",
        "-v",
        f"app_user={app_user}",
        "-v",
        f"app_pass={app_password}",
        "-f",
        str(script_path),
    ]

    result = subprocess.run(cmd, text=True, capture_output=True, env=env)
    if result.returncode != 0:
        errors = [
            "Failed to provision app DB login via psql.",
            f"stdout: {result.stdout.strip()}",
            f"stderr: {result.stderr.strip()}",
        ]
        return PhaseResult(
            name="app_login_role",
            status="failed",
            errors=errors,
            details={"app_user": app_user, "action": "psql_failed"},
        )

    ready, reason = _login_ready()
    if ready:
        return PhaseResult(
            name="app_login_role",
            status="success",
            inserted=1,
            details={"app_user": app_user, "action": "provisioned"},
        )

    errors = ["Provisioning completed but login role still unavailable."]
    if reason:
        errors.append(f"check_error: {reason}")
    return PhaseResult(
        name="app_login_role",
        status="failed",
        errors=errors,
        details={"app_user": app_user, "action": "post_check_failed"},
    )


def _load_schema_columns(conn: "psycopg.Connection", legacy_schema: str) -> Dict[str, set[str]]:
    columns: Dict[str, set[str]] = {}
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            """
            select table_name, column_name
            from information_schema.columns
            where table_schema = %s
            """,
            (legacy_schema,),
        )
        for table_name, column_name in cur.fetchall():
            columns.setdefault(table_name, set()).add(column_name)
    return columns


def _ensure_legacy_user_map(conn: "psycopg.Connection") -> None:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            """
            create table if not exists public.legacy_user_map (
              legacy_id uuid primary key,
              sub text unique
            );
            """
        )


def _load_existing_user_map(conn: "psycopg.Connection") -> Dict[str, str]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute("select legacy_id::text, sub from public.legacy_user_map")
        rows = cur.fetchall()
    return {legacy_id: sub for legacy_id, sub in rows}


def build_identity_map(dsn: str, legacy_schema: str, dry_run: bool, kc_config: KeycloakConfig | None) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        _ensure_legacy_user_map(conn)
        existing_map = _load_existing_user_map(conn)
        existing_subs = set(existing_map.values())
        columns = _load_schema_columns(conn, legacy_schema)

        profiles_table = sql.Identifier(legacy_schema, "profiles")
        profile_emails: Dict[str, str] = {}
        user_ids: set[str] = set()

        if "profiles" in columns and "id" in columns["profiles"]:
            with conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute(
                    sql.SQL("select id::text, email from {}").format(profiles_table)
                )
                for legacy_id, email in cur.fetchall():
                    if legacy_id:
                        user_ids.add(legacy_id)
                        if email:
                            profile_emails[legacy_id] = email.strip()

        scan_columns = [
            ("course", "creator_id"),
            ("course", "created_by"),
            ("course_student", "student_id"),
            ("course_teacher", "teacher_id"),
            ("learning_unit", "creator_id"),
            ("submission", "student_id"),
            ("feedback", "teacher_id"),
        ]

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for table_name, column_name in scan_columns:
                if table_name not in columns or column_name not in columns[table_name]:
                    continue
                query = sql.SQL("select {}::text from {} where {} is not null").format(
                    sql.Identifier(column_name),
                    sql.Identifier(legacy_schema, table_name),
                    sql.Identifier(column_name),
                )
                cur.execute(query)
                for (legacy_id,) in cur.fetchall():
                    if legacy_id:
                        user_ids.add(legacy_id)

        inserted = 0
        already_present = 0
        updated = 0
        warnings: list[str] = []
        missing_profiles: list[str] = []
        keycloak_failures = 0
        kc_client = None
        kc_cache: Dict[str, Optional[str]] = {}

        if kc_config:
            try:
                import sys
                root_dir = Path(__file__).resolve().parents[1]
                if str(root_dir) not in sys.path:
                    sys.path.append(str(root_dir))
                from backend.tools.legacy_user_import import KeycloakAdminClient  # type: ignore

                kc_client = KeycloakAdminClient.from_credentials(
                    base_url=kc_config.base_url,
                    host_header=kc_config.host_header,
                    realm=kc_config.realm,
                    username=kc_config.admin_user,
                    password=kc_config.admin_pass,
                    timeout=kc_config.timeout,
                )
            except Exception as exc:  # pragma: no cover - integration guard
                warnings.append(f"Keycloak lookup disabled ({exc})")
                kc_client = None

        def lookup_keycloak(email: str) -> Optional[str]:
            if not kc_client:
                return None
            key = email.lower()
            if key in kc_cache:
                return kc_cache[key]
            try:
                sub = kc_client.find_user_id(email)
                kc_cache[key] = sub
                return sub
            except Exception as exc:  # pragma: no cover
                nonlocal keycloak_failures
                keycloak_failures += 1
                kc_cache[key] = None
                LOG.warning("Keycloak lookup failed for %s: %s", email, exc)
                return None

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for legacy_id in sorted(user_ids):
                if legacy_id in existing_map:
                    current_sub = existing_map[legacy_id]
                else:
                    current_sub = None

                email = profile_emails.get(legacy_id, "")
                sub_candidate: Optional[str] = None
                if email:
                    sub_candidate = lookup_keycloak(email)
                    if sub_candidate:
                        sub_candidate = sub_candidate.strip()
                if not sub_candidate:
                    sanitized_email = email.strip().lower()
                    if sanitized_email:
                        candidate = f"legacy-email:{sanitized_email}"
                        if candidate in existing_subs:
                            warnings.append(
                                f"Duplicate email-based sub detected for {legacy_id}, falling back to UUID placeholder."
                            )
                            sub_candidate = f"legacy:{legacy_id}"
                        else:
                            sub_candidate = candidate
                    else:
                        sub_candidate = f"legacy:{legacy_id}"
                        missing_profiles.append(legacy_id)

                if current_sub == sub_candidate:
                    already_present += 1
                    continue

                if dry_run:
                    already_present += 1
                    continue

                if current_sub is None:
                    cur.execute(
                        """
                        insert into public.legacy_user_map (legacy_id, sub)
                        values (%s::uuid, %s)
                        on conflict (legacy_id) do nothing
                        """,
                        (legacy_id, sub_candidate),
                    )
                    if cur.rowcount:
                        inserted += 1
                    else:
                        already_present += 1
                else:
                    cur.execute(
                        "update public.legacy_user_map set sub = %s where legacy_id = %s::uuid",
                        (sub_candidate, legacy_id),
                    )
                    updated += 1

                existing_map[legacy_id] = sub_candidate
                existing_subs.add(sub_candidate)

        details = {
            "total_legacy_users": len(user_ids),
            "inserted": inserted,
            "already_present": already_present,
            "updated": updated,
            "dry_run": dry_run,
        }
        if missing_profiles:
            details["missing_profile_entries"] = missing_profiles[:10]
        if keycloak_failures:
            details["keycloak_lookup_failures"] = keycloak_failures

        status = "success"
        warnings_list = warnings if warnings else []
        if missing_profiles:
            status = "partial"
            warnings_list.append(
                f"{len(missing_profiles)} user id(s) without profile/email information; placeholder sub values generated."
            )
        if keycloak_failures:
            status = "partial"
            warnings_list.append(f"{keycloak_failures} Keycloak lookup(s) failed; placeholders retained.")
        return PhaseResult(
            name="identity",
            status=status,
            inserted=inserted,
            skipped=already_present,
            warnings=warnings_list if warnings_list else None,
            details=details,
        )


def transfer_courses(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        identity_map = _load_existing_user_map(conn)
        missing_teachers: list[str] = []
        inserted = 0
        updated = 0
        skipped = 0

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select id::text, name, creator_id::text, created_at, updated_at
                    from {}
                    """
                ).format(sql.Identifier(legacy_schema, "course"))
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for legacy_id, name, creator_id, created_at, updated_at in rows:
                if creator_id is None:
                    missing_teachers.append(f"{legacy_id} (no creator)")
                    skipped += 1
                    continue

                teacher_sub = identity_map.get(creator_id)
                if not teacher_sub:
                    missing_teachers.append(f"{legacy_id} (missing mapping for {creator_id})")
                    skipped += 1
                    continue

                if dry_run:
                    skipped += 1
                    continue

                cur.execute(
                    """
                    insert into public.courses (id, title, subject, grade_level, term, teacher_id, created_at, updated_at)
                    values (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do update set
                      title = excluded.title,
                      teacher_id = excluded.teacher_id,
                      updated_at = excluded.updated_at
                    """,
                    (
                        legacy_id,
                        name,
                        None,
                        None,
                        None,
                        teacher_sub,
                        created_at,
                        updated_at,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

        details = {
            "legacy_courses": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_teachers:
            details["missing_teacher_mappings"] = missing_teachers[:10]

        status = "success" if not missing_teachers else "partial"
        warnings = None
        if missing_teachers:
            warnings = [
                f"{len(missing_teachers)} course(s) missing teacher mapping; see details.missing_teacher_mappings."
            ]

        return PhaseResult(
            name="courses",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings,
            details=details,
        )


def transfer_course_memberships(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        identity_map = _load_existing_user_map(conn)
        missing_students: list[str] = []
        missing_courses: list[str] = []
        inserted = 0
        skipped = 0

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select course_id::text, student_id::text, enrolled_at
                    from {}
                    """
                ).format(sql.Identifier(legacy_schema, "course_student"))
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for course_id, student_id, enrolled_at in rows:
                student_sub = identity_map.get(student_id)
                if not student_sub:
                    missing_students.append(f"{course_id}:{student_id}")
                    skipped += 1
                    continue

                if dry_run:
                    skipped += 1
                    continue

                cur.execute(
                    """
                    insert into public.course_memberships (course_id, student_id, created_at)
                    values (%s::uuid, %s, coalesce(%s, now()))
                    on conflict (course_id, student_id) do nothing
                    """,
                    (course_id, student_sub, enrolled_at),
                )
                if cur.rowcount:
                    inserted += 1

        details = {
            "legacy_memberships": len(rows),
            "inserted": inserted,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_students:
            details["missing_student_mappings"] = missing_students[:10]

        status = "success" if not missing_students else "partial"
        warnings = None
        if missing_students:
            warnings = [
                f"{len(missing_students)} membership(s) skipped due to missing student mapping; see details.missing_student_mappings."
            ]

        return PhaseResult(
            name="course_memberships",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings,
            details=details,
        )


def transfer_units(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        identity_map = _load_existing_user_map(conn)
        missing_authors: list[str] = []
        inserted = 0
        updated = 0
        skipped = 0

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select id::text, title, creator_id::text, created_at, updated_at
                    from {}
                    """
                ).format(sql.Identifier(legacy_schema, "learning_unit"))
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for unit_id, title, creator_id, created_at, updated_at in rows:
                if creator_id is None:
                    missing_authors.append(f"{unit_id} (no creator)")
                    skipped += 1
                    continue
                author_sub = identity_map.get(creator_id)
                if not author_sub:
                    missing_authors.append(f"{unit_id} (missing mapping for {creator_id})")
                    skipped += 1
                    continue

                if dry_run:
                    skipped += 1
                    continue

                cur.execute(
                    """
                    insert into public.units (id, title, summary, author_id, created_at, updated_at)
                    values (%s::uuid, %s, %s, %s, %s, %s)
                    on conflict (id) do update set
                      title = excluded.title,
                      author_id = excluded.author_id,
                      updated_at = excluded.updated_at
                    """,
                    (
                        unit_id,
                        title,
                        None,
                        author_sub,
                        created_at,
                        updated_at,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

        details = {
            "legacy_units": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_authors:
            details["missing_author_mappings"] = missing_authors[:10]

        status = "success" if not missing_authors else "partial"
        warnings = None
        if missing_authors:
            warnings = [
                f"{len(missing_authors)} unit(s) skipped due to missing author mapping; see details.missing_author_mappings."
            ]

        return PhaseResult(
            name="units",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings,
            details=details,
        )


def transfer_course_modules(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        missing_courses: list[str] = []
        missing_units: list[str] = []
        inserted = 0
        updated = 0
        skipped = 0

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select course_id::text, unit_id::text, assigned_at
                    from {}
                    order by course_id, coalesce(assigned_at, '1970-01-01'::timestamptz), unit_id
                    """
                ).format(sql.Identifier(legacy_schema, "course_learning_unit_assignment"))
            )
            rows = cur.fetchall()

        positions: Dict[str, int] = {}

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for course_id, unit_id, assigned_at in rows:
                if dry_run:
                    skipped += 1
                    continue

                cur.execute("select 1 from public.courses where id = %s::uuid", (course_id,))
                if cur.fetchone() is None:
                    missing_courses.append(course_id)
                    skipped += 1
                    continue

                cur.execute("select 1 from public.units where id = %s::uuid", (unit_id,))
                if cur.fetchone() is None:
                    missing_units.append(unit_id)
                    skipped += 1
                    continue

                positions.setdefault(course_id, 0)
                positions[course_id] += 1
                position = positions[course_id]

                cur.execute(
                    """
                    insert into public.course_modules (course_id, unit_id, position, context_notes, created_at, updated_at)
                    values (%s::uuid, %s::uuid, %s, %s, coalesce(%s, now()), coalesce(%s, now()))
                    on conflict (course_id, unit_id) do update set
                      position = excluded.position,
                      updated_at = excluded.updated_at
                    """,
                    (
                        course_id,
                        unit_id,
                        position,
                        None,
                        assigned_at,
                        assigned_at,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

        details = {
            "legacy_assignments": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_courses:
            details["missing_courses"] = missing_courses[:10]
        if missing_units:
            details["missing_units"] = missing_units[:10]

        status = "success"
        warnings: list[str] = []
        if missing_courses:
            status = "partial"
            warnings.append(f"{len(missing_courses)} assignment(s) skipped due to missing course.")
        if missing_units:
            status = "partial"
            warnings.append(f"{len(missing_units)} assignment(s) skipped due to missing unit.")

        return PhaseResult(
            name="course_modules",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings if warnings else None,
            details=details,
        )


def transfer_unit_sections(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        missing_units: list[str] = []
        inserted = 0
        updated = 0
        skipped = 0

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select id::text, unit_id::text, coalesce(title, ''), coalesce(order_in_unit, 0), created_at, updated_at
                    from {}
                    """
                ).format(sql.Identifier(legacy_schema, "unit_section"))
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for section_id, unit_id, title, order_in_unit, created_at, updated_at in rows:
                cur.execute("select 1 from public.units where id = %s::uuid", (unit_id,))
                if cur.fetchone() is None:
                    missing_units.append(f"{section_id} (unit {unit_id})")
                    skipped += 1
                    continue

                position = int(order_in_unit) + 1
                normalized_title = title.strip() if title else ""
                if not normalized_title:
                    normalized_title = f"Section {section_id[:8]}"

                if dry_run:
                    skipped += 1
                    continue

                cur.execute(
                    """
                    insert into public.unit_sections (id, unit_id, title, position, created_at, updated_at)
                    values (%s::uuid, %s::uuid, %s, %s, coalesce(%s, now()), coalesce(%s, now()))
                    on conflict (id) do update set
                      title = excluded.title,
                      position = excluded.position,
                      updated_at = excluded.updated_at
                    """,
                    (
                        section_id,
                        unit_id,
                        normalized_title,
                        position,
                        created_at,
                        updated_at,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

        details = {
            "legacy_sections": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_units:
            details["missing_unit_mappings"] = missing_units[:10]

        status = "success" if not missing_units else "partial"
        warnings = None
        if missing_units:
            warnings = [
                f"{len(missing_units)} section(s) skipped due to missing unit; see details.missing_unit_mappings."
            ]

        return PhaseResult(
            name="unit_sections",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings,
            details=details,
        )


def transfer_materials(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        inserted = 0
        updated = 0
        skipped = 0
        sections_without_materials = 0

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select s.id::text,
                           us.unit_id::text,
                           coalesce(s.materials::text, '[]'),
                           s.created_at,
                           s.updated_at
                    from {} s
                    join public.unit_sections us on us.id = s.id::uuid
                    """
                ).format(sql.Identifier(legacy_schema, "unit_section"))
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for section_id, unit_id, materials_text, section_created, section_updated in rows:
                try:
                    materials = json.loads(materials_text) if materials_text else []
                except json.JSONDecodeError:
                    materials = []
                if not isinstance(materials, list) or not materials:
                    sections_without_materials += 1
                    continue

                position = 0
                for entry in materials:
                    if not isinstance(entry, dict):
                        continue
                    position += 1
                    raw_id = entry.get("id")
                    material_uuid: uuid.UUID
                    try:
                        material_uuid = uuid.UUID(str(raw_id))
                    except Exception:
                        material_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"{section_id}:{position}")

                    title = (entry.get("title") or "").strip() or f"Material {position}"
                    body = entry.get("content") or entry.get("body") or ""
                    entry_type = (entry.get("type") or "").lower()
                    if entry_type != "markdown":
                        link = entry.get("url") or entry.get("href") or ""
                        if link:
                            body = f"{body}\n\n[Legacy resource]({link})".strip()
                        else:
                            body = body or "Legacy resource without URL."
                    if not body:
                        body = "Legacy content was empty."

                    if dry_run:
                        skipped += 1
                        continue

                    cur.execute(
                        """
                        insert into public.unit_materials (
                            id, unit_id, section_id, title, body_md, kind, position,
                            storage_key, filename_original, mime_type, size_bytes, sha256, alt_text,
                            created_at, updated_at
                        )
                        values (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'markdown', %s,
                                NULL, NULL, NULL, NULL, NULL, NULL,
                                coalesce(%s, now()), coalesce(%s, now()))
                        on conflict (id) do update set
                          title = excluded.title,
                          body_md = excluded.body_md,
                          position = excluded.position,
                          updated_at = excluded.updated_at
                        """,
                        (
                            str(material_uuid),
                            unit_id,
                            section_id,
                            title,
                            body,
                            position,
                            section_created,
                            section_updated,
                        ),
                    )
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        updated += 1

        details = {
            "sections_scanned": len(rows),
            "sections_without_materials": sections_without_materials,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }

        return PhaseResult(
            name="unit_materials",
            status="success",
            inserted=inserted,
            skipped=skipped,
            details=details,
        )


def transfer_unit_tasks(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        missing_sections: list[str] = []
        inserted = 0
        updated = 0
        skipped = 0

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select tb.id::text,
                           tb.section_id::text,
                           us.unit_id::text,
                           tb.instruction,
                           tb.assessment_criteria::text,
                           tb.solution_hints,
                           coalesce(rt.order_in_section, tb.order_in_section, 0),
                           rt.max_attempts,
                           tb.created_at,
                           tb.updated_at
                    from {} tb
                    left join {} rt on rt.task_id = tb.id
                    left join public.unit_sections us on us.id = tb.section_id::uuid
                    order by tb.section_id, coalesce(rt.order_in_section, tb.order_in_section, 0), tb.created_at, tb.id
                    """
                ).format(
                    sql.Identifier(legacy_schema, "task_base"),
                    sql.Identifier(legacy_schema, "regular_tasks"),
                )
            )
            rows = cur.fetchall()

        section_positions: Dict[str, int] = {}
        cleared_sections: set[str] = set()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for (
                task_id,
                section_id,
                unit_id,
                instruction,
                criteria_text,
                hints,
                order_in_section,
                max_attempts,
                created_at,
                updated_at,
            ) in rows:
                if unit_id is None or section_id is None:
                    missing_sections.append(task_id)
                    skipped += 1
                    continue

                try:
                    criteria_json = json.loads(criteria_text) if criteria_text else []
                except json.JSONDecodeError:
                    criteria_json = []
                if isinstance(criteria_json, list):
                    criteria_list = [str(item).strip() for item in criteria_json if str(item).strip()]
                elif isinstance(criteria_json, dict):
                    criteria_list = [f"{k}: {v}" for k, v in criteria_json.items()]
                elif isinstance(criteria_json, str):
                    criteria_list = [criteria_json.strip()]
                else:
                    criteria_list = []

                section_positions.setdefault(section_id, 0)
                section_positions[section_id] += 1
                position = section_positions[section_id]

                instruction_md = instruction or "Legacy task had no instruction."
                hints_md = hints or None

                if dry_run:
                    skipped += 1
                    continue

                if section_id not in cleared_sections:
                    cur.execute(
                        "delete from public.unit_tasks where section_id = %s::uuid",
                        (section_id,),
                    )
                    cleared_sections.add(section_id)

                cur.execute(
                    """
                    insert into public.unit_tasks (
                        id, unit_id, section_id, instruction_md, criteria, hints_md,
                        due_at, max_attempts, position, created_at, updated_at
                    )
                    values (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, NULL, %s, %s, coalesce(%s, now()), coalesce(%s, now()))
                    on conflict (id) do update set
                      instruction_md = excluded.instruction_md,
                      criteria = excluded.criteria,
                      hints_md = excluded.hints_md,
                      max_attempts = excluded.max_attempts,
                      position = excluded.position,
                      updated_at = excluded.updated_at
                    """,
                    (
                        task_id,
                        unit_id,
                        section_id,
                        instruction_md,
                        criteria_list,
                        hints_md,
                        max_attempts,
                        position,
                        created_at,
                        updated_at,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

        details = {
            "legacy_tasks": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_sections:
            details["missing_sections"] = missing_sections[:10]

        status = "success" if not missing_sections else "partial"
        warnings = None
        if missing_sections:
            warnings = [
                f"{len(missing_sections)} task(s) skipped due to missing section/unit."
            ]

        return PhaseResult(
            name="unit_tasks",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings,
            details=details,
        )


def transfer_submissions(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        identity_map = _load_existing_user_map(conn)

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("select id::text, unit_id::text, section_id::text from public.unit_tasks")
            task_map = {task_id: (unit_id, section_id) for task_id, unit_id, section_id in cur.fetchall()}

            cur.execute("select course_id::text, unit_id::text from public.course_modules")
            unit_to_courses: Dict[str, List[str]] = {}
            for course_id, unit_id in cur.fetchall():
                unit_to_courses.setdefault(unit_id, []).append(course_id)

            cur.execute("select course_id::text, student_id from public.course_memberships")
            membership_rows = cur.fetchall()
            membership_set = {(course_id, student_id) for course_id, student_id in membership_rows}
            student_courses_map: Dict[str, List[str]] = {}
            for course_id, student_id in membership_rows:
                student_courses_map.setdefault(student_id, []).append(course_id)

            cur.execute("select id::text, author_id from public.units")
            unit_author_map = {unit_id: author_id for unit_id, author_id in cur.fetchall()}

            cur.execute("select id::text, teacher_id from public.courses")
            course_teacher_map = {course_id: teacher_id for course_id, teacher_id in cur.fetchall()}

        inserted = 0
        updated = 0
        skipped = 0
        missing_students: list[str] = []
        missing_tasks: list[str] = []
        missing_courses: list[str] = []

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select id::text,
                           student_id::text,
                           task_id::text,
                           submitted_at,
                           submission_data::text,
                           attempt_number,
                           ai_feedback,
                           teacher_override_feedback,
                           feed_back_text,
                           feed_forward_text,
                           feedback_status,
                           feedback_generated_at,
                           ai_insights::text,
                           created_at,
                           updated_at
                    from {}
                    """
                ).format(sql.Identifier(legacy_schema, "submission"))
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for (
                submission_id,
                student_id,
                task_id,
                submitted_at,
                submission_data_text,
                attempt_number,
                ai_feedback,
                teacher_feedback,
                feed_back_text,
                feed_forward_text,
                feedback_status,
                feedback_generated_at,
                ai_insights_text,
                created_at,
                updated_at,
            ) in rows:
                student_sub = identity_map.get(student_id)
                if not student_sub:
                    missing_students.append(submission_id)
                    skipped += 1
                    continue

                task_meta = task_map.get(task_id)
                if not task_meta:
                    missing_tasks.append(submission_id)
                    skipped += 1
                    continue
                unit_id, section_id = task_meta
                course_candidates = unit_to_courses.get(unit_id, [])
                course_id = None
                for candidate in course_candidates:
                    if (candidate, student_sub) in membership_set:
                        course_id = candidate
                        break
                if course_id is None and course_candidates:
                    course_id = course_candidates[0]
                if course_id is None:
                    possible_courses = student_courses_map.get(student_sub, [])
                    if len(possible_courses) == 1:
                        course_id = possible_courses[0]
                    elif possible_courses:
                        author = unit_author_map.get(unit_id)
                        matching = [c for c in possible_courses if course_teacher_map.get(c) == author]
                        if len(matching) == 1:
                            course_id = matching[0]
                        elif matching:
                            course_id = matching[0]
                if course_id is None:
                    missing_courses.append(submission_id)
                    skipped += 1
                    continue

                try:
                    submission_data = json.loads(submission_data_text) if submission_data_text else {}
                except json.JSONDecodeError:
                    submission_data = {}

                submission_type = (submission_data.get("type") or "text").lower()
                text_body = submission_data.get("text") or submission_data.get("content") or submission_data.get("body") or ""
                kind = "text"
                if submission_type == "image":
                    link = submission_data.get("url") or submission_data.get("link")
                    if link:
                        text_body = f"{text_body}\n\n![Legacy submission image]({link})".strip()
                    else:
                        text_body = text_body or "Legacy image submission without accessible URL."
                elif submission_type != "text":
                    extra = submission_data.get("description") or submission_type
                    text_body = text_body or ""
                    text_body = f"{text_body}\n\nLegacy submission type: {extra}".strip()

                attempt_nr = attempt_number or 1
                status = (feedback_status or "pending").lower()
                if status in ("completed", "done"):
                    analysis_status = "completed"
                elif status in ("failed", "error"):
                    analysis_status = "failed"
                else:
                    analysis_status = "pending"

                feedback_parts = [
                    part
                    for part in [
                        ai_feedback,
                        teacher_feedback,
                        feed_back_text,
                        feed_forward_text,
                    ]
                    if part
                ]
                feedback_md = "\n\n".join(feedback_parts) if feedback_parts else None
                analysis_json = ai_insights_text

                if dry_run:
                    skipped += 1
                    continue

                cur.execute(
                    """
                    insert into public.learning_submissions (
                        id, course_id, task_id, student_sub, kind, text_body,
                        storage_key, mime_type, size_bytes, sha256,
                        attempt_nr, analysis_status, analysis_json,
                        feedback_md, error_code, idempotency_key,
                        created_at, completed_at
                    )
                    values (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s,
                            NULL, NULL, NULL, NULL,
                            %s, %s, %s,
                            %s, NULL, NULL,
                            coalesce(%s, now()), %s)
                    on conflict (id) do update set
                      text_body = excluded.text_body,
                      analysis_status = excluded.analysis_status,
                      analysis_json = excluded.analysis_json,
                      feedback_md = excluded.feedback_md,
                      completed_at = excluded.completed_at
                    """,
                    (
                        submission_id,
                        course_id,
                        task_id,
                        student_sub,
                        kind,
                        text_body,
                        attempt_nr,
                        analysis_status,
                        analysis_json,
                        feedback_md,
                        submitted_at,
                        feedback_generated_at,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

        details = {
            "legacy_submissions": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_students:
            details["missing_students"] = missing_students[:10]
        if missing_tasks:
            details["missing_tasks"] = missing_tasks[:10]
        if missing_courses:
            details["missing_courses"] = missing_courses[:10]

        status = "success"
        warnings: list[str] = []
        if missing_students:
            status = "partial"
            warnings.append(f"{len(missing_students)} submission(s) skipped due to missing student mapping.")
        if missing_tasks:
            status = "partial"
            warnings.append(f"{len(missing_tasks)} submission(s) skipped due to missing task mapping.")
        if missing_courses:
            status = "partial"
            warnings.append(f"{len(missing_courses)} submission(s) skipped due to missing course mapping.")

        return PhaseResult(
            name="learning_submissions",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings if warnings else None,
            details=details,
        )


def transfer_module_section_releases(dsn: str, legacy_schema: str, dry_run: bool) -> PhaseResult:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        identity_map = _load_existing_user_map(conn)
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("select id::text, teacher_id from public.courses")
            course_owner_map = {course_id: teacher_id for course_id, teacher_id in cur.fetchall()}

        inserted = 0
        updated = 0
        skipped = 0
        missing_modules: list[str] = []

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                sql.SQL(
                    """
                    select s.course_id::text,
                           s.section_id::text,
                           s.is_published,
                           s.published_at,
                           cm.id::text as course_module_id
                    from {} s
                    join public.unit_sections us on us.id = s.section_id::uuid
                    join public.course_modules cm on cm.course_id = s.course_id::uuid and cm.unit_id = us.unit_id
                    """
                ).format(sql.Identifier(legacy_schema, "course_unit_section_status"))
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            for course_id, section_id, is_published, published_at, course_module_id in rows:
                if course_module_id is None:
                    missing_modules.append(f"{course_id}:{section_id}")
                    skipped += 1
                    continue

                released_by = course_owner_map.get(course_id)
                if not released_by:
                    released_by = "system"

                visible = bool(is_published)
                released_at = published_at if visible else None

                if dry_run:
                    skipped += 1
                    continue

                cur.execute(
                    """
                    insert into public.module_section_releases (
                        course_module_id, section_id, visible, released_at, released_by
                    )
                    values (%s::uuid, %s::uuid, %s, %s, %s)
                    on conflict (course_module_id, section_id) do update set
                      visible = excluded.visible,
                      released_at = excluded.released_at,
                      released_by = excluded.released_by
                    """,
                    (
                        course_module_id,
                        section_id,
                        visible,
                        released_at,
                        released_by,
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

        details = {
            "legacy_releases": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dry_run": dry_run,
        }
        if missing_modules:
            details["missing_course_modules"] = missing_modules[:10]

        status = "success" if not missing_modules else "partial"
        warnings = None
        if missing_modules:
            warnings = [
                f"{len(missing_modules)} release(s) skipped due to missing course module; see details.missing_course_modules."
            ]

        return PhaseResult(
            name="module_section_releases",
            status=status,
            inserted=inserted,
            skipped=skipped,
            warnings=warnings,
            details=details,
        )


def run_validation(dsn: str) -> Dict[str, Any]:
    ensure_psycopg()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            def count(query: str) -> int:
                cur.execute(query)
                result = cur.fetchone()
                return int(result[0]) if result and result[0] is not None else 0

            validation = {
                "courses": count("select count(*) from public.courses"),
                "course_memberships": count("select count(*) from public.course_memberships"),
                "units": count("select count(*) from public.units"),
                "unit_sections": count("select count(*) from public.unit_sections"),
                "unit_materials": count("select count(*) from public.unit_materials"),
                "unit_tasks": count("select count(*) from public.unit_tasks"),
                "learning_submissions": count("select count(*) from public.learning_submissions"),
                "module_section_releases": count("select count(*) from public.module_section_releases"),
            }

            mastery_tables = {
                "mastery_tasks": count("select count(*) from "
                                        "information_schema.tables where table_schema='public' and table_name='mastery_tasks'")
            }

    validation.update({"mastery_tables_in_public": mastery_tables})
    return validation


def restore_legacy_schema(dump: DumpInfo, dsn: str, legacy_schema: str) -> dict[str, Any]:
    ensure_psycopg()

    start_time = time.time()
    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        conn.autocommit = True
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(sql.SQL("drop schema if exists {} cascade").format(sql.Identifier(legacy_schema)))
            cur.execute(sql.SQL("create schema {}").format(sql.Identifier(legacy_schema)))

    if dump.format == "custom":
        schema_sql = run_command_capture(
            [
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--schema=public",
                "--section=pre-data",
                "-f",
                "-",
                str(dump.path),
            ]
        )
        data_sql = run_command_capture(
            [
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--schema=public",
                "--section=data",
                "-f",
                "-",
                str(dump.path),
            ]
        )
    else:
        schema_sql = Path(dump.path).read_text(encoding="utf-8")
        data_sql = ""

    schema_sql = rewrite_schema_sql(schema_sql, legacy_schema)
    data_sql = rewrite_data_sql(data_sql, legacy_schema)

    run_command_input(
        [
            "psql",
            "--set",
            "ON_ERROR_STOP=1",
            dsn,
        ],
        schema_sql,
    )

    if data_sql.strip():
        run_command_input(
            [
                "psql",
                "--set",
                "ON_ERROR_STOP=1",
                dsn,
            ],
            data_sql,
        )

    with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = %s
                order by table_name
                """,
                (legacy_schema,),
            )
            tables = [row[0] for row in cur.fetchall()]

    duration = time.time() - start_time
    LOG.info(
        "Restored legacy dump: %s tables into schema %s in %.1fs",
        len(tables),
        legacy_schema,
        duration,
    )
    return {
        "tables_moved": tables,
        "duration_seconds": round(duration, 2),
    }


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    try:
        dsn = resolve_dsn(args)
    except Exception as exc:  # pragma: no cover - initial guard
        LOG.error("Failed to resolve DSN: %s", exc)
        sys.exit(1)

    workdir = prepare_workdir(args.workdir, keep_temp=args.keep_temp)
    dump_info = extract_dump(Path(args.dump), workdir)

    kc_config: KeycloakConfig | None = None
    kc_base_url = args.kc_base_url or os.environ.get("KEYCLOAK_BASE_URL")
    kc_admin_user = args.kc_admin_user or os.environ.get("KEYCLOAK_ADMIN_USER")
    kc_admin_pass = args.kc_admin_pass or os.environ.get("KEYCLOAK_ADMIN_PASSWORD")
    kc_host_header = args.kc_host_header or os.environ.get("KEYCLOAK_HOST_HEADER")
    kc_realm = args.kc_realm or os.environ.get("KEYCLOAK_REALM", "gustav")
    if kc_base_url and kc_admin_user and kc_admin_pass:
        if not kc_host_header:
            parsed = urlparse(kc_base_url)
            kc_host_header = parsed.netloc or parsed.hostname or ""
        kc_config = KeycloakConfig(
            base_url=kc_base_url.rstrip("/"),
            host_header=kc_host_header or "",
            realm=kc_realm,
            admin_user=kc_admin_user,
            admin_pass=kc_admin_pass,
            timeout=float(args.kc_timeout),
        )
        if not kc_config.host_header:
            LOG.warning("Keycloak host header missing; requests may fail")

    LOG.info(
        "Ready to restore legacy dump: path=%s format=%s size=%.2f MB",
        dump_info.path,
        dump_info.format,
        dump_info.size_bytes / (1024 * 1024),
    )
    # Security: Do not log the DSN to avoid leaking credentials in logs.
    LOG.info("Legacy schema: %s", args.legacy_schema)
    LOG.info("Storage root: %s", args.storage_root)

    report_path = Path(args.report) if args.report else Path("docs/migration/reports") / f"legacy_import_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        # Intentionally omit DSN to prevent credential leaks in reports.
        "legacy_schema": args.legacy_schema,
        "dump": {
            "path": str(dump_info.path),
            "format": dump_info.format,
            "size_bytes": dump_info.size_bytes,
        },
        "status": "in_progress",
        "phases": [],
        "warnings": [],
        "errors": [],
    }

    try:
        restore_details = restore_legacy_schema(dump_info, dsn, args.legacy_schema)
        report["phases"].append(phase_to_dict(PhaseResult(name="restore", status="success", details=restore_details)))
    except Exception as exc:  # pragma: no cover - runtime safeguard
        LOG.error("Restore failed: %s", exc)
        report["errors"].append(f"restore failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        identity_result = build_identity_map(dsn, args.legacy_schema, args.dry_run, kc_config)
        report["phases"].append(phase_to_dict(identity_result))
        if identity_result.status != "success":
            report["status"] = "failed"
            report["errors"].append("identity mapping incomplete")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Identity mapping did not complete successfully.")
            sys.exit(1)
    except Exception as exc:  # pragma: no cover
        LOG.error("Identity mapping failed: %s", exc)
        report["errors"].append(f"identity failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        courses_result = transfer_courses(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(courses_result))
        if courses_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("course transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Course transfer did not complete successfully.")
            sys.exit(1)
        if courses_result.status == "partial":
            report["warnings"].append("Course transfer completed with missing teacher mappings.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Course transfer failed: %s", exc)
        report["errors"].append(f"courses failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        memberships_result = transfer_course_memberships(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(memberships_result))
        if memberships_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("course membership transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Course membership transfer did not complete successfully.")
            sys.exit(1)
        if memberships_result.status == "partial":
            report["warnings"].append("Course membership transfer completed with missing student mappings.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Course membership transfer failed: %s", exc)
        report["errors"].append(f"course_memberships failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        units_result = transfer_units(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(units_result))
        if units_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("unit transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Unit transfer did not complete successfully.")
            sys.exit(1)
        if units_result.status == "partial":
            report["warnings"].append("Unit transfer completed with missing author mappings.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Unit transfer failed: %s", exc)
        report["errors"].append(f"units failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        modules_result = transfer_course_modules(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(modules_result))
        if modules_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("course module transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Course module transfer did not complete successfully.")
            sys.exit(1)
        if modules_result.status == "partial":
            report["warnings"].append("Course module transfer completed with missing course/unit references.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Course module transfer failed: %s", exc)
        report["errors"].append(f"course_modules failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        sections_result = transfer_unit_sections(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(sections_result))
        if sections_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("unit section transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Unit section transfer did not complete successfully.")
            sys.exit(1)
        if sections_result.status == "partial":
            report["warnings"].append("Unit section transfer completed with missing unit references.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Unit section transfer failed: %s", exc)
        report["errors"].append(f"unit_sections failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        materials_result = transfer_materials(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(materials_result))
        if materials_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("material transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Material transfer did not complete successfully.")
            sys.exit(1)
    except Exception as exc:  # pragma: no cover
        LOG.error("Material transfer failed: %s", exc)
        report["errors"].append(f"materials failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        tasks_result = transfer_unit_tasks(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(tasks_result))
        if tasks_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("task transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Task transfer did not complete successfully.")
            sys.exit(1)
        if tasks_result.status == "partial":
            report["warnings"].append("Task transfer completed with missing section/unit references.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Task transfer failed: %s", exc)
        report["errors"].append(f"unit_tasks failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        submissions_result = transfer_submissions(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(submissions_result))
        if submissions_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("submission transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Submission transfer did not complete successfully.")
            sys.exit(1)
        if submissions_result.status == "partial":
            report["warnings"].append("Submission transfer completed with missing references; see details.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Submission transfer failed: %s", exc)
        report["errors"].append(f"learning_submissions failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        releases_result = transfer_module_section_releases(dsn, args.legacy_schema, args.dry_run)
        report["phases"].append(phase_to_dict(releases_result))
        if releases_result.status not in {"success", "partial"}:
            report["status"] = "failed"
            report["errors"].append("section release transfer failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("Section release transfer did not complete successfully.")
            sys.exit(1)
        if releases_result.status == "partial":
            report["warnings"].append("Section release transfer completed with missing course modules.")
    except Exception as exc:  # pragma: no cover
        LOG.error("Section release transfer failed: %s", exc)
        report["errors"].append(f"module_section_releases failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        login_result = ensure_app_login_role(args.dry_run)
        report["phases"].append(phase_to_dict(login_result))
        if login_result.status == "failed":
            report["status"] = "failed"
            report["errors"].append("app login provisioning failed")
            with report_path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
            LOG.error("App login provisioning failed; see report for details.")
            sys.exit(1)
        if login_result.status == "partial":
            report["warnings"].append("App login provisioning skipped or incomplete; manual follow-up recommended.")
    except Exception as exc:  # pragma: no cover
        LOG.error("App login provisioning raised an unexpected error: %s", exc)
        report["errors"].append(f"app_login failed: {exc}")
        report["status"] = "failed"
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        LOG.error("Import aborted. Report written to %s", report_path)
        sys.exit(1)

    try:
        validation = run_validation(dsn)
        report["validation"] = validation
    except Exception as exc:  # pragma: no cover
        LOG.warning("Validation failed: %s", exc)
        report["warnings"].append(f"validation failed: {exc}")
    report["status"] = "completed"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    LOG.info("Legacy import completed. Report written to %s", report_path)


if __name__ == "__main__":
    main()
