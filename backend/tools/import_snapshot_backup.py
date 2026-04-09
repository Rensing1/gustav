"""Snapshot backup importer for local/dev snapshots.

Purpose
-------
Restore a snapshot produced by the backup cron (`supabase_db.sql.gz` +
`storage_buckets.tar.gz`, optional `h5p_storage.tar.gz`, optional
`keycloak_db.sql.gz`) into a *local*
development instance after tests wiped the DB.

This tool imports snapshot data into a local Supabase stack while keeping
Supabase-managed schemas (`auth`, `storage`, `pgbouncer`, ...) under local
runtime control. The importer restores only app-relevant schemas from the dump
and replays storage objects through the local Storage API.

Security & Safety
-----------------
- Snapshot files contain real user data (PII). Never commit them.
- By default this tool refuses to run against non-local DSNs. Use
  `--allow-remote-dsn` only if you are absolutely sure.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional
from urllib.parse import quote, urlsplit, urlunsplit

import requests

try:  # Optional dependency guard (psycopg is already used by the web service)
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]
    conninfo_to_dict = None  # type: ignore[assignment]


LOG = logging.getLogger("gustav.tools.import_snapshot")

LOCAL_DSN_HOSTS = {
    "",
    "localhost",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
}

# Keep local Supabase service-managed schemas intact. The local runtime owns the
# technical bootstrap of `auth`, `storage`, `realtime`, etc. Snapshot imports
# should only replace app-relevant schemas.
RESTORE_TARGET_SCHEMAS = {
    "public",
    "legacy_raw",
}

_PG_DUMP_OBJECT_HEADER_RE = re.compile(
    rb"^-- (?:Data for )?Name: (?P<name>.*); Type: (?P<type>.*); Schema: (?P<schema>.*); Owner: (?P<owner>.*)$"
)

LOCAL_BUCKET_ALLOWED_MIME_TYPES: dict[str, tuple[str, ...]] = {
    "materials": (
        "application/pdf",
        "image/jpeg",
        "image/png",
    ),
    "submissions": (
        "application/pdf",
        "application/x.makecode.hex",
        "application/x.scratch.sb3",
        "image/jpeg",
        "image/png",
    ),
}

LOCAL_H5P_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "supabase" / "storage" / "h5p"


@dataclass(frozen=True)
class SnapshotFiles:
    root: Path
    supabase_db_sql_gz: Path
    storage_buckets_tar_gz: Path
    h5p_storage_tar_gz: Optional[Path] = None
    keycloak_db_sql_gz: Optional[Path] = None


@dataclass(frozen=True)
class SnapshotMigration:
    version: str
    statements: str
    name: str
    copy_line: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a Supabase snapshot (DB + storage buckets) into local dev.")
    parser.add_argument("--snapshot", required=True, help="Path to snapshot dir or .tar.gz (contains supabase_db.sql.gz)")
    parser.add_argument("--dsn", help="Postgres DSN; falls back to SERVICE_ROLE_DSN env")
    parser.add_argument("--supabase-url", help="Supabase API base URL (e.g. http://127.0.0.1:54321)")
    parser.add_argument("--supabase-service-role-key", help="Supabase service role key (JWT)")
    parser.add_argument("--workdir", default=".tmp/snapshot_import_run", help="Work directory for extracted files/reports")
    parser.add_argument("--no-reset", action="store_true", help="Skip dropping existing schemas before restore")
    parser.add_argument("--skip-storage", action="store_true", help="Skip storage bucket upload")
    parser.add_argument(
        "--skip-keycloak",
        action="store_true",
        help="Skip Keycloak DB restore even if keycloak_db.sql.gz exists in snapshot",
    )
    parser.add_argument(
        "--keycloak-db-container",
        default=os.getenv("KEYCLOAK_DB_CONTAINER", "gustav-keycloak-db"),
        help="Docker container name for Keycloak Postgres",
    )
    parser.add_argument(
        "--keycloak-db-user",
        default=os.getenv("KC_DB_USERNAME", "keycloak"),
        help="Keycloak Postgres user",
    )
    parser.add_argument(
        "--keycloak-db-name",
        default=os.getenv("KC_DB_NAME", "keycloak"),
        help="Keycloak Postgres database",
    )
    parser.add_argument(
        "--keycloak-container",
        default=os.getenv("KEYCLOAK_CONTAINER", "gustav-keycloak"),
        help="Docker container name for Keycloak service (restarted after restore)",
    )
    parser.add_argument(
        "--keycloak-realm",
        default=os.getenv("KC_REALM", "gustav"),
        help="Keycloak realm to localize after restore",
    )
    parser.add_argument(
        "--keycloak-web-client-id",
        default=os.getenv("KC_CLIENT_ID", "gustav-web"),
        help="Keycloak OIDC client ID for web login redirects",
    )
    parser.add_argument(
        "--keycloak-web-base",
        default=os.getenv("WEB_BASE", "https://app.localhost"),
        help="Local app base URL used for Keycloak web client redirect/origin",
    )
    parser.add_argument(
        "--keycloak-admin-realm",
        default=os.getenv("KC_ADMIN_REALM", "master"),
        help="Realm that contains the admin API client used by the web app",
    )
    parser.add_argument(
        "--keycloak-admin-client-id",
        default=os.getenv("KC_ADMIN_CLIENT_ID", "gustav-admin-cli"),
        help="Client ID used for Keycloak admin API calls in the web app",
    )
    parser.add_argument(
        "--keycloak-admin-client-secret",
        default=(os.getenv("KC_ADMIN_CLIENT_SECRET") or "").strip(),
        help="Client secret to enforce for the admin API client (optional)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run preflight checks only (no writes)")
    parser.add_argument("--allow-remote-dsn", action="store_true", help="Allow restoring into non-local DSNs (dangerous)")
    parser.add_argument(
        "--allow-missing-h5p",
        action="store_true",
        help="Continue the import when H5P DB rows reference missing local H5P content files",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _redact_pg_uri(uri: str) -> str:
    if uri.startswith("postgres://") or uri.startswith("postgresql://"):
        parts = urlsplit(uri)
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        user = parts.username or ""
        netloc = host
        if user:
            netloc = f"{user}@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return uri


def resolve_dsn(args: argparse.Namespace) -> str:
    if args.dsn:
        return args.dsn
    env_dsn = (os.getenv("SERVICE_ROLE_DSN") or "").strip()
    if env_dsn:
        return env_dsn
    raise RuntimeError("Missing --dsn and SERVICE_ROLE_DSN is not set.")


def _dsn_host(dsn: str) -> str:
    # Prefer psycopg's parser for both URIs and conninfo strings.
    if conninfo_to_dict is not None:
        try:
            info = conninfo_to_dict(dsn)  # type: ignore[misc]
            host = (info.get("host") or "").strip()
            return host
        except Exception:
            pass

    # Fallback: URI parsing
    if dsn.startswith("postgres://") or dsn.startswith("postgresql://"):
        return (urlsplit(dsn).hostname or "").strip()

    # Fallback: conninfo parsing for `host=...`
    for part in dsn.split():
        if part.startswith("host="):
            return part.split("=", 1)[1].strip()
    return ""


def ensure_local_dsn(dsn: str, *, allow_remote: bool) -> None:
    host = _dsn_host(dsn)
    if host in LOCAL_DSN_HOSTS:
        return
    if allow_remote:
        LOG.warning("Non-local DSN allowed by flag: host=%s dsn=%s", host, _redact_pg_uri(dsn))
        return
    raise RuntimeError(
        f"Refusing to run against non-local DSN host={host!r}. "
        "Use --allow-remote-dsn to override (dangerous)."
    )


def _psql_query_scalar(dsn: str, query: str) -> str:
    res = subprocess.run(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-At", "-c", query],
        check=True,
        capture_output=True,
        text=True,
    )
    out = (res.stdout or "").strip()
    if not out:
        raise RuntimeError("psql query returned no output")
    return out.splitlines()[0].strip()


def _is_superuser_dsn(dsn: str) -> bool:
    # psql prints booleans as `t`/`f` in unaligned tuples-only mode.
    val = _psql_query_scalar(dsn, "select rolsuper from pg_roles where rolname=current_user;")
    return val.lower() in {"t", "true", "1", "yes"}


def ensure_superuser_for_reset(dsn: str) -> bool:
    """Fail fast when the DSN role cannot do a full schema reset.

    The snapshot dump uses `CREATE SCHEMA ...` without `IF NOT EXISTS`, so the
    restore must start from a clean DB. On Supabase local, many schemas are
    owned by `supabase_admin` (superuser), not by `postgres`.
    """

    is_superuser = _is_superuser_dsn(dsn)
    if is_superuser:
        return True
    raise RuntimeError(
        "Snapshot restore requires a superuser DSN to drop/recreate Supabase schemas. "
        "In Supabase local, use `supabase_admin` (e.g. "
        "postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres) or pass --no-reset."
    )


def _safe_extract_tar(tar: tarfile.TarFile, dest: Path) -> None:
    dest = dest.resolve()
    for member in tar.getmembers():
        name = member.name
        if name.startswith("/") or name.startswith("\\"):
            raise RuntimeError(f"Unsafe absolute path in tar member: {name!r}")
        if ".." in Path(name).parts:
            raise RuntimeError(f"Unsafe parent traversal in tar member: {name!r}")
        if member.issym() or member.islnk():
            raise RuntimeError(f"Refusing to extract symlink/hardlink from tar member: {name!r}")
        if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
            raise RuntimeError(f"Refusing to extract special file from tar member: {name!r}")
        target = (dest / name).resolve()
        try:
            target.relative_to(dest)
        except ValueError as exc:
            raise RuntimeError(f"Unsafe tar member path: {name!r}") from exc
    try:
        tar.extractall(dest, filter="data")  # Python 3.12+
    except TypeError:  # pragma: no cover - compatibility with older Python
        tar.extractall(dest)


def _find_unique(root: Path, filename: str) -> Path:
    matches = list(root.rglob(filename))
    if not matches:
        raise FileNotFoundError(f"{filename} not found under {root}")
    if len(matches) > 1:
        sample = ", ".join(str(p) for p in matches[:5])
        raise RuntimeError(f"Multiple {filename} found under {root} (sample: {sample})")
    return matches[0]


def _find_optional(root: Path, filename: str) -> Optional[Path]:
    matches = list(root.rglob(filename))
    if not matches:
        return None
    if len(matches) > 1:
        sample = ", ".join(str(p) for p in matches[:5])
        raise RuntimeError(f"Multiple {filename} found under {root} (sample: {sample})")
    return matches[0]


def resolve_snapshot_files(snapshot: Path, extract_root: Path) -> SnapshotFiles:
    snapshot = snapshot.resolve()
    if snapshot.is_dir():
        root = snapshot
    elif snapshot.is_file() and snapshot.name.endswith((".tar.gz", ".tgz")):
        extract_root.mkdir(parents=True, exist_ok=True)
        with tarfile.open(snapshot, "r:gz") as tar:
            _safe_extract_tar(tar, extract_root)
        root = extract_root
    else:
        raise ValueError("snapshot must be a directory or a .tar.gz/.tgz file")

    db_sql = _find_unique(root, "supabase_db.sql.gz")
    storage_tar = _find_unique(root, "storage_buckets.tar.gz")
    h5p_storage_tar = _find_optional(root, "h5p_storage.tar.gz")
    keycloak_sql = _find_optional(root, "keycloak_db.sql.gz")
    return SnapshotFiles(
        root=root,
        supabase_db_sql_gz=db_sql,
        storage_buckets_tar_gz=storage_tar,
        h5p_storage_tar_gz=h5p_storage_tar,
        keycloak_db_sql_gz=keycloak_sql,
    )


def _psql_check(dsn: str) -> None:
    subprocess.run(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-c", "select 1"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _reset_db_for_restore(dsn: str) -> None:
    _drop_restore_target_schemas(dsn)
    # The filtered dump replays app objects only. `public` may be omitted as a
    # schema object in pg_dump output, so recreate it explicitly before replay.
    subprocess.run(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-c", "create schema if not exists public;"],
        check=True,
    )


def _drop_restore_target_schemas(dsn: str) -> None:
    schema_literals = ", ".join(f"'{schema}'" for schema in sorted(RESTORE_TARGET_SCHEMAS))
    sql = f"""
do $$
declare
  r record;
begin
  for r in (
    select nspname
    from pg_namespace
    where nspname in ({schema_literals})
  ) loop
    execute format('drop schema if exists %I cascade', r.nspname);
  end loop;
end $$;
"""
    subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-c", sql], check=True)


def expected_local_migration_owner() -> str:
    """Return the local role expected to run `supabase migration up`."""
    return str(os.getenv("DB_SUPERUSER", "postgres")).strip() or "postgres"


def _normalize_restore_target_ownership(dsn: str, target_owner: str) -> None:
    """Reassign restored app objects to the local migration runner.

    Snapshot imports run with a superuser DSN (`supabase_admin`) so they can
    reset app schemas. Without an explicit owner handoff afterwards, restored
    tables/functions stay owned by that restore role and later
    `supabase migration up` runs as `postgres` can fail on `ALTER TABLE`.
    """

    owner_literal = target_owner.replace("'", "''")
    schema_literals = ", ".join(f"'{schema}'" for schema in sorted(RESTORE_TARGET_SCHEMAS))
    sql = f"""
do $$
declare
  target_owner text := '{owner_literal}';
  r record;
begin
  for r in (
    select nspname
      from pg_namespace
     where nspname in ({schema_literals})
  ) loop
    execute format('alter schema %I owner to %I', r.nspname, target_owner);
  end loop;

  for r in (
    select n.nspname, c.relname, c.relkind
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     where n.nspname in ({schema_literals})
       and c.relkind in ('r', 'p', 'v', 'm', 'S', 'f')
  ) loop
    case r.relkind
      when 'S' then
        execute format('alter sequence %I.%I owner to %I', r.nspname, r.relname, target_owner);
      when 'v' then
        execute format('alter view %I.%I owner to %I', r.nspname, r.relname, target_owner);
      when 'm' then
        execute format('alter materialized view %I.%I owner to %I', r.nspname, r.relname, target_owner);
      else
        execute format('alter table %I.%I owner to %I', r.nspname, r.relname, target_owner);
    end case;
  end loop;

  for r in (
    select n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) as args, p.prokind
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname in ({schema_literals})
       and p.prokind in ('f', 'p')
  ) loop
    if r.prokind = 'p' then
      execute format('alter procedure %I.%I(%s) owner to %I', r.nspname, r.proname, r.args, target_owner);
    else
      execute format('alter function %I.%I(%s) owner to %I', r.nspname, r.proname, r.args, target_owner);
    end if;
  end loop;

  for r in (
    select n.nspname, t.typname
      from pg_type t
      join pg_namespace n on n.oid = t.typnamespace
     where n.nspname in ({schema_literals})
       and t.typtype in ('d', 'e')
  ) loop
    execute format('alter type %I.%I owner to %I', r.nspname, r.typname, target_owner);
  end loop;
end $$;
"""
    subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-c", sql], check=True)


def _decode_dump_header_value(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").strip()


def extract_snapshot_migration_history(db_sql_gz: Path) -> list[SnapshotMigration]:
    """Read `supabase_migrations.schema_migrations` rows embedded in the dump."""

    rows: list[SnapshotMigration] = []
    inside_copy = False
    with gzip.open(db_sql_gz, "rt", encoding="utf-8", errors="replace") as dump:
        for line in dump:
            if line.startswith("COPY supabase_migrations.schema_migrations "):
                inside_copy = True
                continue
            if not inside_copy:
                continue
            if line.strip() == r"\.":
                break
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) != 3:
                raise RuntimeError(
                    "Malformed supabase_migrations.schema_migrations row in snapshot dump."
                )
            rows.append(
                SnapshotMigration(
                    version=parts[0],
                    statements=parts[1],
                    name=parts[2],
                    copy_line=line.rstrip("\n"),
                )
            )
    if not rows:
        raise RuntimeError("Snapshot dump does not contain supabase_migrations.schema_migrations rows.")
    return rows


def sync_snapshot_migration_history(dsn: str, rows: list[SnapshotMigration]) -> None:
    """Replace local Supabase migration history with the snapshot's history."""

    proc = subprocess.Popen(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1"],
        stdin=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    try:
        proc.stdin.write("truncate table supabase_migrations.schema_migrations;\n")
        proc.stdin.write("copy supabase_migrations.schema_migrations(version, statements, name) from stdin;\n")
        for row in rows:
            proc.stdin.write(f"{row.copy_line}\n")
        proc.stdin.write("\\.\n")
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"psql migration history sync failed with exit code {rc}")


def _should_keep_dump_object(header_line: bytes) -> bool:
    match = _PG_DUMP_OBJECT_HEADER_RE.match(header_line.rstrip(b"\n"))
    if match is None:
        return True

    object_type = _decode_dump_header_value(match.group("type"))
    schema = _decode_dump_header_value(match.group("schema"))
    name = _decode_dump_header_value(match.group("name"))

    if schema in RESTORE_TARGET_SCHEMAS:
        return True
    if object_type == "SCHEMA" and name in RESTORE_TARGET_SCHEMAS:
        return True
    if schema == "-" and name.startswith("SCHEMA "):
        return name.removeprefix("SCHEMA ").strip() in RESTORE_TARGET_SCHEMAS
    return False


def _iter_filtered_dump_lines(lines: Iterable[bytes]) -> Iterator[bytes]:
    current_block: list[bytes] = []
    keep_current_block = True
    in_object_block = False

    def flush_current_block() -> Iterator[bytes]:
        nonlocal current_block
        if keep_current_block:
            yield from current_block
        current_block = []

    for line in lines:
        if _PG_DUMP_OBJECT_HEADER_RE.match(line.rstrip(b"\n")):
            if in_object_block:
                yield from flush_current_block()
            keep_current_block = _should_keep_dump_object(line)
            current_block = [line]
            in_object_block = True
            continue

        if in_object_block:
            current_block.append(line)
            continue

        yield line

    if in_object_block:
        yield from flush_current_block()


def _restore_db_sql_gz(db_sql_gz: Path, dsn: str) -> None:
    start = time.monotonic()
    LOG.info("Restoring DB from %s ...", db_sql_gz)
    LOG.info("Filtering snapshot DB restore to app schemas: %s", ", ".join(sorted(RESTORE_TARGET_SCHEMAS)))

    proc = subprocess.Popen(["psql", dsn, "-v", "ON_ERROR_STOP=1"], stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        with gzip.open(db_sql_gz, "rb") as f:
            for raw_line in _iter_filtered_dump_lines(f):
                if _is_graphql_public_grant_line(raw_line):
                    continue
                if _is_unsupported_pg_setting_line(raw_line):
                    continue
                proc.stdin.write(raw_line)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"psql restore failed with exit code {rc}")

    LOG.info("DB restore done in %.1fs", time.monotonic() - start)


def _is_graphql_public_grant_line(line: bytes) -> bool:
    return line.lstrip().startswith(b"GRANT ALL ON FUNCTION graphql_public.graphql(")


def _is_unsupported_pg_setting_line(line: bytes) -> bool:
    stripped = line.lstrip().lower()
    return stripped.startswith(b"set transaction_timeout")


def _run_docker_psql(*, container: str, db_user: str, db_name: str, sql: str) -> None:
    subprocess.run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            db_user,
            "-d",
            db_name,
            "-c",
            sql,
        ],
        check=True,
    )


def _reset_keycloak_db_for_restore(*, keycloak_db_container: str, keycloak_db_user: str, keycloak_db_name: str) -> None:
    sql = """
do $$
declare
  r record;
begin
  for r in (
    select nspname
    from pg_namespace
    where nspname not in ('pg_catalog', 'information_schema')
      and nspname not like 'pg_toast%'
      and nspname not like 'pg_temp_%'
      and nspname not like 'pg_toast_temp_%'
  ) loop
    execute format('drop schema if exists %I cascade', r.nspname);
  end loop;
end $$;

create schema if not exists public;
"""
    _run_docker_psql(
        container=keycloak_db_container,
        db_user=keycloak_db_user,
        db_name=keycloak_db_name,
        sql=sql,
    )


def _restore_keycloak_db_sql_gz(
    *,
    db_sql_gz: Path,
    keycloak_db_container: str,
    keycloak_db_user: str,
    keycloak_db_name: str,
) -> None:
    start = time.monotonic()
    LOG.info("Restoring Keycloak DB from %s ...", db_sql_gz)
    _reset_keycloak_db_for_restore(
        keycloak_db_container=keycloak_db_container,
        keycloak_db_user=keycloak_db_user,
        keycloak_db_name=keycloak_db_name,
    )

    proc = subprocess.Popen(
        [
            "docker",
            "exec",
            "-i",
            keycloak_db_container,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            keycloak_db_user,
            "-d",
            keycloak_db_name,
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None
    try:
        with gzip.open(db_sql_gz, "rb") as f:
            for raw_line in f:
                if _is_unsupported_pg_setting_line(raw_line):
                    continue
                proc.stdin.write(raw_line)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"Keycloak psql restore failed with exit code {rc}")

    LOG.info("Keycloak DB restore done in %.1fs", time.monotonic() - start)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_keycloak_localization_sql(*, realm: str, web_client_id: str, app_base_url: str) -> str:
    app_base = app_base_url.rstrip("/")
    redirect_uri = f"{app_base}/*"
    return f"""
do $$
declare
  rid varchar(36);
  cid varchar(36);
begin
  select id into rid from realm where name = {_sql_literal(realm)};
  if rid is null then
    raise exception 'Keycloak realm not found: %', {_sql_literal(realm)};
  end if;

  select id into cid from client where realm_id = rid and client_id = {_sql_literal(web_client_id)};
  if cid is null then
    raise exception 'Keycloak client not found in realm %: %', {_sql_literal(realm)}, {_sql_literal(web_client_id)};
  end if;

  delete from redirect_uris where client_id = cid;
  insert into redirect_uris(client_id, value) values (cid, {_sql_literal(redirect_uri)});

  delete from web_origins where client_id = cid;
  insert into web_origins(client_id, value) values (cid, {_sql_literal(app_base)});
end $$;
"""


def _build_keycloak_admin_client_secret_sql(
    *,
    admin_realm: str,
    admin_client_id: str,
    admin_client_secret: str,
) -> str:
    return f"""
do $$
declare
  rid varchar(36);
  cid varchar(36);
begin
  select id into rid from realm where name = {_sql_literal(admin_realm)};
  if rid is null then
    raise notice 'Keycloak admin realm not found: %', {_sql_literal(admin_realm)};
    return;
  end if;

  select id into cid from client where realm_id = rid and client_id = {_sql_literal(admin_client_id)};
  if cid is null then
    raise notice 'Keycloak admin client not found in realm %: %', {_sql_literal(admin_realm)}, {_sql_literal(admin_client_id)};
    return;
  end if;

  update client set secret = {_sql_literal(admin_client_secret)} where id = cid;
end $$;
"""


def _sync_keycloak_admin_client_secret(
    *,
    keycloak_db_container: str,
    keycloak_db_user: str,
    keycloak_db_name: str,
    admin_realm: str,
    admin_client_id: str,
    admin_client_secret: str,
) -> None:
    if not admin_client_secret:
        LOG.info("Keycloak admin client secret sync skipped (no secret provided).")
        return
    realm_candidates = [admin_realm]
    if str(admin_realm).strip().lower() != "master":
        realm_candidates.append("master")

    seen: set[str] = set()
    for realm_name in realm_candidates:
        if realm_name in seen:
            continue
        seen.add(realm_name)
        sql = _build_keycloak_admin_client_secret_sql(
            admin_realm=realm_name,
            admin_client_id=admin_client_id,
            admin_client_secret=admin_client_secret,
        )
        _run_docker_psql(
            container=keycloak_db_container,
            db_user=keycloak_db_user,
            db_name=keycloak_db_name,
            sql=sql,
        )


def _localize_keycloak_for_local_web(
    *,
    keycloak_db_container: str,
    keycloak_db_user: str,
    keycloak_db_name: str,
    realm: str,
    web_client_id: str,
    app_base_url: str,
) -> None:
    sql = _build_keycloak_localization_sql(
        realm=realm,
        web_client_id=web_client_id,
        app_base_url=app_base_url,
    )
    _run_docker_psql(
        container=keycloak_db_container,
        db_user=keycloak_db_user,
        db_name=keycloak_db_name,
        sql=sql,
    )


def _build_keycloak_theme_localization_sql(
    *,
    realm: str,
    login_theme: str,
    account_theme: str,
    email_theme: str,
) -> str:
    return f"""
do $$
begin
  update realm
     set login_theme = {_sql_literal(login_theme)},
         account_theme = {_sql_literal(account_theme)},
         email_theme = {_sql_literal(email_theme)}
   where name = {_sql_literal(realm)};

  if not found then
    raise exception 'Keycloak realm not found: %', {_sql_literal(realm)};
  end if;
end $$;
"""


def _localize_keycloak_theme(
    *,
    keycloak_db_container: str,
    keycloak_db_user: str,
    keycloak_db_name: str,
    realm: str,
    login_theme: str,
    account_theme: str,
    email_theme: str,
) -> None:
    sql = _build_keycloak_theme_localization_sql(
        realm=realm,
        login_theme=login_theme,
        account_theme=account_theme,
        email_theme=email_theme,
    )
    _run_docker_psql(
        container=keycloak_db_container,
        db_user=keycloak_db_user,
        db_name=keycloak_db_name,
        sql=sql,
    )


def _restart_container(container_name: str) -> None:
    subprocess.run(["docker", "restart", container_name], check=True)


def _ensure_graphql_public_function(dsn: str) -> None:
    has_wrapper = _psql_query_scalar(
        dsn,
        "SELECT to_regprocedure('graphql_public.graphql(text, text, jsonb, jsonb)') IS NOT NULL;",
    )
    if has_wrapper.lower() in {"t", "true", "1", "yes"}:
        return

    has_resolve = _psql_query_scalar(
        dsn,
        "SELECT to_regprocedure('graphql.resolve(text, jsonb, text, jsonb)') IS NOT NULL;",
    )
    if has_resolve.lower() not in {"t", "true", "1", "yes"}:
        return

    create_sql = """
CREATE OR REPLACE FUNCTION graphql_public.graphql(
    "operationName" text default null,
    query text default null,
    variables jsonb default null,
    extensions jsonb default null
) RETURNS jsonb
    LANGUAGE sql
AS $$
    select graphql.resolve(
        query := query,
        variables := coalesce(variables, '{}'),
        "operationName" := "operationName",
        extensions := extensions
    );
$$;
"""
    grant_sql = """
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO postgres;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO anon;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO authenticated;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO service_role;
"""
    subprocess.run(["psql", dsn, "-v", "ON_ERROR_STOP=1", "-c", create_sql + grant_sql], check=True)


def _inspect_storage_tar(storage_tar_gz: Path) -> tuple[list[str], int, int]:
    files = 0
    total_bytes = 0
    paths: list[tuple[str, ...]] = []
    with tarfile.open(storage_tar_gz, "r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            files += 1
            total_bytes += int(m.size or 0)
            parts = tuple(p for p in Path(m.name).parts if p not in ("", "."))
            if parts:
                paths.append(parts)

    # Best-effort bucket inference:
    # - Choose the first path component index with a small number of distinct values (>=2),
    #   which usually corresponds to the bucket directory (wrapper dirs often have only 1 value).
    # - If we can't infer reliably (e.g. only one bucket), fall back to the first component.
    buckets: set[str] = set()
    if paths:
        max_depth = min(6, max(len(p) for p in paths))
        bucket_index: int | None = None
        for i in range(max_depth - 1):  # bucket must have at least 1 key segment after it
            vals = {p[i] for p in paths if len(p) >= i + 2}
            if 2 <= len(vals) <= 50:
                bucket_index = i
                buckets = vals
                break
        if bucket_index is None:
            buckets = {p[0] for p in paths if len(p) >= 2}
    return sorted(buckets), files, total_bytes


def _extract_storage_tar(storage_tar_gz: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(storage_tar_gz, "r:gz") as tar:
        _safe_extract_tar(tar, dest)
    return dest


def _clear_directory_contents(dest: Path) -> Path:
    """Remove all children from a directory while keeping the directory itself."""
    dest.mkdir(parents=True, exist_ok=True)
    for child in dest.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
            continue
        child.unlink()
    return dest


def _restore_h5p_storage_tar(h5p_storage_tar_gz: Path, dest: Path) -> Path:
    """Restore H5P storage in place so bind-mounted container roots stay stable."""
    _clear_directory_contents(dest)
    with tarfile.open(h5p_storage_tar_gz, "r:gz") as tar:
        _safe_extract_tar(tar, dest)
    return dest


def _list_snapshot_h5p_task_refs(dsn: str) -> list[dict[str, object]]:
    """Return all distinct H5P task references restored from the snapshot DB."""
    if psycopg is None:
        raise RuntimeError("psycopg is required to inspect restored H5P task references.")

    query = """
        select t.h5p_content_id::text as content_id,
               t.id::text as task_id,
               t.unit_id::text as unit_id,
               coalesce(
                 array_agg(distinct cm.course_id::text) filter (where cm.course_id is not null),
                 array[]::text[]
               ) as course_ids
          from public.unit_tasks t
          left join public.course_modules cm on cm.unit_id = t.unit_id
         where t.kind = 'h5p'
           and t.h5p_content_id is not null
         group by t.h5p_content_id, t.id, t.unit_id
         order by t.h5p_content_id, t.id
    """
    items: list[dict[str, object]] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            for content_id, task_id, unit_id, course_ids in cur.fetchall() or []:
                items.append(
                    {
                        "content_id": str(content_id),
                        "task_id": str(task_id),
                        "unit_id": str(unit_id),
                        "course_ids": [str(course_id) for course_id in (course_ids or [])],
                    }
                )
    return items


def _assert_snapshot_h5p_storage_complete(dsn: str, h5p_root: Path) -> dict[str, list[str]]:
    """Fail fast when restored snapshot DB rows reference missing H5P content."""
    refs = _list_snapshot_h5p_task_refs(dsn)
    expected_ids = sorted({str(item["content_id"]) for item in refs if str(item.get("content_id") or "").strip()})
    if not expected_ids:
        return {"expected_ids": [], "missing_ids": []}

    missing_ids = [content_id for content_id in expected_ids if not (h5p_root / "content" / content_id).is_dir()]
    if not missing_ids:
        return {"expected_ids": expected_ids, "missing_ids": []}

    examples: list[str] = []
    for item in refs:
        content_id = str(item.get("content_id") or "")
        if content_id not in missing_ids:
            continue
        course_ids = ",".join(str(course_id) for course_id in (item.get("course_ids") or [])) or "-"
        examples.append(
            f"content_id={content_id} task_id={item.get('task_id')} unit_id={item.get('unit_id')} course_ids={course_ids}"
        )
        if len(examples) >= 5:
            break

    raise RuntimeError(
        "Snapshot references H5P content that is missing from local H5P storage. "
        f"Missing content_ids: {', '.join(missing_ids)}. "
        "Provide h5p_storage.tar.gz or re-import the missing H5P packages. "
        f"Examples: {'; '.join(examples)}"
    )


def _parse_missing_h5p_ids(error_text: str) -> list[str]:
    """Extract missing H5P content IDs from the consistency error message."""
    match = re.search(r"Missing content_ids:\s*([0-9,\s-]+)\.", error_text)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def _build_object_url(base_url: str, bucket: str, key: str) -> str:
    encoded_key = quote(key, safe="/")
    encoded_bucket = quote(bucket, safe="")
    return f"{base_url.rstrip('/')}/storage/v1/object/{encoded_bucket}/{encoded_key}"


def _fetch_storage_bucket_ids(dsn: str) -> list[str]:
    try:
        res = subprocess.run(
            ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-At", "-c", "select id from storage.buckets order by id"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        LOG.warning("Could not read bucket list from DB (storage.buckets): %s", exc)
        return []

    buckets = [line.strip() for line in (res.stdout or "").splitlines() if line.strip()]
    return buckets


def _collect_storage_objects(
    *,
    storage_root: Path,
    bucket_ids: Optional[set[str]],
) -> tuple[list[tuple[str, str, Path]], set[str], list[str]]:
    objects: list[tuple[str, str, Path]] = []
    buckets: set[str] = set()
    skipped: list[str] = []
    stripped_version_suffixes = 0

    def _looks_like_version_blob(part: str) -> bool:
        try:
            uuid.UUID(str(part))
            return True
        except (TypeError, ValueError, AttributeError):
            return False

    for file_path in sorted(storage_root.rglob("*")):
        if not file_path.is_file():
            continue
        parts = file_path.relative_to(storage_root).parts
        if len(parts) < 2:
            skipped.append(str(file_path))
            continue

        bucket_index: int | None = None
        if bucket_ids:
            for i, part in enumerate(parts[:-1]):
                if part in bucket_ids:
                    bucket_index = i
                    break
            if bucket_index is None:
                skipped.append(str(file_path))
                continue
        else:
            bucket_index = 0

        bucket = parts[bucket_index]
        key_parts = parts[bucket_index + 1 :]
        if not key_parts:
            skipped.append(str(file_path))
            continue
        if len(key_parts) >= 2 and _looks_like_version_blob(key_parts[-1]):
            key_parts = key_parts[:-1]
            stripped_version_suffixes += 1
        key = Path(*key_parts).as_posix()
        objects.append((bucket, key, file_path))
        buckets.add(bucket)

    if stripped_version_suffixes:
        LOG.info(
            "Detected %s versioned storage blobs in snapshot layout; stripped version suffix from import keys.",
            stripped_version_suffixes,
        )

    return objects, buckets, skipped


def _ensure_buckets(base_url: str, key: str, buckets: Iterable[str]) -> None:
    # Reuse existing bootstrap logic (idempotent).
    from backend.storage.bootstrap import ensure_buckets  # local import to keep module import cheap

    ensure_buckets(base_url, key, buckets)


def _sql_text_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sync_bucket_allowlists(dsn: str, buckets: Iterable[str]) -> None:
    target_buckets = sorted({bucket for bucket in buckets if bucket in LOCAL_BUCKET_ALLOWED_MIME_TYPES})
    if not target_buckets:
        return

    updates_sql = []
    for bucket in target_buckets:
        mime_literals = ", ".join(_sql_text_literal(mime) for mime in LOCAL_BUCKET_ALLOWED_MIME_TYPES[bucket])
        updates_sql.append(
            f"""
    update storage.buckets
       set allowed_mime_types = (
         select array_agg(distinct mime order by mime)
         from unnest(
           coalesce(allowed_mime_types, array[]::text[]) ||
           array[{mime_literals}]::text[]
         ) as mime
       )
     where id = {_sql_text_literal(bucket)};
"""
        )

    sql = """
do $$
begin
  if exists (
    select 1
      from information_schema.columns
     where table_schema = 'storage'
       and table_name = 'buckets'
       and column_name = 'allowed_mime_types'
  ) then
""" + "".join(updates_sql) + """
  end if;
end$$;
"""
    subprocess.run(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
    )
    LOG.info("Synced local storage bucket MIME allowlists for: %s", ", ".join(target_buckets))


def _upload_storage_objects(
    *,
    base_url: str,
    service_role_key: str,
    storage_root: Path,
    dsn: str,
    dry_run: bool,
) -> dict[str, int]:
    session = requests.Session()
    headers_base = {"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}", "x-upsert": "true"}

    bucket_ids = set(_fetch_storage_bucket_ids(dsn))
    objects, buckets_set, skipped_files = _collect_storage_objects(
        storage_root=storage_root, bucket_ids=bucket_ids or None
    )
    buckets = sorted(buckets_set)
    if not buckets:
        raise RuntimeError(f"Could not infer any buckets from extracted storage root: {storage_root}")

    LOG.info("Buckets in archive: %s", ", ".join(buckets))
    if skipped_files:
        LOG.warning("Skipping %s files that don't match bucket layout (see report).", len(skipped_files))
    if not dry_run:
        _ensure_buckets(base_url, service_role_key, buckets)
        _sync_bucket_allowlists(dsn, buckets)

    uploaded = 0
    failed = 0
    skipped = 0  # dry-run skips

    for bucket, key, file_path in objects:
        content_type = _guess_content_type(file_path, key)
        url = _build_object_url(base_url, bucket, key)
        if dry_run:
            skipped += 1
            continue
        with file_path.open("rb") as f:
            resp = session.post(
                url,
                headers={**headers_base, "Content-Type": content_type},
                data=f,
                timeout=(5, 120),
            )
        if resp.status_code >= 300:
            failed += 1
            body = (resp.text or "")[:500]
            LOG.error("Upload failed: bucket=%s key=%s status=%s body=%s", bucket, key, resp.status_code, body)
            continue
        uploaded += 1
        if uploaded % 200 == 0:
            LOG.info("Uploaded %s objects ...", uploaded)

    result = {"uploaded": uploaded, "failed": failed, "skipped": skipped, "db_buckets": len(bucket_ids)}
    if skipped_files:
        result["skipped_files"] = len(skipped_files)
    return result


def _guess_content_type(file_path: Path, key: str) -> str:
    # Some archive paths place the meaningful extension in an intermediate path
    # segment (for example, when uploads are keyed by digest directories).
    for candidate in [*Path(key).parts[::-1], file_path.name]:
        suffix = Path(candidate).suffix.lower()
        if suffix == ".sb3":
            return "application/x.scratch.sb3"
        if suffix == ".hex":
            return "application/x.makecode.hex"
        mime, _ = mimetypes.guess_type(candidate)
        if mime:
            return mime
    return "application/octet-stream"


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    dsn = resolve_dsn(args)
    ensure_local_dsn(dsn, allow_remote=args.allow_remote_dsn)

    snapshot_path = Path(args.snapshot)
    workdir = Path(args.workdir).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = workdir / f"run_{run_id}"
    extract_root = run_dir / "extracted"
    storage_extract_root = run_dir / "storage_extracted"
    run_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, object] = {
        "snapshot": str(snapshot_path),
        "dsn_redacted": _redact_pg_uri(dsn),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(args.dry_run),
        "skip_storage": bool(args.skip_storage),
        "skip_keycloak": bool(args.skip_keycloak),
        "no_reset": bool(args.no_reset),
        "allow_missing_h5p": bool(args.allow_missing_h5p),
    }

    try:
        files = resolve_snapshot_files(snapshot_path, extract_root)
        report["resolved_root"] = str(files.root)
        report["supabase_db_sql_gz"] = str(files.supabase_db_sql_gz)
        report["storage_buckets_tar_gz"] = str(files.storage_buckets_tar_gz)
        report["h5p_storage_tar_gz"] = str(files.h5p_storage_tar_gz) if files.h5p_storage_tar_gz else None
        report["h5p_storage_archive_present"] = bool(files.h5p_storage_tar_gz)
        report["keycloak_db_sql_gz"] = str(files.keycloak_db_sql_gz) if files.keycloak_db_sql_gz else None
        snapshot_migrations = extract_snapshot_migration_history(files.supabase_db_sql_gz)
        report["snapshot_migration_count"] = len(snapshot_migrations)
        report["snapshot_latest_migration"] = snapshot_migrations[-1].version if snapshot_migrations else None

        LOG.info("Preflight: checking DB connectivity ...")
        _psql_check(dsn)

        if not args.no_reset:
            report["dsn_is_superuser"] = ensure_superuser_for_reset(dsn)

        if not args.skip_storage:
            base_url = (args.supabase_url or os.getenv("SUPABASE_URL") or "").strip()
            key = (args.supabase_service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
            if not base_url or not key:
                raise RuntimeError(
                    "Storage import requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (env or flags)."
                )
            buckets, file_count, total_bytes = _inspect_storage_tar(files.storage_buckets_tar_gz)
            report["storage_buckets"] = buckets
            report["storage_file_count"] = file_count
            report["storage_total_bytes"] = total_bytes
            LOG.info("Preflight: storage tar has %s files (%.1f MB).", file_count, total_bytes / (1024 * 1024))

        if args.dry_run:
            if files.keycloak_db_sql_gz and not args.skip_keycloak:
                report["keycloak_would_restore"] = True
            LOG.info("Dry-run complete (no writes).")
            return 0

        if not args.no_reset:
            LOG.warning("Dropping non-system extensions + schemas before restore (destructive).")
            _reset_db_for_restore(dsn)

        _restore_db_sql_gz(files.supabase_db_sql_gz, dsn)
        _ensure_graphql_public_function(dsn)
        restore_target_owner = expected_local_migration_owner()
        _normalize_restore_target_ownership(dsn, restore_target_owner)
        sync_snapshot_migration_history(dsn, snapshot_migrations)
        report["restore_target_owner"] = restore_target_owner

        if files.h5p_storage_tar_gz is not None:
            restored_h5p_root = _restore_h5p_storage_tar(files.h5p_storage_tar_gz, LOCAL_H5P_STORAGE_ROOT)
            report["h5p_storage_restored_to"] = str(restored_h5p_root)
        try:
            h5p_consistency = _assert_snapshot_h5p_storage_complete(dsn, LOCAL_H5P_STORAGE_ROOT)
            report["h5p_storage_result"] = h5p_consistency
        except RuntimeError as exc:
            if not args.allow_missing_h5p:
                raise
            report["h5p_storage_result"] = {
                "expected_ids": [],
                "missing_ids": _parse_missing_h5p_ids(str(exc)),
            }
            report["h5p_storage_warning"] = str(exc)
            LOG.warning(
                "Continuing snapshot import despite missing H5P content because --allow-missing-h5p was set: %s",
                exc,
            )

        if files.keycloak_db_sql_gz and not args.skip_keycloak:
            _restore_keycloak_db_sql_gz(
                db_sql_gz=files.keycloak_db_sql_gz,
                keycloak_db_container=args.keycloak_db_container,
                keycloak_db_user=args.keycloak_db_user,
                keycloak_db_name=args.keycloak_db_name,
            )
            _localize_keycloak_for_local_web(
                keycloak_db_container=args.keycloak_db_container,
                keycloak_db_user=args.keycloak_db_user,
                keycloak_db_name=args.keycloak_db_name,
                realm=args.keycloak_realm,
                web_client_id=args.keycloak_web_client_id,
                app_base_url=args.keycloak_web_base,
            )
            _localize_keycloak_theme(
                keycloak_db_container=args.keycloak_db_container,
                keycloak_db_user=args.keycloak_db_user,
                keycloak_db_name=args.keycloak_db_name,
                realm=args.keycloak_realm,
                login_theme="gustav",
                account_theme="gustav",
                email_theme="gustav",
            )
            _sync_keycloak_admin_client_secret(
                keycloak_db_container=args.keycloak_db_container,
                keycloak_db_user=args.keycloak_db_user,
                keycloak_db_name=args.keycloak_db_name,
                admin_realm=args.keycloak_admin_realm,
                admin_client_id=args.keycloak_admin_client_id,
                admin_client_secret=args.keycloak_admin_client_secret,
            )
            _restart_container(args.keycloak_container)
            report["keycloak_restored"] = True
        elif files.keycloak_db_sql_gz is None:
            LOG.info("Snapshot contains no keycloak_db.sql.gz. Skipping Keycloak restore.")
            report["keycloak_restored"] = False

        if not args.skip_storage:
            base_url = (args.supabase_url or os.getenv("SUPABASE_URL") or "").strip()
            key = (args.supabase_service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
            assert base_url and key
            extracted = _extract_storage_tar(files.storage_buckets_tar_gz, storage_extract_root)
            storage_result = _upload_storage_objects(
                base_url=base_url,
                service_role_key=key,
                storage_root=extracted,
                dsn=dsn,
                dry_run=False,
            )
            report["storage_result"] = storage_result
            if int(storage_result.get("failed", 0)) > 0:
                raise RuntimeError(f"Storage upload had failures: {storage_result}")

        LOG.info("Snapshot import completed successfully.")
        return 0
    except Exception as exc:
        LOG.error("Snapshot import failed: %s", exc)
        report["error"] = str(exc)
        return 1
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report_path = run_dir / "report.json"
        try:
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            LOG.info("Wrote report: %s", report_path)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
