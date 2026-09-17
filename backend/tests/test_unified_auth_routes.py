"""Browser binding, continuation and logout with the real local flow store."""
import importlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.identity_access.oidc import OIDCClient, OIDCConfig
from backend.tests.test_unified_sessions import record
from backend.tests.test_unified_sessions import repo as session_repo

auth_router = importlib.import_module("backend.web.routes.auth").auth_router
repo = session_repo

pytestmark = pytest.mark.db_write


@pytest.fixture
def client(repo, monkeypatch):
    monkeypatch.setenv('APP_CSRF_TOKEN_SECRET', 'synthetic-test-secret-with-at-least-32-chars')
    cfg = OIDCConfig('http://keycloak:8080', 'gustav', 'gustav-web', 'https://app.localhost/auth/callback')
    app = FastAPI()
    app.state.runtime = SimpleNamespace(session_repository=repo, oidc_config=cfg, oidc_client=OIDCClient(cfg), session_store=repo)
    monkeypatch.setattr(app.state.runtime.oidc_client, "end_session", lambda **kwargs: None)
    app.include_router(auth_router)
    with TestClient(app, base_url='https://app.localhost', follow_redirects=False) as client:
        yield client


def test_continuation_attempt_is_bounded_across_callback(client):
    first = client.get('/auth/continue')
    assert first.status_code == 302
    params = parse_qs(urlsplit(first.headers['location']).query)
    assert params['prompt'] == ['none']
    callback = client.get('/auth/callback', params={'state': params['state'][0], 'error': 'login_required'})
    assert callback.status_code == 302
    assert 'reason=session-expired' not in callback.headers['location']
    second = client.get('/auth/continue')
    assert second.headers['location'].startswith('/?')


def test_invalid_callback_does_not_consume_another_flow(client):
    first = client.get('/auth/login')
    state = parse_qs(urlsplit(first.headers['location']).query)['state'][0]
    assert client.get('/auth/callback?state=invalid&code=invalid').status_code == 400
    assert client.app.state.runtime.session_repository.consume_flow(state, client.cookies.get('gustav_auth_browser')) is not None


def test_logout_get_is_confirmation_and_post_requires_origin(client, repo):
    rec = record(repo, expired=False)
    client.cookies.set('gustav_session', rec.session_id)
    assert client.get('/auth/logout').status_code == 200
    assert repo.get(rec.session_id)
    assert client.post('/auth/logout').status_code == 403
    assert repo.get(rec.session_id)
    response = client.post('/auth/logout', headers={'origin': 'https://app.localhost'})
    assert response.status_code == 302
    assert repo.get(rec.session_id) is None
    assert client.get('/auth/continue').headers['location'].startswith('/?')


def test_registration_direct_and_safe_return(client):
    result = client.get('/auth/register', params={'redirect': '//evil.example'})
    assert '/registrations?' in result.headers['location']
    assert 'evil.example' not in result.headers['location']


@pytest.mark.parametrize('path,part', [('/auth/login','/auth?'),('/auth/register','/registrations?'),('/auth/password','kc_action=UPDATE_PASSWORD'),('/auth/forgot','/forgot-credentials?')])
def test_oidc_entries_use_pkce_nonce_configured_callback_and_private_headers(client, path, part):
    response = client.get(path, params={'redirect':'/learning?module=test'})
    assert response.status_code == 302
    assert part in response.headers['location']
    assert response.headers['cache-control'] == 'private, no-store'
    params = parse_qs(urlsplit(response.headers['location']).query)
    assert params['code_challenge_method'] == ['S256']
    assert params['nonce'][0]
    assert params['redirect_uri'] == ['https://app.localhost/auth/callback']
    browser = client.cookies.get('gustav_auth_browser')
    flow = client.app.state.runtime.session_repository.consume_flow(params['state'][0], browser)
    assert OIDCClient.code_challenge_s256(flow.code_verifier) == params['code_challenge'][0]
    assert flow.redirect == '/learning?module=test'


@pytest.mark.parametrize('target', ['//evil.example', 'https://evil.example', '/a/../b', '/%2f%2fevil.example', '/\\evil.example', '/x#fragment'])
def test_unsafe_return_targets_are_never_persisted(client, target):
    response = client.get('/auth/login', params={'redirect':target})
    params = parse_qs(urlsplit(response.headers['location']).query)
    flow = client.app.state.runtime.session_repository.consume_flow(params['state'][0], client.cookies.get('gustav_auth_browser'))
    assert flow.redirect is None


@pytest.mark.parametrize('headers', [{}, {'origin':'null'}, {'origin':'https://evil.example','referer':'https://app.localhost/'}, {'origin':'http://app.localhost'}, {'origin':'https://app.localhost:444'}])
def test_logout_rejects_missing_or_foreign_provenance(client, headers):
    assert client.post('/auth/logout', headers=headers).status_code == 403


def test_logout_callback_is_browser_bound_and_single_use(client):
    response = client.post('/auth/logout', headers={'referer':'https://app.localhost/profile'})
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    assert client.get('/auth/logout/callback', params={'state':'other'}).status_code == 400
    assert client.get('/auth/logout/callback', params={'state':state}).headers['location'] == '/auth/logout/success'
    assert client.get('/auth/logout/callback', params={'state':state}).status_code == 400


def test_callback_infrastructure_failure_preserves_other_flows(client, monkeypatch):
    from backend.identity_access.unified_sessions import SessionUnavailable
    first = client.get('/auth/login')
    second = client.get('/auth/login')
    state = parse_qs(urlsplit(first.headers['location']).query)['state'][0]
    def unavailable(**kwargs):
        raise SessionUnavailable()
    monkeypatch.setattr(client.app.state.runtime.oidc_client, 'exchange_code_for_tokens', unavailable)
    assert client.get('/auth/callback', params={'state':state,'code':'synthetic'}).status_code == 503
    other = parse_qs(urlsplit(second.headers['location']).query)['state'][0]
    assert client.app.state.runtime.session_repository.consume_flow(other, client.cookies.get('gustav_auth_browser')) is not None


def test_ambiguous_callback_is_rejected_without_consuming_valid_flow(client):
    response = client.get('/auth/login')
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    assert client.get('/auth/callback', params={'state':state,'code':'synthetic','error':'login_required'}).status_code == 400
    assert client.app.state.runtime.session_repository.consume_flow(state, client.cookies.get('gustav_auth_browser')) is not None


def test_browser_auth_errors_go_to_a_safe_frontend_message(client):
    response = client.get('/auth/callback?code=invalid', headers={'accept':'text/html'})
    assert response.status_code == 302
    assert response.headers['location'] == '/auth/problem?reason=invalid_code_or_state'
    assert response.headers['referrer-policy'] == 'no-referrer'


@pytest.mark.parametrize('origin', ['https://app.localhost/path', 'https://app.localhost?query', 'https://app.localhost#fragment'])
def test_origin_header_requires_a_bare_origin(client, origin):
    assert client.post('/auth/logout', headers={'origin':origin}).status_code == 403


def test_failed_password_reset_does_not_forward_email_to_problem_page(client, monkeypatch):
    def unavailable(**kwargs):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(client.app.state.runtime.session_repository, 'create_flow', unavailable)
    response = client.get('/auth/forgot?login_hint=student@example.com', headers={'accept':'text/html'})
    assert response.headers['location'] == '/auth/problem?reason=auth_unavailable'


def test_logout_keeps_all_tokens_server_side(client, repo, monkeypatch):
    rec = record(repo, expired=False)
    client.cookies.set('gustav_session', rec.session_id)
    calls = []
    monkeypatch.setattr(client.app.state.runtime.oidc_client, 'end_session', lambda **kwargs: calls.append(kwargs), raising=False)
    response = client.post('/auth/logout', headers={'origin':'https://app.localhost'})
    assert response.status_code == 302
    assert rec.id_token not in response.headers['location']
    assert 'id_token_hint' not in response.headers['location']
    assert calls[0]['id_token'] == rec.id_token
    assert repo.get(rec.session_id) is None


def test_failed_idp_logout_preserves_local_revocation_and_never_claims_success(client, repo, monkeypatch):
    rec = record(repo, expired=False)
    client.cookies.set('gustav_session', rec.session_id)
    def fail(**kwargs):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(client.app.state.runtime.oidc_client, 'end_session', fail, raising=False)
    response = client.post('/auth/logout', headers={'origin':'https://app.localhost', 'accept':'text/html'})
    assert response.headers['location'] == '/auth/problem?reason=local_logout_only'
    assert repo.get(rec.session_id) is None
    assert client.get('/auth/continue').headers['location'].startswith('/?')
