"""OIDC callback origins come from configuration, never the request Host."""
from urllib.parse import parse_qs, urlsplit

from backend.identity_access.oidc import OIDCClient, OIDCConfig


def test_authorization_uses_configured_callback():
    cfg = OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.example/auth/callback')
    url = OIDCClient(cfg).build_authorization_url(state='state', code_challenge='pkce', nonce='nonce')
    assert parse_qs(urlsplit(url).query)['redirect_uri'] == [cfg.redirect_uri]
