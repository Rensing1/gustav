"""Real PostgreSQL regression tests for shared sessions and refresh races."""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import psycopg
import pytest

from backend.identity_access.unified_sessions import SessionService, SessionUnavailable
from backend.identity_access.unified_store import UnifiedSessionRepository

pytestmark = pytest.mark.db_write


@pytest.fixture
def repo():
    dsn = os.environ.get("SESSION_TEST_DSN")
    if not dsn:
        pytest.skip("local PostgreSQL is required")
    store = UnifiedSessionRepository(dsn)
    created = []
    original = store.create
    def create(**kwargs):
        record = original(**kwargs)
        created.append(record.session_id)
        return record
    store.create = create
    yield store
    for sid in created:
        store.delete(sid)


def record(repo, expired=True):
    return repo.create(sub="synthetic-student", roles=["student"], name="Test", id_token="synthetic-id",
                       access_token="synthetic-access", refresh_token="synthetic-refresh",
                       access_expires_at=int(time.time()) + (-10 if expired else 300),
                       expires_at=int(time.time()) + 3600)


def service(repo, refresh):
    return SessionService(repo, SimpleNamespace(refresh_tokens=refresh), lambda tokens, current: {
        "sub": current.sub, "roles": ["student"], "name": "Test",
        "access_token": "fresh-access", "refresh_token": "fresh-refresh", "id_token": "fresh-id",
        "access_expires_at": int(time.time()) + 300, "expires_at": int(time.time()) + 3600,
    })


def test_transient_refresh_preserves_session(repo):
    rec = record(repo)
    def fail(_):
        raise SessionUnavailable()
    with pytest.raises(SessionUnavailable):
        service(repo, fail).get(rec.session_id)
    assert repo.get(rec.session_id) is not None


def test_parallel_refresh_is_shared_across_service_instances(repo):
    rec = record(repo)
    calls = []
    barrier = threading.Barrier(3)
    def refresh(_):
        calls.append(1)
        time.sleep(0.15)
        return {}
    def read(_):
        barrier.wait()
        return service(repo, refresh).get(rec.session_id)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(read, range(3)))
    assert len(calls) == 1
    assert all(r.access_token == "fresh-access" for r in results)


def test_logout_during_refresh_cannot_resurrect_session(repo):
    rec = record(repo)
    def refresh(_):
        repo.delete(rec.session_id)
        return {}
    assert service(repo, refresh).get(rec.session_id) is None
    assert repo.get(rec.session_id) is None


def test_raw_cookie_is_not_stored(repo):
    rec = record(repo, expired=False)
    with psycopg.connect(repo.dsn) as conn:
        assert conn.execute("select count(*) from public.app_sessions where session_id=%s", (rec.session_id,)).fetchone()[0] == 0
    assert repo.get(rec.session_id).sub == "synthetic-student"


def test_flow_requires_same_browser_and_is_single_use(repo):
    flow = repo.create_flow(browser="browser-one", mode="login", redirect="/learning", code_verifier="pkce", nonce="nonce")
    assert repo.consume_flow(flow.state, "browser-two") is None
    assert repo.consume_flow(flow.state, "browser-one").nonce == "nonce"
    assert repo.consume_flow(flow.state, "browser-one") is None


def test_invalid_grant_revokes_session(repo):
    from backend.identity_access.unified_sessions import SessionInvalid
    rec = record(repo)
    def invalid(_):
        raise SessionInvalid()
    assert service(repo, invalid).get(rec.session_id) is None
    assert repo.get(rec.session_id) is None


def test_cooldown_prevents_an_outage_request_wave(repo):
    rec = record(repo)
    calls = []
    def unavailable(_):
        calls.append(1)
        raise SessionUnavailable()
    resolver = service(repo, unavailable)
    for _ in range(3):
        with pytest.raises(SessionUnavailable):
            resolver.get(rec.session_id)
    assert calls == [1]


def test_expired_lease_can_be_reclaimed_and_old_owner_cannot_overwrite(repo):
    rec = record(repo)
    first = repo.reserve_refresh(rec.session_id, 0)
    with psycopg.connect(repo.dsn) as conn:
        conn.execute("update public.app_sessions set refresh_locked_until=now()-interval '1 second' where sub=%s and session_id=%s", (rec.sub, __import__('hashlib').sha256(rec.session_id.encode()).hexdigest()))
    fresh = service(repo, lambda _: {}).get(rec.session_id)
    assert fresh.refresh_version > first
    assert repo.finish_refresh(rec.session_id, first, {
        'sub': rec.sub, 'roles': ['teacher'], 'name': 'stale', 'id_token': 'stale',
        'access_token': 'stale', 'refresh_token': 'stale', 'access_expires_at': time.time()+300, 'expires_at': time.time()+3600,
    }) is False
    assert repo.get(rec.session_id).access_token == 'fresh-access'


def test_only_three_parallel_flows_are_retained(repo):
    flows = [repo.create_flow(browser='bounded-browser', mode='login', redirect='/', code_verifier='pkce', nonce=str(i)) for i in range(4)]
    assert repo.consume_flow(flows[0].state, 'bounded-browser') is None
    assert all(repo.consume_flow(flow.state, 'bounded-browser') is not None for flow in flows[1:])


def test_logout_during_failed_early_refresh_does_not_return_revoked_identity(repo):
    rec = record(repo, expired=False)
    with psycopg.connect(repo.dsn) as conn:
        conn.execute("update public.app_sessions set access_expires_at=now()+interval '20 seconds' where session_id=%s", (__import__('hashlib').sha256(rec.session_id.encode()).hexdigest(),))
    def refresh(_):
        repo.delete(rec.session_id)
        raise SessionUnavailable()
    assert service(repo, refresh).get(rec.session_id) is None


def test_feature_cleanup_removes_only_owned_shared_sessions(repo):
    from backend.tools.feature_acceptance import _delete_run_sessions
    owned = record(repo)
    foreign = repo.create(sub='unrelated-synthetic-user', roles=['student'], name='Test', id_token='id', access_token='access', refresh_token='refresh', access_expires_at=time.time()+300, expires_at=time.time()+3600)
    _delete_run_sessions(repo.dsn, {owned.sub})
    assert repo.get(owned.session_id) is None
    assert repo.get(foreign.session_id) is not None


def _process_refresh_read(dsn, sid, barrier, calls, results):
    """Independent processes coordinate exclusively through PostgreSQL."""
    repository = UnifiedSessionRepository(dsn)
    def refresh(_):
        with calls.get_lock():
            calls.value += 1
        time.sleep(0.2)
        return {}
    barrier.wait(timeout=10)
    try:
        resolved = service(repository, refresh).get(sid)
        results.put(resolved.access_token if resolved else None)
    except Exception:
        results.put('failed')


def test_refresh_is_shared_across_independent_backend_processes(repo):
    import multiprocessing
    ctx = multiprocessing.get_context('spawn')
    rec = record(repo)
    barrier, calls, results = ctx.Barrier(3), ctx.Value('i', 0), ctx.Queue()
    processes = [ctx.Process(target=_process_refresh_read, args=(repo.dsn, rec.session_id, barrier, calls, results)) for _ in range(3)]
    try:
        for process in processes:
            process.start()
        assert [results.get(timeout=15) for _ in processes] == ['fresh-access'] * 3
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        assert calls.value == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)


@pytest.mark.parametrize('age_days', [2, 6, 29])
def test_no_independent_one_day_expiry_when_provider_session_is_valid(repo, monkeypatch, age_days):
    """Controlled time advances within the provider-confirmed remember-me lifetime."""
    now = time.time()
    # The token must also be expired for PostgreSQL's atomic renewal check.
    rec = repo.create(sub='synthetic-student', roles=['student'], name='Test', id_token='id', access_token='access', refresh_token='refresh', access_expires_at=now-10, expires_at=now+30*86400)
    monkeypatch.setattr(time, 'time', lambda: now + age_days*86400)
    assert service(repo, lambda _: {}).get(rec.session_id) is not None


def test_expired_unclaimed_lease_can_finish_without_losing_rotated_tokens(repo):
    from backend.identity_access.unified_store import digest
    rec = record(repo)
    version = repo.reserve_refresh(rec.session_id, rec.refresh_version)
    with psycopg.connect(repo.dsn) as conn:
        conn.execute("update public.app_sessions set refresh_locked_until=now()-interval '1 second' where session_id=%s", (digest(rec.session_id),))
    values = service(repo, lambda _: {}).validate_tokens({}, rec)
    assert repo.finish_refresh(rec.session_id, version, values)
    assert repo.get(rec.session_id).refresh_token == 'fresh-refresh'


def test_late_invalid_grant_does_not_reject_a_newer_session(repo):
    from backend.identity_access.unified_sessions import SessionInvalid
    from backend.identity_access.unified_store import digest
    rec = record(repo)
    def late_failure(_):
        with repo.connect() as conn:
            conn.execute("update public.app_sessions set refresh_locked_until=now()-interval '1 second' where session_id=%s", (digest(rec.session_id),))
        current = repo.get(rec.session_id)
        version = repo.reserve_refresh(rec.session_id, current.refresh_version)
        values = service(repo, None).validate_tokens({}, current)
        assert repo.finish_refresh(rec.session_id, version, values)
        raise SessionInvalid()
    result = service(repo, late_failure).get(rec.session_id)
    assert result is not None
    assert result.access_token == "fresh-access"


def test_auth_tables_are_restricted_to_server_roles(repo):
    for role in ('anon', 'authenticated', 'gustav_limited'):
        for table in ('app_sessions', 'auth_flows'):
            with repo.connect() as conn:
                conn.execute(f'set local role {role}')
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(f'select * from public.{table} limit 1')
    with repo.connect() as conn:
        conn.execute('set local role service_role')
        conn.execute('select state_hash from public.auth_flows limit 1')
        conn.execute('select session_id from public.app_sessions limit 1')


def test_legacy_bff_session_table_is_retired(repo):
    with repo.connect() as conn:
        assert conn.execute("select to_regclass('public.bff_sessions') as relation").fetchone()['relation'] is None


@pytest.mark.parametrize('past_old_expiry', [False, True])
def test_reader_during_refresh_keeps_the_completed_session(repo, monkeypatch, past_old_expiry):
    """Force read-before-finish, resume-after-finish with real committed DB writes."""
    rec = record(repo)
    owner = repo.reserve_refresh(rec.session_id, rec.refresh_version)
    original_get = repo.get
    stale = original_get(rec.session_id)
    resumed_at = stale.expires_at + 1 if past_old_expiry else time.time()
    values = service(repo, None).validate_tokens({}, stale)
    values.update(access_expires_at=resumed_at + 300, expires_at=resumed_at + 3600)
    assert repo.finish_refresh(rec.session_id, owner, values)

    reads = iter([stale])
    monkeypatch.setattr(repo, 'get', lambda sid: next(reads, None) or original_get(sid))
    monkeypatch.setattr(time, 'time', lambda: resumed_at)
    attempts = []
    def refresh(token):
        from backend.identity_access.unified_sessions import SessionInvalid
        attempts.append(token)
        raise SessionInvalid()
    result = service(repo, refresh).get(rec.session_id)
    assert result is not None
    assert result.refresh_token == 'fresh-refresh'
    assert attempts == []
    assert original_get(rec.session_id) is not None


def test_fresh_access_token_cannot_be_reserved_for_refresh(repo):
    rec = record(repo, expired=False)
    assert repo.reserve_refresh(rec.session_id, rec.refresh_version) is None


def test_expired_session_is_removed_without_refresh(repo):
    from backend.identity_access.unified_store import digest
    rec = record(repo)
    with repo.connect() as conn:
        conn.execute("update public.app_sessions set expires_at=now()-interval '1 second' where session_id=%s", (digest(rec.session_id),))
    assert service(repo, lambda _: pytest.fail('Expired sessions must not refresh')).get(rec.session_id) is None
    assert repo.get(rec.session_id) is None


def claimed_flow(repo, browser):
    flow = repo.create_flow(browser=browser, mode='login', redirect='/learning', code_verifier='test', nonce='test')
    assert repo.consume_flow(flow.state, browser)
    return flow


def test_logout_prevents_completion_of_already_claimed_flow(repo):
    flow = claimed_flow(repo, 'revoked-browser')
    repo.revoke_browser(None, 'revoked-browser')
    values = service(repo, None).validate_tokens({}, SimpleNamespace(sub='synthetic-student'))
    assert repo.complete_flow(flow.state, 'revoked-browser', values) is None


@pytest.mark.parametrize('browser_cookie', ['response-browser', None, 'renewed-browser-cookie'])
def test_logout_revokes_completed_callback_even_before_cookie_delivery(repo, browser_cookie):
    old_flow = claimed_flow(repo, 'response-browser')
    values = service(repo, None).validate_tokens({}, SimpleNamespace(sub='synthetic-student'))
    old = repo.complete_flow(old_flow.state, 'response-browser', values)
    flow = claimed_flow(repo, 'response-browser')
    pending = repo.complete_flow(flow.state, 'response-browser', values, old.session_id)
    assert repo.get(old.session_id) is None
    try:
        repo.revoke_browser(old.session_id, browser_cookie)
        assert repo.get(pending.session_id) is None
    finally:
        repo.delete(old.session_id)
        repo.delete(pending.session_id)


def test_logout_leaves_other_browsers_and_allows_new_explicit_flow(repo):
    values = service(repo, None).validate_tokens({}, SimpleNamespace(sub='synthetic-student'))
    foreign_flow = claimed_flow(repo, 'other-browser')
    foreign = repo.complete_flow(foreign_flow.state, 'other-browser', values)
    fresh = None
    try:
        repo.revoke_browser(None, 'local-browser')
        assert repo.get(foreign.session_id)
        new_flow = claimed_flow(repo, 'local-browser')
        fresh = repo.complete_flow(new_flow.state, 'local-browser', values)
        assert fresh is not None
        assert repo.complete_flow(new_flow.state, 'local-browser', values) is None
    finally:
        repo.delete(foreign.session_id)
        if fresh:
            repo.delete(fresh.session_id)


def test_completion_requires_claim_and_same_browser(repo):
    flow = repo.create_flow(browser='owner-browser', mode='login', redirect='/', code_verifier='test', nonce='test')
    values = service(repo, None).validate_tokens({}, SimpleNamespace(sub='synthetic-student'))
    assert repo.complete_flow(flow.state, 'owner-browser', values) is None
    assert repo.consume_flow(flow.state, 'owner-browser')
    assert repo.complete_flow(flow.state, 'foreign-browser', values) is None


def test_expiry_reader_waits_for_active_refresh_and_uses_extended_session(repo, monkeypatch):
    from backend.identity_access.unified_store import digest
    rec = record(repo)
    version = repo.reserve_refresh(rec.session_id, rec.refresh_version)
    with repo.connect() as conn:
        conn.execute('update public.app_sessions set expires_at=now()-interval \'1 second\' where session_id=%s', (digest(rec.session_id),))
    values = service(repo, None).validate_tokens({}, rec)
    def complete(_seconds):
        assert repo.finish_refresh(rec.session_id, version, values)
    monkeypatch.setattr(time, 'sleep', complete)
    result = service(repo, None).get(rec.session_id)
    assert result is not None
    assert result.access_token == 'fresh-access'


def test_expiry_during_stalled_refresh_returns_503_then_expires_after_lease(repo, monkeypatch):
    from backend.identity_access.unified_store import digest
    rec = record(repo)
    repo.reserve_refresh(rec.session_id, rec.refresh_version)
    with repo.connect() as conn:
        conn.execute('update public.app_sessions set expires_at=now()-interval \'1 second\' where session_id=%s', (digest(rec.session_id),))
    clock = [0.0]
    monkeypatch.setattr(time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0]+1))
    with pytest.raises(SessionUnavailable):
        service(repo, None).get(rec.session_id)
    assert repo.get(rec.session_id)
    with repo.connect() as conn:
        conn.execute('update public.app_sessions set refresh_locked_until=now()-interval \'1 second\' where session_id=%s', (digest(rec.session_id),))
    assert service(repo, None).get(rec.session_id) is None


def test_concurrent_callback_commit_and_logout_never_leave_usable_credentials(repo):
    values = service(repo, None).validate_tokens({}, SimpleNamespace(sub='synthetic-student'))
    for index in range(6):
        browser = f'commit-logout-race-{index}'
        first = claimed_flow(repo, browser)
        old = repo.complete_flow(first.state, browser, values)
        flow = claimed_flow(repo, browser)
        barrier = threading.Barrier(2)
        def complete():
            barrier.wait(timeout=5)
            return repo.complete_flow(flow.state, browser, values, old.session_id)
        def logout():
            barrier.wait(timeout=5)
            repo.revoke_browser(old.session_id, browser)
        result = None
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                completed, revoked = pool.submit(complete), pool.submit(logout)
                result = completed.result(timeout=5)
                revoked.result(timeout=5)
            assert repo.get(old.session_id) is None
            assert result is None or repo.get(result.session_id) is None
        finally:
            repo.delete(old.session_id)
            if result:
                repo.delete(result.session_id)


def test_replaced_cookie_cannot_be_restored_by_its_old_refresh(repo):
    from backend.identity_access.unified_store import digest
    rec = record(repo)
    version = repo.reserve_refresh(rec.session_id, rec.refresh_version)
    flow = claimed_flow(repo, 'replacement-browser')
    values = service(repo, None).validate_tokens({}, rec)
    replacement = repo.complete_flow(flow.state, 'replacement-browser', values, rec.session_id)
    try:
        assert repo.get(rec.session_id) is None
        assert not repo.finish_refresh(rec.session_id, version, values)
        with repo.connect() as conn:
            row = conn.execute('select access_token,refresh_token,id_token from public.app_sessions where session_id=%s', (digest(rec.session_id),)).fetchone()
        assert row == dict(access_token=None, refresh_token=None, id_token=None)
    finally:
        repo.delete(replacement.session_id)
