"""
OIDC client hardening tests.

Focus:
- http_post enforces a timeout for IdP calls
"""

from __future__ import annotations

import types

from identity_access.oidc import http_post


def test_http_post_sets_timeout(monkeypatch):
    called = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        called["url"] = url
        called["data"] = data
        called["headers"] = headers
        called["timeout"] = timeout
        return types.SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    # Patch the requests alias used in oidc module
    monkeypatch.setattr("identity_access.oidc.http.post", fake_post, raising=False)

    resp = http_post("http://idp/token", {"a": "b"}, {"h": "v"})
    assert resp.status_code == 200
    assert called.get("timeout") == 5

