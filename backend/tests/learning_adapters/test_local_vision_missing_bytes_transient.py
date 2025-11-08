"""
Vision adapter — missing bytes must be transient with retry.

Scenario:
    STORAGE_VERIFY_ROOT is set but the referenced file is not present.
    Remote GET also fails. The adapter must NOT call the model without
    images and must raise VisionTransientError("image_unavailable").
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace
import sys

import pytest

pytest.importorskip("psycopg")


class _CapturingClient:
    def __init__(self) -> None:
        self.called = False

    def generate(self, *args, **kwargs):  # noqa: ANN001, ANN201
        self.called = True
        return {"response": "should not be used"}


def _install_fake_httpx_and_ollama(monkeypatch: pytest.MonkeyPatch, client: _CapturingClient) -> None:
    # Simulate remote fetch failure (e.g., 404 or network error)
    class _Resp:
        status_code = 404
        content = b""

    fake_httpx = SimpleNamespace(get=lambda url, headers=None, timeout=None: _Resp())
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    # Provide an ollama client stub to detect unintended calls
    fake_ollama = SimpleNamespace(Client=lambda base_url=None: client)
    monkeypatch.setitem(sys.modules, "ollama", fake_ollama)


def test_missing_local_and_remote_is_transient(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Local verify root is set, but file does not exist
    root = tmp_path / "storage"
    root.mkdir()
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
    # Remote access configured but fetch will 404 via fake httpx
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srk")

    client = _CapturingClient()
    _install_fake_httpx_and_ollama(monkeypatch, client)

    mod = importlib.import_module("backend.learning.adapters.local_vision")
    adapter = mod.build()  # type: ignore[attr-defined]

    submission = {"id": "deadbeef-dead-beef-missing-bytes", "kind": "file"}
    job_payload = {
        "mime_type": "image/png",
        "storage_key": "submissions/missing.png",
        "size_bytes": 123,
        "sha256": None,
    }

    with pytest.raises(Exception) as ei:
        adapter.extract(submission=submission, job_payload=job_payload)

    # Must be transient and not call the model at all
    from backend.learning.workers.process_learning_submission_jobs import VisionTransientError  # type: ignore

    assert isinstance(ei.value, VisionTransientError)
    assert "image_unavailable" in str(ei.value)
    assert client.called is False

