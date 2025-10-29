"""Synchronize legacy placeholder SUBs to real Keycloak SUBs.

Why:
    During the legacy → Alpha2 migration, references to users (teacher, author,
    student) may be written as placeholders of the form ``legacy:<uuid>``. This
    utility replaces those placeholders with the real OIDC subject identifiers
    (Keycloak user IDs) so that Row Level Security (RLS) grants access to the
    correct rows when a user logs in.

Usage (CSV mapping):
    python -m backend.tools.sub_mapping_sync \
      --db-dsn postgresql://postgres:postgres@127.0.0.1:54322/postgres \
      --mapping-csv /path/to/map.csv

Where map.csv has a header row and two columns:
    legacy_id,sub
    017c5cb7-fd9a-4d7b-8d48-350996b10b2a,8f573bca-2bad-45d2-9f7e-b6b99c34ba6f

Notes:
    - Idempotent: running multiple times updates the same values without side
      effects.
    - Minimal scope: only updates known locations in public schema. Extend as
      needed if new user-referencing tables are introduced.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Tuple

import click

try:  # pragma: no cover - optional dependency for unit tests
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


def _ensure_psycopg() -> None:
    if psycopg is None:  # pragma: no cover - defensive guard in test envs
        raise click.ClickException("psycopg is required for sub-mapping sync tool")


def _load_csv_mapping(path: Path) -> list[tuple[str, str]]:
    """Load mapping from CSV with columns legacy_id,sub.

    Returns a list of (legacy_id, sub). Lines with missing/empty cells are
    ignored. The function is strict about column names to avoid accidental
    misalignment.
    """
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or set(h.strip() for h in reader.fieldnames) != {"legacy_id", "sub"}:
            raise click.ClickException("mapping CSV must have header: legacy_id,sub")
        for r in reader:
            legacy = (r.get("legacy_id") or "").strip()
            sub = (r.get("sub") or "").strip()
            if not legacy or not sub:
                continue
            rows.append((legacy, sub))
    return rows


def _apply_mapping(conn: "psycopg.Connection", pairs: Iterable[tuple[str, str]]) -> dict[str, int]:  # type: ignore[name-defined]
    """Apply mapping to all known user-reference columns in public schema.

    The updates are executed through a temp table to keep statements simple and
    efficient. Returns counts per table of rows affected for basic reporting.
    """
    counts = {"legacy_user_map": 0, "courses": 0, "units": 0, "course_memberships": 0, "learning_submissions": 0, "module_section_releases": 0}
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        # Use a temp table whose rows survive statements within this session.
        cur.execute("create temp table temp_kc_map(legacy_id uuid primary key, sub text) on commit preserve rows")
        cur.executemany("insert into temp_kc_map(legacy_id, sub) values (%s::uuid, %s)", list(pairs))
        cur.execute("update public.legacy_user_map m set sub = t.sub from temp_kc_map t where m.legacy_id = t.legacy_id")
        counts["legacy_user_map"] = cur.rowcount or 0
        cur.execute("update public.courses c set teacher_id = t.sub from temp_kc_map t where c.teacher_id = 'legacy:'||t.legacy_id::text")
        counts["courses"] = cur.rowcount or 0
        cur.execute("update public.units u set author_id = t.sub from temp_kc_map t where u.author_id = 'legacy:'||t.legacy_id::text")
        counts["units"] = cur.rowcount or 0
        cur.execute("update public.course_memberships cm set student_id = t.sub from temp_kc_map t where cm.student_id = 'legacy:'||t.legacy_id::text")
        counts["course_memberships"] = cur.rowcount or 0
        cur.execute("update public.learning_submissions s set student_sub = t.sub from temp_kc_map t where s.student_sub = 'legacy:'||t.legacy_id::text")
        counts["learning_submissions"] = cur.rowcount or 0
        cur.execute("update public.module_section_releases r set released_by = t.sub from temp_kc_map t where r.released_by = 'legacy:'||t.legacy_id::text")
        counts["module_section_releases"] = cur.rowcount or 0
    return counts


def _kc_email_mapping(*, legacy_dsn: str, base_url: str, host_header: str, realm: str, username: str, password: str, timeout: float = 5.0) -> List[Tuple[str, str]]:
    """Build (legacy_id, sub) pairs by resolving Keycloak IDs via user emails.

    Uses the legacy DB to fetch user emails and queries Keycloak's admin API for
    each email. This avoids a full realm user listing and works even without
    custom attributes.
    """
    # Import locally to avoid hard dependency at module import time (speeds tests).
    try:  # pragma: no cover - exercised in integration
        from backend.tools.legacy_user_import import fetch_legacy_users, KeycloakAdminClient  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise click.ClickException(f"Failed to import Keycloak helpers: {exc}")

    rows = fetch_legacy_users(legacy_dsn)
    client = KeycloakAdminClient.from_credentials(
        base_url=base_url,
        host_header=host_header,
        realm=realm,
        username=username,
        password=password,
        timeout=timeout,
    )
    pairs: List[Tuple[str, str]] = []
    for r in rows:
        sub = client.find_user_id(r.email)
        if sub:
            pairs.append((str(r.id), sub))
    return pairs


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--db-dsn", required=True, help="Service-role DSN for the Alpha2 database.")
@click.option("--mapping-csv", type=click.Path(path_type=Path), help="CSV file with columns legacy_id,sub")
@click.option("--from-keycloak", is_flag=True, help="Build mapping by querying Keycloak (email-based)")
@click.option("--legacy-dsn", required=False, help="Legacy DB DSN (used for --from-keycloak email mapping)")
@click.option("--kc-base-url", required=False, help="Keycloak base URL (admin) for --from-keycloak")
@click.option("--kc-host-header", required=False, help="Host header for Keycloak (e.g. id.localhost)")
@click.option("--realm", default="gustav", show_default=True, help="Keycloak realm for --from-keycloak")
@click.option("--kc-admin-user", required=False, help="Keycloak admin user for --from-keycloak")
@click.option("--kc-admin-pass", required=False, help="Keycloak admin password for --from-keycloak")
@click.option("--timeout", type=float, default=10.0, show_default=True, help="HTTP timeout for Keycloak calls")
def cli(
    db_dsn: str,
    mapping_csv: Path | None,
    from_keycloak: bool,
    legacy_dsn: str | None,
    kc_base_url: str | None,
    kc_host_header: str | None,
    realm: str,
    kc_admin_user: str | None,
    kc_admin_pass: str | None,
    timeout: float,
) -> None:
    """Replace legacy:<uuid> placeholders with real Keycloak SUBs.

    Callers should provide a service-role DSN so RLS does not interfere. At the
    moment, only CSV input is supported for testability; a Keycloak-backed mode
    can be added later using the admin client.
    """
    _ensure_psycopg()
    if from_keycloak:
        # Validate inputs for KC mode
        missing = [
            name
            for name, val in (
                ("--legacy-dsn", legacy_dsn),
                ("--kc-base-url", kc_base_url),
                ("--kc-host-header", kc_host_header),
                ("--kc-admin-user", kc_admin_user),
                ("--kc-admin-pass", kc_admin_pass),
            )
            if not val
        ]
        if missing:
            raise click.ClickException("Missing required options for --from-keycloak: " + ", ".join(missing))
        pairs = _kc_email_mapping(
            legacy_dsn=legacy_dsn or "",  # type: ignore[arg-type]
            base_url=kc_base_url or "",
            host_header=kc_host_header or "",
            realm=realm,
            username=kc_admin_user or "",
            password=kc_admin_pass or "",
            timeout=timeout,
        )
    else:
        if not mapping_csv:
            raise click.ClickException("Please provide --mapping-csv or --from-keycloak")
        pairs = _load_csv_mapping(mapping_csv)
    if not pairs:
        click.echo("No mappings found in CSV; nothing to do.")
        return
    with psycopg.connect(db_dsn, autocommit=True) as conn:  # type: ignore[arg-type]
        counts = _apply_mapping(conn, pairs)
    click.echo(
        "Updated legacy_user_map={legacy_user_map}, courses={courses}, units={units}, memberships={course_memberships}, submissions={learning_submissions}, releases={module_section_releases}".format(
            **counts
        )
    )


if __name__ == "__main__":  # pragma: no cover - manual entry
    cli()
