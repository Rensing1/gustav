"""Real signed JWTs protect the shared session across login and refresh."""
import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from backend.identity_access import tokens as token_module
from backend.identity_access.oidc import OIDCConfig
from backend.identity_access.session_tokens import session_values
from backend.identity_access.unified_sessions import SessionInvalid, SessionUnavailable


@pytest.fixture
def signed_tokens(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setattr(token_module, '_find_key', lambda jwks, kid: public if kid == 'test-key' else None)
    monkeypatch.setattr(token_module.JWKS_CACHE, 'get', lambda *a, **kw: {'keys': []})
    cfg = OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.example/auth/callback', 'https://id.example')
    def make(*, identity=None, access=None, lifetime=3600):
        common = {'sub': 'synthetic-student', 'iss': 'https://id.example/realms/gustav', 'iat': int(time.time()), 'exp': int(time.time())+300}
        id_claims = {**common, 'aud': 'gustav-web', 'nonce': 'nonce', 'gustav_display_name': 'Schüler', **(identity or {})}
        id_claims = {name: value for name, value in id_claims.items() if value is not None}
        access_claims = {**common, 'aud': 'gustav-api', 'realm_access': {'roles': ['student']}, **(access or {})}
        return {'id_token': jwt.encode(id_claims, key, algorithm='RS256', headers={'kid':'test-key'}), 'access_token': jwt.encode(access_claims, key, algorithm='RS256', headers={'kid':'test-key'}), 'refresh_token':'opaque-refresh', 'refresh_expires_in':lifetime}
    return cfg, make


def test_valid_login_uses_keycloak_lifetime_and_verified_roles(signed_tokens):
    cfg, make = signed_tokens
    result = session_values(make(lifetime=30*86400), cfg, nonce='nonce')
    assert result['roles'] == ['student']
    assert result['name'] == 'Schüler'
    assert abs(result['expires_at']-time.time()-30*86400) < 2


@pytest.mark.parametrize('identity,access', [
    ({'nonce':'wrong'}, {}), ({'iss':'https://evil.example'}, {}),
    ({'aud':'other'}, {}), ({'aud':None}, {}), ({'iat':None}, {}), ({'exp':1}, {}), ({'nbf':4102444800}, {}),
    ({'sub':'different'}, {}), ({}, {'aud':['account'], 'azp':'gustav-web'}),
    ({}, {'exp':1}), ({}, {'iss':'https://evil.example'}),
])
def test_login_rejects_invalid_claims(signed_tokens, identity, access):
    cfg, make = signed_tokens
    with pytest.raises(SessionInvalid):
        session_values(make(identity=identity, access=access), cfg, nonce='nonce')


def test_refresh_updates_roles_but_never_subject(signed_tokens):
    cfg, make = signed_tokens
    current = SimpleNamespace(sub='synthetic-student', name='Schüler', id_token='previous')
    assert session_values(make(access={'realm_access':{'roles':['teacher','irrelevant']}}), cfg, current)['roles'] == ['teacher']
    current.sub = 'different'
    with pytest.raises(SessionInvalid):
        session_values(make(), cfg, current)


def test_key_retrieval_outage_is_not_an_invalid_session(signed_tokens, monkeypatch):
    cfg, make = signed_tokens
    def fail(*args, **kwargs):
        raise token_module.IDTokenVerificationError('jwks_fetch_failed')
    monkeypatch.setattr(token_module.JWKS_CACHE, 'get', fail)
    with pytest.raises(SessionUnavailable):
        session_values(make(), cfg, nonce='nonce')


def test_invalid_signature_is_rejected(signed_tokens):
    cfg, make = signed_tokens
    value = make()
    parts = value['id_token'].split('.')
    parts[2] = ('A' if parts[2][0] != 'A' else 'B') + parts[2][1:]
    value['id_token'] = '.'.join(parts)
    with pytest.raises(SessionInvalid):
        session_values(value, cfg, nonce='nonce')
