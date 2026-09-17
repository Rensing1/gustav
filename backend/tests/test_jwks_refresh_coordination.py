"""Untrusted JWT headers may not create unbounded identity-provider traffic."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from backend.identity_access import tokens
from backend.identity_access.oidc import OIDCConfig

CFG = OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.example/auth/callback')


@pytest.mark.parametrize('identity', [False, True])
def test_wrong_algorithm_is_rejected_without_reading_keys(monkeypatch, identity):
    cache = tokens.JWKSCache()
    calls = []
    monkeypatch.setattr(cache, '_fetch', lambda cfg: calls.append(1) or {'keys': []})
    token = jwt.encode({'exp': 4102444800}, 'synthetic', algorithm='HS256', headers={'kid': 'unknown'})
    with pytest.raises((tokens.IDTokenVerificationError, tokens.BearerTokenVerificationError)):
        if identity:
            tokens.verify_id_token(id_token=token, cfg=CFG, cache=cache)
        else:
            tokens.verify_bearer_token(token=token, cfg=CFG, cache=cache)
    assert calls == []


def test_unknown_key_wave_shares_one_forced_fetch(monkeypatch):
    cache = tokens.JWKSCache()
    calls = []
    def fetch(cfg):
        calls.append(1)
        time.sleep(0.02)
        return {'keys': [{'kid': 'known'}]}
    monkeypatch.setattr(cache, '_fetch', fetch)
    monkeypatch.setattr(tokens.jwt, 'get_unverified_header', lambda token: {'kid': token, 'alg': 'RS256'})
    cache.get(CFG)
    barrier = threading.Barrier(8)
    def check(index):
        barrier.wait(timeout=5)
        with pytest.raises(tokens.BearerTokenVerificationError):
            tokens.verify_bearer_token(token=f'unknown-{index}', cfg=CFG, cache=cache)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(check, range(8)))
    for index in range(8):
        with pytest.raises(tokens.BearerTokenVerificationError):
            tokens.verify_bearer_token(token=f'next-{index}', cfg=CFG, cache=cache)
    assert len(calls) == 2


def test_cached_keys_remain_available_during_forced_network_call(monkeypatch):
    cache = tokens.JWKSCache()
    monkeypatch.setattr(cache, '_fetch', lambda cfg: {'keys': [{'kid': 'known'}]})
    cached = cache.get(CFG)
    started, release = threading.Event(), threading.Event()
    def fetch(cfg):
        started.set()
        assert release.wait(timeout=5)
        return {'keys': [{'kid': 'known'}, {'kid': 'new'}]}
    monkeypatch.setattr(cache, '_fetch', fetch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        forced = pool.submit(cache.get, CFG, force=True)
        try:
            assert started.wait(timeout=2)
            assert pool.submit(cache.get, CFG).result(timeout=1) == cached
        finally:
            release.set()
            forced.result(timeout=2)


@pytest.mark.parametrize('warm_cache', [False, True])
def test_key_outage_is_shared_and_recoverable(monkeypatch, warm_cache):
    clock = [100.0]
    monkeypatch.setattr(tokens.time, 'monotonic', lambda: clock[0])
    cache = tokens.JWKSCache()
    calls = []
    healthy = [warm_cache]
    def fetch(cfg):
        calls.append(1)
        if not healthy[0]:
            raise tokens.IDTokenVerificationError('jwks_fetch_failed')
        return {'keys': [{'kid': 'known'}]}
    monkeypatch.setattr(cache, '_fetch', fetch)
    if warm_cache:
        cache.get(CFG)
        healthy[0] = False
    for _ in range(5):
        with pytest.raises(tokens.IDTokenVerificationError, match='jwks_fetch_failed'):
            cache.get(CFG, force=warm_cache)
    assert len(calls) == (2 if warm_cache else 1)
    if warm_cache:
        assert cache.get(CFG)['keys'][0]['kid'] == 'known'
    healthy[0] = True
    clock[0] += 6
    assert cache.get(CFG, force=warm_cache)['keys'][0]['kid'] == 'known'
    assert len(calls) == (3 if warm_cache else 2)


def test_newly_rotated_signed_key_recovers_after_bounded_cooldown(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(tokens.time, 'monotonic', lambda: clock[0])
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    from jose import jwk
    public = jwk.construct(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo), algorithm='RS256').to_dict()
    public['kid'] = 'new'
    now = int(time.time())
    token = jwt.encode({'sub': 'synthetic', 'aud': 'gustav-api', 'iss': 'http://keycloak:8080/realms/gustav', 'iat': now, 'exp': now+300}, pem, algorithm='RS256', headers={'kid': 'new'})
    cache = tokens.JWKSCache()
    keys = [{'kid': 'old'}]
    calls = []
    def fetch(cfg):
        calls.append(1)
        return {'keys': list(keys)}
    monkeypatch.setattr(cache, '_fetch', fetch)
    cache.get(CFG)
    cache.get(CFG, force=True)
    keys[:] = [public]
    with pytest.raises(tokens.BearerTokenVerificationError, match='jwks_refresh_deferred'):
        tokens.verify_bearer_token(token=token, cfg=CFG, cache=cache)
    assert len(calls) == 2
    clock[0] += 6
    assert tokens.verify_bearer_token(token=token, cfg=CFG, cache=cache)['sub'] == 'synthetic'
    assert len(calls) == 3
