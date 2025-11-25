"""
Daily backup script for GUSTAV data stores.

Creates timestamped backups of the Supabase Postgres database (including auth),
the Keycloak database, and Supabase storage buckets, placing all artifacts in
`/backups/<timestamp>/`. Designed for cron execution inside the container.

Inputs (required via environment):
- DATABASE_URL: Postgres URI with sufficient privileges to dump Supabase DB.
- KC_DB_URL: Postgres URI for Keycloak DB (includes credentials).
- SUPABASE_STORAGE_ROOT: Filesystem root of Supabase storage buckets.
- BACKUP_DIR: Destination directory for backups (e.g., /backups).
- RETENTION_DAYS: Number of days to keep backups (default: 7).

Behavior:
- On each run: create timestamped directory, dump Supabase DB and Keycloak DB
  to gzip-compressed plain SQL, archive storage buckets to tar.gz, write a
  small manifest, then delete backup directories older than RETENTION_DAYS.
- Fails fast on missing configuration or command errors; exits non-zero when
  any step fails. Caller must ensure the cron user can read storage and write
  to BACKUP_DIR.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlsplit, urlunsplit


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


def _require_any_env(candidates: List[str]) -> str:
    for key in candidates:
        value = os.environ.get(key)
        if value:
            return value
    raise SystemExit(f"Missing required environment variable (tried): {', '.join(candidates)}")


def _run_pg_dump(uri: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pg_dump", "--format=plain", "--no-owner", uri]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed for {uri}: {proc.stderr.decode().strip()}")
    with gzip.open(dest, "wb") as gz:
        gz.write(proc.stdout)


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
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
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
        mtime = dt.datetime.fromtimestamp(entry.stat().st_mtime)
        if mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)


def _timestamp() -> str:
    return dt.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")


def _normalize_pg_uri(uri: str, user: str | None = None, password: str | None = None) -> str:
    # Accept JDBC-prefixed URLs (Keycloak) and inject credentials when missing.
    raw = uri
    if raw.startswith("jdbc:"):
        raw = raw.removeprefix("jdbc:")
    parts = urlsplit(raw)
    if (not parts.username) and user:
        netloc = parts.hostname or ""
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        auth = user
        if password:
            auth = f"{auth}:{password}"
        netloc = f"{auth}@{netloc}"
        parts = parts._replace(netloc=netloc)
    return urlunsplit(parts)


def main() -> int:
    """Entry point for cron: backs up Supabase DB, Keycloak DB, and storage buckets. Caller must have read access and write perms to BACKUP_DIR."""
    parser = argparse.ArgumentParser(description="Daily backup for Supabase DB, storage buckets, and Keycloak DB.")
    parser.add_argument("--once", action="store_true", help="Run once and exit (default behavior).")
    args = parser.parse_args()
    _ = args  # currently unused; reserved for future scheduling flags

    try:
        env_required = _require_env(["KC_DB_URL", "SUPABASE_STORAGE_ROOT", "BACKUP_DIR"])
        db_uri = _require_any_env(["BACKUP_DATABASE_URL", "DATABASE_URL"])
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
    kc_uri = _normalize_pg_uri(env_required["KC_DB_URL"], kc_user, kc_password)
    supabase_uri = _normalize_pg_uri(db_uri)

    now = dt.datetime.utcnow()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        _run_pg_dump(supabase_uri, target_dir / "supabase_db.sql.gz")
        _run_pg_dump(kc_uri, target_dir / "keycloak_db.sql.gz")
        _archive_storage(storage_root, target_dir / "storage_buckets.tar.gz")
        _write_manifest(
            target_dir,
            status="ok",
            extra={"supabase_db": "supabase_db.sql.gz", "keycloak_db": "keycloak_db.sql.gz", "storage": "storage_buckets.tar.gz"},
        )
        _cleanup_retention(backup_dir, retention_days, now)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"backup failed: {exc}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
