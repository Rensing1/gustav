"""
Daily backup script for GUSTAV data stores.

Creates timestamped backups of the Supabase Postgres database (including auth),
the Keycloak database, and Supabase storage buckets, placing all artifacts in
`/backups/<timestamp>/`. Designed for cron execution inside the container.

Inputs (required via environment):
- SESSION_DATABASE_URL (preferred) or BACKUP_DATABASE_URL or DATABASE_URL: Postgres URI with sufficient privileges to dump Supabase DB (auth schema included).
- KC_DB_URL: Postgres URI for Keycloak DB (includes credentials).
- SUPABASE_STORAGE_ROOT: Filesystem root of Supabase storage buckets.
- BACKUP_DIR: Destination directory for backups (e.g., /backups).
- RETENTION_DAYS: Number of days to keep backups (default: 7).
- BACKUP_PG_TIMEOUT_SECONDS: Optional pg_dump timeout (default: 300 seconds).

Behavior:
- On each run: create timestamped directory, dump Supabase DB and Keycloak DB
  to gzip-compressed plain SQL, archive storage buckets to tar.gz, write a
  manifest (ok/failed), then delete backup directories older than RETENTION_DAYS.
- Fails fast on missing configuration or command errors; exits non-zero when
  any step fails. Credentials are passed via env (PGPASSWORD) so passwords do
  not appear in process lists or logs. Caller must ensure the cron user can
  read storage and write to BACKUP_DIR.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlsplit, urlunsplit
import gzip
import time


def _require_env(keys: List[str]) -> Dict[str, str]:
    env: Dict[str, str] = {}
    missing = []
    for key in keys:
        value = os.environ.get(key)
        if not value:
            missing.append(key)
        else:
            env[key] = value
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    return env


def _run_pg_dump(uri: str, dest: Path, *, timeout: int, env: Dict[str, str]) -> None:
    """
    Stream pg_dump output directly into gzip file without buffering full dump in memory.

    Secrets:
        Passwords are provided via env (PGPASSWORD) instead of embedding them in the URI
        to avoid leaking them in process lists or logs.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pg_dump", "--format=plain", "--no-owner", uri]
    proc_env = os.environ.copy()
    proc_env.update(env)
    start = time.monotonic()
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=proc_env,
    ) as proc:
        with gzip.open(dest, "wb") as gz:
            while True:
                if proc.stdout is None:
                    break
                chunk = proc.stdout.read(8192)
                if chunk:
                    gz.write(chunk)
                if chunk == b"":
                    break
                if time.monotonic() - start > timeout:
                    proc.kill()
                    proc.wait()
                    raise RuntimeError(f"pg_dump timeout after {timeout}s for {uri}")
        stderr = proc.stderr.read() if proc.stderr else b""
        ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"pg_dump failed for {uri}: {stderr.decode().strip()}")


def _archive_storage(storage_root: Path, dest: Path) -> None:
    if not storage_root.exists():
        raise RuntimeError(f"storage root not found: {storage_root}")
    if not storage_root.is_dir():
        raise RuntimeError(f"storage root is not a directory: {storage_root}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    import tarfile

    with tarfile.open(dest, "w:gz") as tar:
        for child in storage_root.iterdir():
            # Add children with relative names so restored paths match bucket names.
            tar.add(child, arcname=child.name)


def _write_manifest(target_dir: Path, status: str, extra: Dict[str, str]) -> None:
    manifest = {
        "status": status,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        **extra,
    }
    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))


def _cleanup_retention(backup_dir: Path, retention_days: int, now: dt.datetime) -> None:
    if not backup_dir.exists():
        return
    cutoff = now - dt.timedelta(days=retention_days)
    for entry in backup_dir.iterdir():
        if not entry.is_dir():
            continue
        mtime = dt.datetime.fromtimestamp(entry.stat().st_mtime, tz=dt.timezone.utc)
        if mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H%M%S")


def _normalize_pg_uri(uri: str, user: str | None = None, password: str | None = None) -> Tuple[str, Dict[str, str]]:
    """
    Normalize a Postgres URI:
    - Accept JDBC prefixes.
    - Ensure username is present (from URI or explicit user arg).
    - Strip password from URI; provide it via env (PGPASSWORD) to avoid leaks.
    """
    raw = uri
    if raw.startswith("jdbc:"):
        raw = raw.removeprefix("jdbc:")
    parts = urlsplit(raw)
    username = parts.username or user or ""
    pwd = parts.password or password
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = host
    if username:
        netloc = f"{username}@{host}"
    sanitized = urlunsplit(parts._replace(netloc=netloc))
    env = {"PGPASSWORD": pwd} if pwd else {}
    return sanitized, env


def _redact_uri(uri: str) -> str:
    """Remove password from URI for logs."""
    parts = urlsplit(uri)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    username = parts.username or ""
    netloc = host
    if username:
        netloc = f"{username}@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _select_supabase_uri() -> str:
    """
    DSN precedence:
    1. SESSION_DATABASE_URL (preferred for backup to include auth schema)
    2. BACKUP_DATABASE_URL (explicit override)
    3. DATABASE_URL (fallback)
    """
    for key in ("SESSION_DATABASE_URL", "BACKUP_DATABASE_URL", "DATABASE_URL"):
        val = os.environ.get(key)
        if val:
            return val
    raise SystemExit("Missing required environment variable (tried): SESSION_DATABASE_URL, BACKUP_DATABASE_URL, DATABASE_URL")


def main() -> int:
    """Entry point for cron: backs up Supabase DB, Keycloak DB, and storage buckets. Caller must have read access and write perms to BACKUP_DIR."""
    parser = argparse.ArgumentParser(description="Daily backup for Supabase DB, storage buckets, and Keycloak DB.")
    parser.add_argument("--once", action="store_true", help="Run once and exit (default behavior).")
    args = parser.parse_args()
    _ = args  # currently unused; reserved for future scheduling flags

    try:
        env_required = _require_env(["KC_DB_URL", "SUPABASE_STORAGE_ROOT", "BACKUP_DIR"])
        db_uri = _select_supabase_uri()
    except SystemExit as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1

    retention_days = int(os.environ.get("RETENTION_DAYS", "7"))
    backup_dir = Path(env_required["BACKUP_DIR"])
    storage_root = Path(env_required["SUPABASE_STORAGE_ROOT"])
    stamp = _timestamp()
    target_dir = backup_dir / stamp
    kc_user = os.environ.get("KC_DB_USERNAME")
    kc_password = os.environ.get("KC_DB_PASSWORD")
    kc_uri, kc_env = _normalize_pg_uri(env_required["KC_DB_URL"], kc_user, kc_password)
    supabase_uri, supabase_env = _normalize_pg_uri(db_uri)

    pg_timeout = int(os.environ.get("BACKUP_PG_TIMEOUT_SECONDS", "300"))
    now = dt.datetime.now(dt.timezone.utc)
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        _run_pg_dump(_redact_uri(supabase_uri), target_dir / "supabase_db.sql.gz", timeout=pg_timeout, env=supabase_env)
        _run_pg_dump(_redact_uri(kc_uri), target_dir / "keycloak_db.sql.gz", timeout=pg_timeout, env=kc_env)
        _archive_storage(storage_root, target_dir / "storage_buckets.tar.gz")
        _write_manifest(
            target_dir,
            status="ok",
            extra={"supabase_db": "supabase_db.sql.gz", "keycloak_db": "keycloak_db.sql.gz", "storage": "storage_buckets.tar.gz"},
        )
        _cleanup_retention(backup_dir, retention_days, now)
    except Exception as exc:  # noqa: BLE001
        _write_manifest(
            target_dir,
            status="failed",
            extra={"error": str(exc)},
        )
        sys.stderr.write(f"backup failed: {exc}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
