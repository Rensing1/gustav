"""
Verification streaming security — host allowlist.

Ensures that the streaming helper refuses URLs whose host does not match
the configured SUPABASE_URL host to prevent SSRF/host escape.
"""
from __future__ import annotations

import os

import backend.storage.verification as verification


def test_stream_hash_from_url_rejects_untrusted_host(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")
    ok, sha, size, reason = verification._stream_hash_from_url("https://evil.local/obj")
    assert ok is False and sha is None and size is None
    assert reason == "untrusted_host"

