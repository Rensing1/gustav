"""Contract tests for FastAPI bearer JWT authentication."""

from __future__ import annotations

import base64
import time
import types
from pathlib import Path
import sys

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport
from jose import jwt


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.oidc import OIDCConfig  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")

TEST_ISSUER = "http://keycloak:8080/realms/gustav"
TEST_AUDIENCE = "gustav-web"
TEST_KID = "gustav-bearer-test-key"


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


_TEST_RSA_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PRIVATE_KEY_PEM = _TEST_RSA_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("ascii")

_public_numbers = _TEST_RSA_PRIVATE_KEY.public_key().public_numbers()
TEST_JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": TEST_KID,
            "n": _b64url_uint(_public_numbers.n),
            "e": _b64url_uint(_public_numbers.e),
        }
    ]
}


def _make_bearer_token(
    claim_overrides: dict[str, object] | None = None,
    *,
    audience: object = TEST_AUDIENCE,
) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": TEST_ISSUER,
        "aud": audience,
        "azp": TEST_AUDIENCE,
        "sub": "teacher-bearer",
        "exp": now + 300,
        "iat": now,
        "name": "Ada",
        "gustav_display_name": "Ada",
        "realm_access": {"roles": ["teacher"]},
    }
    if claim_overrides:
        claims.update(claim_overrides)
    return jwt.encode(claims, TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": TEST_KID, "typ": "JWT"})


def _configure_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = OIDCConfig(
        base_url="http://keycloak:8080",
        realm="gustav",
        client_id=TEST_AUDIENCE,
        redirect_uri="http://app.localhost/auth/callback",
    )
    monkeypatch.setattr(main, "OIDC_CFG", cfg)

    from identity_access import tokens as tokens_module  # type: ignore

    monkeypatch.setattr(tokens_module, "JWKS_CACHE", tokens_module.JWKSCache(ttl_seconds=0))
    monkeypatch.setattr(
        "requests.get",
        lambda url, timeout=5: types.SimpleNamespace(status_code=200, json=lambda: TEST_JWKS),
        raising=False,
    )


@pytest.mark.anyio
async def test_session_bootstrap_accepts_verified_bearer_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_jwks(monkeypatch)
    token = _make_bearer_token()

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/app/session-bootstrap",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["user"]["sub"] == "teacher-bearer"
    assert response.json()["user"]["role"] == "teacher"


@pytest.mark.anyio
async def test_api_me_accepts_access_token_style_bearer_with_azp(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_jwks(monkeypatch)
    token = _make_bearer_token(
        {
            "sub": "student-bearer",
            "realm_access": {"roles": ["student"]},
        },
        audience=["account"],
    )

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["sub"] == "student-bearer"
    assert response.json()["roles"] == ["student"]
    assert response.json()["name"] == "Ada"


@pytest.mark.anyio
async def test_teacher_home_rejects_invalid_bearer_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_jwks(monkeypatch)
    token = "broken.jwt.token"

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/teaching/views/teacher-home",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert response.json() == {"error": "unauthenticated"}
