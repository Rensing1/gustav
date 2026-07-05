from __future__ import annotations

import pytest

from backend.identity_access.oidc import OIDCConfig
from backend.identity_access.tokens import (
    BearerTokenVerificationError,
    IDTokenVerificationError,
    verify_bearer_token,
)
from backend.identity_access import tokens as tokens_mod


class FakeCache:
    def get(self, cfg):
        return {"keys": [{"kid": "kid1", "kty": "RSA"}]}


class FailingCache:
    def get(self, cfg):
        raise IDTokenVerificationError("jwks_fetch_failed")


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


def test_verify_bearer_token_maps_jwks_fetch_failures_to_bearer_error() -> None:
    cfg = OIDCConfig(
        base_url="http://kc.example",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app/auth/callback",
    )

    with pytest.raises(BearerTokenVerificationError) as exc_info:
        verify_bearer_token(token="dummy", cfg=cfg, cache=FailingCache())

    assert exc_info.value.code == "jwks_fetch_failed"


def test_verify_bearer_token_maps_expired_claims_to_bearer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tokens_mod.jwt, "get_unverified_header", lambda _: {"kid": "kid1"})
    monkeypatch.setattr(
        tokens_mod.jwt,
        "decode",
        lambda token, key, algorithms=None, **kwargs: {
            "iss": "http://kc.example/realms/gustav",
            "aud": ["gustav-web"],
            "sub": "teacher-1",
            "exp": 1,
        },
    )

    cfg = OIDCConfig(
        base_url="http://kc.example",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://app/auth/callback",
    )

    with pytest.raises(BearerTokenVerificationError) as exc_info:
        verify_bearer_token(token="dummy", cfg=cfg, cache=FakeCache())

    assert exc_info.value.code == "invalid_bearer_token"
