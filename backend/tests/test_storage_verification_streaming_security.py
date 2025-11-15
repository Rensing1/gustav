"""
Verification streaming security — host allowlist.

Ensures that the streaming helper refuses URLs whose host does not match
the configured SUPABASE_URL host to prevent SSRF/host escape.
"""
from __future__ import annotations
import sys
import types
from hashlib import sha256 as _sha256

import backend.storage.verification as verification


def _install_fake_httpx(monkeypatch, *, status_code: int = 200, chunks: list[bytes] | None = None):
    """
    Replace `httpx` with a lightweight stub so tests don't hit the network.

    Returns a mutable state dict so tests can tweak status/chunks per call.
    """

    state: dict[str, object] = {"status_code": status_code, "chunks": list(chunks or [b"ok"])}

    class _Stream:
        def __init__(self) -> None:
            self.status_code = int(state["status_code"])
            self._chunks = list(state["chunks"])  # type: ignore[arg-type]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_bytes(self):
            for chunk in self._chunks:
                yield chunk

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url):
            return _Stream()

    fake_module = types.ModuleType("httpx")
    fake_module.Client = _Client  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "httpx", fake_module)
    return state


def test_stream_hash_from_url_rejects_untrusted_host(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")
    ok, sha, size, reason = verification._stream_hash_from_url("https://evil.local/obj")
    assert ok is False and sha is None and size is None
    assert reason == "untrusted_host"


def test_stream_hash_from_url_allows_supabase_public_host(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:443")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")

    state = _install_fake_httpx(monkeypatch, chunks=[b"hello"])

    ok, sha, size, reason = verification._stream_hash_from_url("https://app.localhost/storage/v1/object/foo")

    assert ok is True
    assert size == len(b"hello")
    assert sha == _sha256(b"hello").hexdigest()
    assert reason == "ok"


def test_stream_hash_from_url_rejects_redirects(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local")
    state = _install_fake_httpx(monkeypatch)
    state["status_code"] = 302

    ok, sha, size, reason = verification._stream_hash_from_url("https://supabase.local/storage/v1/object/foo")

    assert ok is False
    assert sha is None
    assert size is None
    assert reason == "redirect_detected"
