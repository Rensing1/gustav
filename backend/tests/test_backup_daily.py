import gzip
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest


def _require_cmd(cmd: str) -> None:
    if shutil.which(cmd) is None:
        pytest.skip(f"{cmd} not available in PATH")


def _replace_db_name(db_url: str, db_name: str) -> str:
    parts = urlsplit(db_url)
    return urlunsplit(parts._replace(path="/" + db_name))


def _psql(uri: str, sql: str) -> None:
    result = subprocess.run(
        ["psql", uri, "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"psql failed: {result.stderr.strip()}")


def _prepare_test_db(admin_url: str, db_name: str, table_name: str) -> str:
    db_url = _replace_db_name(admin_url, db_name)
    _psql(admin_url, f'DROP DATABASE IF EXISTS "{db_name}"')
    _psql(admin_url, f'CREATE DATABASE "{db_name}"')
    _psql(db_url, f'CREATE TABLE IF NOT EXISTS "{table_name}" (id serial PRIMARY KEY, name text)')
    return db_url


def _read_gzip_text(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return handle.read()


@pytest.mark.integration
def test_backup_happy_path_and_retention(tmp_path: Path) -> None:
    _require_cmd("psql")
    _require_cmd("pg_dump")
    _require_cmd("tar")

    admin_url = os.environ.get("TEST_ADMIN_DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    # Smoke-check connectivity early to avoid hanging on pg_dump.
    _psql(admin_url, "SELECT 1")

    supabase_db = _prepare_test_db(admin_url, "backup_supabase_test", "demo_supabase")
    keycloak_db = _prepare_test_db(admin_url, "backup_keycloak_test", "demo_keycloak")

    storage_root = tmp_path / "storage"
    (storage_root / "materials").mkdir(parents=True, exist_ok=True)
    (storage_root / "submissions").mkdir(parents=True, exist_ok=True)
    (storage_root / "materials" / "hello.txt").write_text("hi")
    (storage_root / "submissions" / "image.png").write_bytes(b"\x89PNG\r\n")

    backup_dir = tmp_path / "backups"
    old_dir = backup_dir / "2000-01-01_000000"
    old_dir.mkdir(parents=True, exist_ok=True)
    (old_dir / "old.txt").write_text("old")
    os.utime(old_dir, (0, 0))

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "backup_daily.py"
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": supabase_db,
            "KC_DB_URL": keycloak_db,
            "BACKUP_DIR": str(backup_dir),
            "SUPABASE_STORAGE_ROOT": str(storage_root),
            "RETENTION_DAYS": "7",
        }
    )
    result = subprocess.run(
        [sys.executable, str(script_path), "--once"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert not old_dir.exists()
    backups = sorted(backup_dir.iterdir())
    assert backups, f"no backups created, stdout: {result.stdout}, stderr: {result.stderr}"
    latest = backups[-1]

    supabase_dump = latest / "supabase_db.sql.gz"
    keycloak_dump = latest / "keycloak_db.sql.gz"
    storage_tar = latest / "storage_buckets.tar.gz"
    manifest = latest / "manifest.json"

    for path in (supabase_dump, keycloak_dump, storage_tar, manifest):
        assert path.exists(), f"missing {path.name}"

    supabase_sql = _read_gzip_text(supabase_dump)
    keycloak_sql = _read_gzip_text(keycloak_dump)
    assert "demo_supabase" in supabase_sql
    assert "demo_keycloak" in keycloak_sql

    with tarfile.open(storage_tar, "r:gz") as tar_handle:
        names = tar_handle.getnames()
    assert "materials/hello.txt" in names
    assert "submissions/image.png" in names


def test_backup_requires_env(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "backup_daily.py"
    env = {"BACKUP_DIR": str(tmp_path / "backups")}
    result = subprocess.run(
        [sys.executable, str(script_path), "--once"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr or "KC_DB_URL" in result.stderr
