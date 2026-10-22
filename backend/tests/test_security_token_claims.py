"""Real signed JWKs exercise the library boundary rather than a decode mock."""
import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.identity_access.oidc import OIDCConfig
from backend.identity_access.tokens import (
    BearerTokenVerificationError,
    IDTokenVerificationError,
    verify_bearer_token,
    verify_id_token,
)


@pytest.fixture
def signed_identity():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    def b64(number):
        return base64.urlsafe_b64encode(number.to_bytes((number.bit_length()+7)//8, 'big')).decode().rstrip('=')
    key = {'kty': 'RSA', 'kid': 'test', 'n': b64(numbers.n), 'e': b64(numbers.e), 'alg': 'RS256'}
    class Cache:
        def get(self, *args, **kwargs):
            return {'keys': [key]}
    cfg = OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.example/callback', 'https://id.example')
    def sign(audience, **changes):
        claims = {'sub': 'synthetic', 'iss': 'https://id.example/realms/gustav',
                  'aud': audience, 'iat': int(time.time()), 'exp': int(time.time())+300, **changes}
        return jwt.encode(claims, private, algorithm='RS256', headers={'kid': 'test'})
    return cfg, Cache(), sign


@pytest.mark.parametrize('bearer', [False, True])
def test_real_jwk_signature_and_audience(signed_identity, bearer):
    cfg, cache, sign = signed_identity
    if bearer:
        assert verify_bearer_token(token=sign('gustav-api'), cfg=cfg, cache=cache)['sub'] == 'synthetic'
    else:
        assert verify_id_token(id_token=sign('gustav-web'), cfg=cfg, cache=cache)['sub'] == 'synthetic'


@pytest.mark.parametrize('claim,value', [('exp', float('nan')), ('exp', float('inf')), ('exp', True), ('exp', 10**400), ('iat', 10**400), ('nbf', 10**400), ('nbf', 'tomorrow'), ('iat', 'yesterday')])
@pytest.mark.parametrize('bearer', [False, True])
def test_invalid_temporal_types_fail_closed(signed_identity, claim, value, bearer):
    cfg, cache, sign = signed_identity
    with pytest.raises((BearerTokenVerificationError, IDTokenVerificationError)):
        if bearer:
            verify_bearer_token(token=sign('gustav-api', **{claim:value}), cfg=cfg, cache=cache)
        else:
            verify_id_token(id_token=sign('gustav-web', **{claim:value}), cfg=cfg, cache=cache)
