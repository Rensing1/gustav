"""
Storage bootstrap — ensure buckets exist (TDD).

Why:
    New environments should work without manual bucket creation. This test
    drives a small bootstrap that creates missing buckets using Supabase's
    REST API when AUTO_CREATE_STORAGE_BUCKETS=true.

Scope:
    - Unit-style: monkeypatch requests.get/post to avoid network calls.
    - Verifies: when materials exists and submissions is missing, bootstrap
      creates submissions only.
"""
from __future__ import annotations

import os
import types

import pytest
import logging


@pytest.mark.anyio
async def test_bootstrap_creates_missing_learning_bucket(monkeypatch):
    # Arrange env
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "materials")
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")

    calls: list[tuple[str, str]] = []  # (method, url)

    def fake_get(url: str, headers: dict[str, str]):
        calls.append(("GET", url))
        # Simulate existing buckets: only materials exists
        class _Resp:
            status_code = 200

            def json(self):
                return [{"id": "materials", "name": "materials"}]

        return _Resp()

    def fake_post(url: str, headers: dict[str, str], json: dict):
        calls.append(("POST", url))
        # Validate payload
        assert json.get("name") == "submissions"
        assert json.get("public") is False

        class _Resp:
            status_code = 200

            def json(self):
                return {"id": "submissions", "name": "submissions"}

        return _Resp()

    import backend.storage.bootstrap as bootstrap  # type: ignore

    monkeypatch.setattr(bootstrap, "requests", types.SimpleNamespace(get=fake_get, post=fake_post))

    # Act
    created = bootstrap.ensure_buckets_from_env()

    # Assert
    assert created is True  # work was attempted
    assert ("GET", "http://local.test:54321/storage/v1/bucket") in calls
    assert ("POST", "http://local.test:54321/storage/v1/bucket") in calls


@pytest.mark.anyio
async def test_bootstrap_logs_when_create_fails(monkeypatch, caplog):
    """Logs a warning with status code when create returns non-2xx (e.g., 409)."""
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "materials")
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")

    # One bucket exists; creation of the second fails with 409
    def fake_get(url: str, headers: dict[str, str]):
        class _Resp:
            status_code = 200

            def json(self):
                return [{"id": "materials", "name": "materials"}]

        return _Resp()

    def fake_post(url: str, headers: dict[str, str], json: dict):
        class _Resp:
            status_code = 409

            def json(self):
                return {"message": "bucket already exists or conflict"}

            text = "conflict"

        return _Resp()

    import backend.storage.bootstrap as bootstrap  # type: ignore

    monkeypatch.setattr(bootstrap, "requests", types.SimpleNamespace(get=fake_get, post=fake_post))

    caplog.set_level(logging.DEBUG, logger="gustav.storage")
    bootstrap.ensure_buckets_from_env()

    # Expect a warning mentioning create failure and status code
    msgs = "\n".join(rec.message for rec in caplog.records)
    assert "create bucket" in msgs and "status=409" in msgs


@pytest.mark.anyio
async def test_bootstrap_warns_when_bucket_missing_after_create(monkeypatch, caplog):
    """Warns when API created but subsequent list still does not show the bucket."""
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "materials")
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")

    calls: list[str] = []

    def fake_get(url: str, headers: dict[str, str]):
        calls.append("GET")
        # Always report only materials; simulate propagation failure
        class _Resp:
            status_code = 200

            def json(self):
                return [{"id": "materials", "name": "materials"}]

        return _Resp()

    def fake_post(url: str, headers: dict[str, str], json: dict):
        calls.append("POST")
        class _Resp:
            status_code = 200

            def json(self):
                return {"id": "submissions", "name": "submissions"}

            text = "ok"

        return _Resp()

    import backend.storage.bootstrap as bootstrap  # type: ignore

    monkeypatch.setattr(bootstrap, "requests", types.SimpleNamespace(get=fake_get, post=fake_post))

    caplog.set_level(logging.DEBUG, logger="gustav.storage")
    bootstrap.ensure_buckets_from_env()

    msgs = "\n".join(rec.message for rec in caplog.records)
    # Should have attempted POST and then warned about missing bucket
    assert "POST /storage/v1/bucket" in msgs
    assert "still missing after create attempt" in msgs
