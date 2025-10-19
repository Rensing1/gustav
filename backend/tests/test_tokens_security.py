"""
Security tests for token verification: enforce algorithm whitelist.

We assert that verify_id_token calls jwt.decode with algorithms=["RS256"]
regardless of JWKS 'alg' value.
"""

from __future__ import annotations

import types
import pytest

from identity_access.tokens import verify_id_token, IDTokenVerificationError
from identity_access import tokens as tokens_mod
from identity_access.oidc import OIDCConfig


def test_verify_enforces_rs256_alg(monkeypatch: pytest.MonkeyPatch):
    # Provide a minimal cache that returns a JWKS with any alg; we ignore it
    class FakeCache:
        def get(self, cfg):
            return {"keys": [{"kid": "kid1", "kty": "RSA"}]}

    # Ensure header returns a kid
    monkeypatch.setattr(tokens_mod.jwt, "get_unverified_header", lambda _: {"kid": "kid1"})

    captured = {}

    def fake_decode(token, key, algorithms=None, **kwargs):
        captured["algorithms"] = list(algorithms or [])
        # Raise to force verify_id_token to wrap into IDTokenVerificationError
        from jose.exceptions import JOSEError
        raise JOSEError("boom")

    monkeypatch.setattr(tokens_mod.jwt, "decode", fake_decode)

    cfg = OIDCConfig(base_url="http://kc:8080", realm="gustav", client_id="gustav-web", redirect_uri="http://app/auth/callback")

    with pytest.raises(IDTokenVerificationError):
        verify_id_token(id_token="dummy", cfg=cfg, cache=FakeCache())

    assert captured.get("algorithms") == ["RS256"], "Expected RS256-only enforcement"

