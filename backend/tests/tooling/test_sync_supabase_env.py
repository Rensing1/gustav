import os
import types
import builtins

import pytest


def _fake_completed(stdout_text: str) -> object:
    # Minimal stub mimicking subprocess.CompletedProcess for our script
    obj = types.SimpleNamespace()
    obj.stdout = stdout_text
    obj.stderr = ""
    obj.returncode = 0
    return obj


def test_parse_status_and_extract_fields(monkeypatch):
    # Simulate supabase status -o json output with preamble noise
    json_payload = (
        '{"SERVICE_ROLE_KEY":"s3cr3t","API_URL":"http://127.0.0.1:54321",'
        '"services":{"rest":{"status":"running"},"storage":{"status":"running"}}}'
    )
    stdout = f"some banner...\n{json_payload}\n"

    import subprocess as _subprocess

    def _run(cmd, check, capture_output, text):  # noqa: D401
        return _fake_completed(stdout)

    monkeypatch.setattr(_subprocess, "run", _run)

    import importlib
    mod = importlib.import_module("scripts.sync_supabase_env")
    data = mod._load_supabase_status()
    assert isinstance(data, dict)

    # New helper: extract URL + Service Role Key and health flags
    url, key, services_ok = mod._extract_core_fields(data)
    assert url == "http://127.0.0.1:54321"
    assert key == "s3cr3t"
    assert services_ok is True


def test_update_env_updates_or_appends(tmp_path):
    envfile = tmp_path / ".env"
    envfile.write_text("SUPABASE_URL=http://127.0.0.1:54321\nSUPABASE_SERVICE_ROLE_KEY=DUMMY_DO_NOT_USE\n")

    import importlib
    mod = importlib.import_module("scripts.sync_supabase_env")

    # Replace both values
    mod._update_env(envfile, "SUPABASE_URL", "http://127.0.0.1:12345")
    mod._update_env(envfile, "SUPABASE_SERVICE_ROLE_KEY", "real_key")

    text = envfile.read_text()
    assert "SUPABASE_URL=http://127.0.0.1:12345" in text
    assert "SUPABASE_SERVICE_ROLE_KEY=real_key" in text


def test_main_exits_when_services_not_running(monkeypatch, tmp_path):
    # Prepare a temp .env for the script to modify
    envfile = tmp_path / ".env"
    envfile.write_text("SUPABASE_URL=http://127.0.0.1:54321\nSUPABASE_SERVICE_ROLE_KEY=DUMMY_DO_NOT_USE\n")

    # Point script to our temp .env via chdir + monkeypatching ENV_PATH
    monkeypatch.chdir(tmp_path)

    # Simulate status where storage is not running
    json_payload = (
        '{"SERVICE_ROLE_KEY":"s3cr3t","API_URL":"http://127.0.0.1:54321",'
        '"services":{"rest":{"status":"running"},"storage":{"status":"stopped"}}}'
    )
    stdout = f"status...\n{json_payload}\n"

    import subprocess as _subprocess

    def _run(cmd, check, capture_output, text):  # noqa: D401
        return _fake_completed(stdout)

    monkeypatch.setattr(_subprocess, "run", _run)

    import importlib
    mod = importlib.import_module("scripts.sync_supabase_env")
    # For unhealthy services, main should abort with SystemExit
    with pytest.raises(SystemExit):
        mod.main()

