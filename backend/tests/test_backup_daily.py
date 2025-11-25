import gzip
import json
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


def _make_fake_pg_dump(tmp_path: Path, behavior: str = "ok") -> Path:
    """
    Create a fake pg_dump binary.

    behavior:
        - "ok": writes simple SQL to stdout and exits 0.
        - "fail": writes error to stderr and exits 1.
        - "hang": sleeps for HANG_SECONDS (default 5) without producing output.
    """
    script = tmp_path / "pg_dump"
    script.write_text(
        "#!/bin/sh\n"
        'echo "$@" >>"$TMP_PG_DUMP_ARGS"\n'
        'if [ "$1" = "--format=plain" ]; then\n'
        "  if [ \"${BEHAVIOR}\" = \"fail\" ]; then\n"
        "    echo \"pg_dump boom\" 1>&2\n"
        "    exit 1\n"
        "  elif [ \"${BEHAVIOR}\" = \"hang\" ]; then\n"
        "    sleep \"${HANG_SECONDS:-5}\"\n"
        "    exit 0\n"
        "  fi\n"
        "  echo \"-- SQL DUMP --\"; exit 0\n"
        "fi\n"
        "exit 1\n"
    )
    script.chmod(0o755)
    return script


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
            "SESSION_DATABASE_URL": supabase_db,
            "DATABASE_URL": supabase_db,
            "KC_DB_URL": keycloak_db,
            "BACKUP_DIR": str(backup_dir),
            "SUPABASE_STORAGE_ROOT": str(storage_root),
            "RETENTION_DAYS": "7",
        }
    )
    # Ensure no conflicting DSNs bleed in from the environment.
    env.pop("BACKUP_DATABASE_URL", None)
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


def test_backup_pg_dump_failure_writes_failed_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "backup_daily.py"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    backup_dir = tmp_path / "backups"
    (backup_dir / "old").mkdir(parents=True, exist_ok=True)

    args_log = tmp_path / "pg_args.log"
    fake_pg_dump = _make_fake_pg_dump(tmp_path, behavior="fail")
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH','')}")
    monkeypatch.setenv("TMP_PG_DUMP_ARGS", str(args_log))
    args_log.touch()
    env = os.environ.copy()
    env.update(
        {
            "BACKUP_DIR": str(backup_dir),
            "SUPABASE_STORAGE_ROOT": str(storage_root),
            "DATABASE_URL": "postgresql://user:secret@db/supabase",
            "KC_DB_URL": "postgresql://kc_user:kc_pass@kc-db/keycloak",
            "BEHAVIOR": "fail",
        }
    )
    result = subprocess.run(
        [sys.executable, str(script_path), "--once"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    manifests = list(backup_dir.glob("*/manifest.json"))
    assert manifests, "manifest should be written on failure"
    manifest = json.loads(manifests[0].read_text())
    assert manifest.get("status") == "failed"
    # Ensure pg_dump was invoked (arguments recorded)
    assert args_log.read_text().strip() != ""


def test_backup_missing_storage_root_marks_failed_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "backup_daily.py"
    backup_dir = tmp_path / "backups"
    # Create fake pg_dump that succeeds to reach storage step.
    args_log = tmp_path / "pg_args.log"
    _make_fake_pg_dump(tmp_path, behavior="ok")
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH','')}")
    monkeypatch.setenv("TMP_PG_DUMP_ARGS", str(args_log))
    env = os.environ.copy()
    env.update(
        {
            "BACKUP_DIR": str(backup_dir),
            "SUPABASE_STORAGE_ROOT": str(tmp_path / "missing-storage"),
            "DATABASE_URL": "postgresql://user:secret@db/supabase",
            "KC_DB_URL": "postgresql://kc_user:kc_pass@kc-db/keycloak",
            "BEHAVIOR": "ok",
        }
    )
    result = subprocess.run(
        [sys.executable, str(script_path), "--once"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    manifests = list(backup_dir.glob("*/manifest.json"))
    assert manifests, "manifest should be written on failure"
    manifest = json.loads(manifests[0].read_text())
    assert manifest.get("status") == "failed"


def test_backup_prefers_session_database_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "backup_daily.py"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    args_log = tmp_path / "pg_args.log"
    _make_fake_pg_dump(tmp_path, behavior="ok")
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH','')}")
    monkeypatch.setenv("TMP_PG_DUMP_ARGS", str(args_log))
    env = os.environ.copy()
    env.update(
        {
            "BACKUP_DIR": str(backup_dir),
            "SUPABASE_STORAGE_ROOT": str(storage_root),
            "SESSION_DATABASE_URL": "postgresql://session_user:pass@db/sessiondb",
            "DATABASE_URL": "postgresql://primary_user:pass@db/primarydb",
            "KC_DB_URL": "postgresql://kc_user:kc_pass@kc-db/keycloak",
            "BEHAVIOR": "ok",
        }
    )
    result = subprocess.run(
        [sys.executable, str(script_path), "--once"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # pg_dump called twice; check first recorded URI ends with session DB
    args_lines = args_log.read_text().strip().splitlines()
    assert any("sessiondb" in line for line in args_lines), f"args: {args_lines}"


def test_backup_pg_dump_timeout_marks_failed_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "backup_daily.py"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    args_log = tmp_path / "pg_args.log"
    _make_fake_pg_dump(tmp_path, behavior="hang")
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH','')}")
    monkeypatch.setenv("TMP_PG_DUMP_ARGS", str(args_log))
    env = os.environ.copy()
    env.update(
        {
            "BACKUP_DIR": str(backup_dir),
            "SUPABASE_STORAGE_ROOT": str(storage_root),
            "DATABASE_URL": "postgresql://user:secret@db/supabase",
            "KC_DB_URL": "postgresql://kc_user:kc_pass@kc-db/keycloak",
            "BEHAVIOR": "hang",
            "HANG_SECONDS": "5",
            "BACKUP_PG_TIMEOUT_SECONDS": "1",
        }
    )
    result = subprocess.run(
        [sys.executable, str(script_path), "--once"],
        env=env,
        capture_output=True,
        text=True,
        timeout=6,
    )
    assert result.returncode != 0
    manifests = list(backup_dir.glob("*/manifest.json"))
    assert manifests, "manifest should be written on timeout"
    manifest = json.loads(manifests[0].read_text())
    assert manifest.get("status") == "failed"
    assert "timeout" in manifest.get("error", "").lower()
