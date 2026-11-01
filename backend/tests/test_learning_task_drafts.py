"""Contract-first checks for private, mutable task drafts against real PostgreSQL."""
import os
from uuid import uuid4

import psycopg
import pytest

from backend.tests.test_learning_api_contract import _client, _prepare_learning_fixture, main

pytestmark = [pytest.mark.anyio('asyncio'), pytest.mark.db_write]


def endpoint(f):
    return f'/api/learning/courses/{f.course_id}/tasks/{f.task["id"]}/draft'


async def test_roundtrip_empty_unicode_last_write_and_no_submission(monkeypatch):
    f = await _prepare_learning_fixture(monkeypatch)
    async with await _client() as c:
        c.cookies.set('gustav_session', f.student_session_id)
        assert (await c.get(endpoint(f))).status_code == 204
        for text in ['  Grüße\n\n```python\nx = 1\n```\n', '🦉' * 65536, 'second tab', '']:
            saved = await c.put(endpoint(f), json={'text_body': text})
            assert saved.status_code == 200, saved.text
            assert saved.json()['text_body'] == text
            assert saved.json()['updated_at']
            loaded = await c.get(endpoint(f))
            assert loaded.json() == saved.json()
            assert loaded.headers['cache-control'] == 'private, no-store'
        assert (await c.put(endpoint(f), json={'text_body': 'x' * 65537})).status_code == 400
        assert (await c.put(endpoint(f), json={'text_body': None})).status_code == 400
        assert (await c.put(endpoint(f), json={'text_body': '', 'student_sub': 'foreign'})).status_code == 400
        history = await c.get(endpoint(f).replace('/draft', '/submissions'))
        assert history.json() == []


@pytest.mark.parametrize('visible,member', [(False, True), (True, False)])
async def test_inaccessible_tasks_hide_drafts(monkeypatch, visible, member):
    f = await _prepare_learning_fixture(monkeypatch, visible=visible, add_member=member)
    async with await _client() as c:
        c.cookies.set('gustav_session', f.student_session_id)
        assert (await c.get(endpoint(f))).status_code == 404
        assert (await c.put(endpoint(f), json={'text_body': 'secret'})).status_code == 404


async def test_identity_role_and_csrf(monkeypatch):
    f = await _prepare_learning_fixture(monkeypatch)
    async with await _client() as c:
        assert (await c.get(endpoint(f))).status_code == 401
        c.cookies.set('gustav_session', f.teacher_session_id)
        assert (await c.get(endpoint(f))).status_code == 403
        c.cookies.set('gustav_session', f.student_session_id)
        assert (await c.put(endpoint(f), json={'text_body': 'private'}, headers={'Origin': 'https://foreign.example'})).status_code == 403
        assert (await c.put(endpoint(f), json={'text_body': 'private'})).status_code == 200
        outsider = main.RUNTIME.session_store.create(sub=str(uuid4()), name='Student', roles=['student'])
        c.cookies.set('gustav_session', outsider.session_id)
        assert (await c.get(endpoint(f))).status_code == 404


@pytest.mark.parametrize('removed', ['task', 'membership', 'course'])
async def test_rls_and_cascades(monkeypatch, removed):
    f = await _prepare_learning_fixture(monkeypatch)
    async with await _client() as c:
        c.cookies.set('gustav_session', f.student_session_id)
        assert (await c.put(endpoint(f), json={'text_body': 'private'})).status_code == 200
    with psycopg.connect(os.environ['RLS_TEST_DSN']) as conn:
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, true)", (str(uuid4()),))
            cur.execute('select text_body from public.learning_task_drafts where course_id=%s', (f.course_id,))
            assert cur.fetchall() == []
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute('insert into public.learning_task_drafts(student_sub,course_id,task_id,text_body) values (%s,%s,%s,%s)', (f.student_sub, f.course_id, f.task['id'], 'overwrite'))
        conn.rollback()
    with psycopg.connect(os.environ['SERVICE_ROLE_DSN']) as conn:
        with conn.cursor() as cur:
            if removed == 'task':
                cur.execute('delete from public.unit_tasks where id=%s', (f.task['id'],))
            elif removed == 'course':
                cur.execute('delete from public.courses where id=%s', (f.course_id,))
            else:
                cur.execute('delete from public.course_memberships where course_id=%s and student_id=%s', (f.course_id, f.student_sub))
            cur.execute('select count(*) from public.learning_task_drafts where course_id=%s', (f.course_id,))
            assert cur.fetchone()[0] == 0


@pytest.mark.parametrize('restriction', ['archived', 'ended', 'upload'])
async def test_lifecycle_and_task_type_restrict_access(monkeypatch, restriction):
    f = await _prepare_learning_fixture(monkeypatch)
    async with await _client() as c:
        c.cookies.set('gustav_session', f.student_session_id)
        assert (await c.put(endpoint(f), json={'text_body': 'retained'})).status_code == 200
        with psycopg.connect(os.environ['SERVICE_ROLE_DSN']) as conn:
            if restriction == 'archived':
                conn.execute("update public.courses set status='archived', archived_at=now() where id=%s", (f.course_id,))
            elif restriction == 'ended':
                conn.execute('update public.course_memberships set ended_at=now() where course_id=%s', (f.course_id,))
            else:
                conn.execute("update public.unit_tasks set kind='visual' where id=%s", (f.task['id'],))
        assert (await c.get(endpoint(f))).status_code == 404
        assert (await c.put(endpoint(f), json={'text_body': 'forbidden'})).status_code == 404
        with psycopg.connect(os.environ['SERVICE_ROLE_DSN']) as conn:
            assert conn.execute('select text_body from public.learning_task_drafts where course_id=%s', (f.course_id,)).fetchone() == ('retained',)


async def test_database_outage_fails_closed_without_disclosing_text(monkeypatch):
    from backend.web.learning_draft_providers import LearningDraftProviders
    f = await _prepare_learning_fixture(monkeypatch)
    def unavailable():
        raise psycopg.OperationalError('database offline')
    monkeypatch.setattr(main.app.state, 'learning_draft_providers', LearningDraftProviders(repository=unavailable))
    async with await _client() as c:
        c.cookies.set('gustav_session', f.student_session_id)
        for response in [await c.get(endpoint(f)), await c.put(endpoint(f), json={'text_body': 'private'})]:
            assert response.status_code == 503
            assert response.json() == {'error': 'service_unavailable'}


async def test_modular_open_task_allowed_but_locked_task_hidden(monkeypatch):
    from backend.tests.test_learning_h5p_access_check_api import _prepare_locked_modular_h5p_task
    f = await _prepare_locked_modular_h5p_task(monkeypatch)
    with psycopg.connect(os.environ['SERVICE_ROLE_DSN']) as conn:
        conn.execute("update public.unit_tasks set kind='native', h5p_content_id=null where id=%s", (f['task_b'],))
    async with await _client() as c:
        c.cookies.set('gustav_session', f['student'].session_id)
        base = f'/api/learning/courses/{f["course_id"]}/tasks'
        assert (await c.put(f'{base}/{f["task_a"]}/draft', json={'text_body': 'open'})).status_code == 200
        assert (await c.put(f'{base}/{f["task_b"]}/draft', json={'text_body': 'locked'})).status_code == 404


async def test_practice_module_does_not_use_task_drafts(monkeypatch):
    f = await _prepare_learning_fixture(monkeypatch)
    with psycopg.connect(os.environ['SERVICE_ROLE_DSN']) as conn:
        # Fixture-only data: make this section a valid practice module. No schema changes.
        conn.execute('delete from public.unit_materials where section_id=%s', (f.section_id,))
        conn.execute("update public.unit_tasks set max_attempts=null, model_solution_md='Example solution' where id=%s", (f.task['id'],))
        phase = conn.execute('insert into public.unit_phases(unit_id,title,position) values (%s,%s,1) returning id', (f.unit_id, 'Practice')).fetchone()[0]
        conn.execute('''insert into public.unit_modules(unit_id,section_id,phase_id,position_in_phase,module_kind)
            values (%s,%s,%s,1,'practice')''', (f.unit_id, f.section_id, phase))
    async with await _client() as c:
        c.cookies.set('gustav_session', f.student_session_id)
        assert (await c.put(endpoint(f), json={'text_body': 'excluded'})).status_code == 404


async def test_stale_browser_identity_cannot_write_into_newly_logged_in_account(monkeypatch):
    f = await _prepare_learning_fixture(monkeypatch)
    async with await _client() as c:
        c.cookies.set('gustav_session', f.student_session_id)
        stale = {'X-Draft-Owner': 'previous-account'}
        assert (await c.put(endpoint(f), json={'text_body': 'private previous account'}, headers=stale)).status_code == 403
        assert (await c.get(endpoint(f), headers=stale)).status_code == 403
        assert (await c.get(endpoint(f))).status_code == 204
        assert (await c.put(endpoint(f), json={'text_body': 'current account'}, headers={'X-Draft-Owner': f.student_sub})).status_code == 200
