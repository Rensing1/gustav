"""
Unit tests for the minimal OIDC client used to integrate Keycloak.

We validate that:
- The authorization URL is constructed correctly (realm path + required query params).
- The token exchange performs the expected POST to the token endpoint and returns tokens.
"""

from urllib.parse import urlparse, parse_qs
import types
import pytest


from pathlib import Path
import sys

# Import OIDC client from identity_access
REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_DIR = REPO_ROOT / "backend" / "identity_access"
sys.path.insert(0, str(IDENTITY_DIR))

from oidc import OIDCConfig, OIDCClient  # type: ignore  # noqa: E402


def test_build_authorization_url_contains_required_params():
    cfg = OIDCConfig(
        base_url="http://localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://testserver/auth/callback",
    )
    client = OIDCClient(cfg)
    url = client.build_authorization_url(state="abc123", code_challenge="xyz")

    parsed = urlparse(url)
    assert parsed.scheme in ("http", "https")
    assert parsed.netloc
    assert parsed.path.endswith("/realms/gustav/protocol/openid-connect/auth")

    qs = parse_qs(parsed.query)
    assert qs.get("response_type") == ["code"]
    assert qs.get("client_id") == ["gustav-web"]
    assert qs.get("redirect_uri") == ["http://testserver/auth/callback"]
    assert qs.get("scope") == ["openid"]
    assert qs.get("state") == ["abc123"]
    assert qs.get("code_challenge") == ["xyz"]
    assert qs.get("code_challenge_method") == ["S256"]


def test_exchange_code_for_tokens_success(monkeypatch: pytest.MonkeyPatch):
    cfg = OIDCConfig(
        base_url="http://localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://testserver/auth/callback",
    )
    client = OIDCClient(cfg)

    called = {}

    def fake_post(url: str, data: dict, headers: dict):
        called["url"] = url
        called["data"] = data
        called["headers"] = headers

        resp = types.SimpleNamespace()
        resp.status_code = 200
        def _json():
            return {"access_token": "at", "id_token": "it", "token_type": "Bearer"}
        resp.json = _json
        return resp

    import oidc as oidc_module  # type: ignore  # noqa: E402
    monkeypatch.setattr(oidc_module, "http_post", fake_post)

    tokens = client.exchange_code_for_tokens(code="abc", code_verifier="ver")

    assert called["url"].endswith("/realms/gustav/protocol/openid-connect/token")
    assert called["data"]["grant_type"] == "authorization_code"
    assert called["data"]["code"] == "abc"
    assert called["data"]["client_id"] == "gustav-web"
    assert called["data"]["redirect_uri"] == "http://testserver/auth/callback"
    assert called["data"]["code_verifier"] == "ver"
    assert tokens["access_token"] == "at"
    assert tokens["id_token"] == "it"


def test_exchange_code_for_tokens_failure(monkeypatch: pytest.MonkeyPatch):
    cfg = OIDCConfig(
        base_url="http://localhost:8080",
        realm="gustav",
        client_id="gustav-web",
        redirect_uri="http://testserver/auth/callback",
    )
    client = OIDCClient(cfg)

    def fake_post(url: str, data: dict, headers: dict):
        resp = types.SimpleNamespace()
        resp.status_code = 400
        def _json():
            return {"error": "invalid_grant"}
        resp.json = _json
        return resp

    import oidc as oidc_module  # type: ignore  # noqa: E402
    monkeypatch.setattr(oidc_module, "http_post", fake_post)

    with pytest.raises(ValueError):
        client.exchange_code_for_tokens(code="abc", code_verifier="ver")

