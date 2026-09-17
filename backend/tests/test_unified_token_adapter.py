"""The session adapter distinguishes invalid credentials from outages."""
from types import SimpleNamespace

import pytest

from backend.identity_access import oidc, tokens
from backend.identity_access.unified_sessions import SessionInvalid, SessionUnavailable

CFG = oidc.OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.localhost/auth/callback')


@pytest.mark.parametrize('status,code,error', [(400, 'invalid_grant', SessionInvalid), (429, 'slow_down', SessionUnavailable), (503, 'unavailable', SessionUnavailable)])
def test_refresh_classifies_errors(monkeypatch, status, code, error):
    monkeypatch.setattr(oidc, 'http_post', lambda *args, **kwargs: SimpleNamespace(status_code=status, json=lambda: {'error': code}))
    with pytest.raises(error):
        oidc.OIDCClient(CFG).refresh_tokens('synthetic')


def test_api_audience_cannot_be_replaced_by_authorized_party():
    with pytest.raises(tokens.BearerTokenVerificationError):
        tokens._validate_bearer_audience({'aud': ['account'], 'azp': 'gustav-web'}, 'gustav-api')


def test_unknown_signing_key_refreshes_cache_once(monkeypatch):
    cache = tokens.JWKSCache()
    calls = []
    def fetch(cfg):
        calls.append(1)
        return {'keys': [{'kid': 'old' if len(calls) == 1 else 'new', 'kty': 'RSA'}]}
    monkeypatch.setattr(cache, '_fetch', fetch)
    monkeypatch.setattr(tokens.jwt, 'get_unverified_header', lambda _: {'kid': 'new', 'alg': 'RS256'})
    monkeypatch.setattr(tokens.jwt, 'decode', lambda *a, **k: {'sub': 'synthetic', 'aud': 'gustav-api', 'exp': 4102444800})
    assert tokens.verify_bearer_token(token='synthetic', cfg=CFG, cache=cache)['sub'] == 'synthetic'
    assert len(calls) == 2


def test_malformed_bearer_is_invalid_even_during_jwks_outage(monkeypatch):
    def unavailable(_cfg, **_kwargs):
        raise AssertionError('Malformed credentials must be rejected before network I/O')
    cache = tokens.JWKSCache()
    monkeypatch.setattr(cache, 'get', unavailable)
    with pytest.raises(tokens.BearerTokenVerificationError):
        tokens.verify_bearer_token(token='session:obsolete-transport', cfg=CFG, cache=cache)


def test_server_logout_checks_the_confirmed_redirect_without_following_it(monkeypatch):
    from types import SimpleNamespace

    import backend.identity_access.oidc as module
    from backend.identity_access.oidc import OIDCClient, OIDCConfig
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=302, headers={'Location':'https://app.example/auth/logout/callback?state=expected'})
    monkeypatch.setattr(module.http, 'get', lambda *a, **kw: pytest.fail('Logout tokens must be sent in a POST body'))
    monkeypatch.setattr(module.http, 'post', get)
    client = OIDCClient(OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.example/auth/callback'))
    client.end_session(id_token='synthetic-id-token', callback='https://app.example/auth/logout/callback', state='expected')
    assert calls[0][1]['data']['id_token_hint'] == 'synthetic-id-token'
    assert calls[0][1]['timeout'] == 5
    assert calls[0][1]['allow_redirects'] is False


@pytest.mark.parametrize('status,location', [(200,''),(503,''),(302,'https://evil.example/?state=expected'),(302,'https://app.example/auth/logout/callback?state=wrong')])
def test_server_logout_rejects_unconfirmed_results(monkeypatch, status, location):
    from types import SimpleNamespace

    import backend.identity_access.oidc as module
    from backend.identity_access.oidc import OIDCClient, OIDCConfig
    from backend.identity_access.unified_sessions import SessionUnavailable
    monkeypatch.setattr(module.http, 'post', lambda *a, **kw: SimpleNamespace(status_code=status, headers={'Location':location}))
    client = OIDCClient(OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.example/auth/callback'))
    with pytest.raises(SessionUnavailable):
        client.end_session(id_token='synthetic-id-token', callback='https://app.example/auth/logout/callback', state='expected')
