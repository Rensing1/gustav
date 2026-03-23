from __future__ import annotations

import pytest

from identity_access.oidc import OIDCConfig
from identity_access.tokens import BearerTokenVerificationError, verify_bearer_token
from identity_access import tokens as tokens_mod


class FakeCache:
    def get(self, cfg):
        return {"keys": [{"kid": "kid1", "kty": "RSA"}]}


def test_verify_bearer_token_accepts_azp_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tokens_mod.jwt, "get_unverified_header", lambda _: {"kid": "kid1"})
    monkeypatch.setattr(
        tokens_mod.jwt,
        "decode",
        lambda token, key, algorithms=None, **kwargs: {
            "iss": "http://kc.example/realms/gustav",
            "aud": ["account"],
            "azp": "gustav-web",
            "sub": "teacher-1",
            "exp": 4102444800,
            "realm_access": {"roles": ["teacher"]},
        },
    )

    cfg = OIDCConfig(
        base_url="http://kc.example",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app/auth/callback",
    )
    claims = verify_bearer_token(token="dummy", cfg=cfg, cache=FakeCache())
    assert claims["sub"] == "teacher-1"


def test_verify_bearer_token_rejects_wrong_audience_and_azp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tokens_mod.jwt, "get_unverified_header", lambda _: {"kid": "kid1"})
    monkeypatch.setattr(
        tokens_mod.jwt,
        "decode",
        lambda token, key, algorithms=None, **kwargs: {
            "iss": "http://kc.example/realms/gustav",
            "aud": ["account"],
            "azp": "other-client",
            "sub": "teacher-1",
            "exp": 4102444800,
        },
    )

    cfg = OIDCConfig(
        base_url="http://kc.example",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app/auth/callback",
    )

    with pytest.raises(BearerTokenVerificationError):
        verify_bearer_token(token="dummy", cfg=cfg, cache=FakeCache())
