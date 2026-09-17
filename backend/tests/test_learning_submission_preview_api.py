"""Preview reads select the exact learner snapshot, independent of history size."""
from __future__ import annotations

import importlib
import os
from uuid import uuid4

import psycopg
import pytest

from backend.tests.test_learning_api_contract import _client, _prepare_learning_fixture

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


def seed_history(fixture):
    """Insert only this fixture's records; no worker/provider side effects."""
    final_id = str(uuid4())
    with psycopg.connect(os.environ["SERVICE_ROLE_DSN"]) as conn:
        conn.execute(
            """insert into public.learning_submissions
               (id, course_id, task_id, student_sub, section_id, attempt_nr, intent,
                kind, storage_key, mime_type, size_bytes, analysis_status, created_at)
               values (%s, %s, %s, %s, %s, 1, 'submit', 'file',
                       'submissions/preview/original.pdf', 'application/pdf', 2048,
                       'completed', now() - interval '1 day')""",
            (final_id, fixture.course_id, fixture.task["id"], fixture.student_sub, fixture.section_id),
        )
        conn.execute(
            """insert into public.learning_submissions
               (course_id, task_id, student_sub, section_id, attempt_nr, intent,
                kind, text_body, analysis_status, created_at)
               select %s, %s, %s, %s, n, 'feedback', 'text', 'Entwurf ' || n,
                      'completed', now() + n * interval '1 second'
                 from generate_series(2, 103) n""",
            (fixture.course_id, fixture.task["id"], fixture.student_sub, fixture.section_id),
        )
    return final_id


async def test_preview_filters_before_pagination_and_preserves_default_history(monkeypatch):
    fixture = await _prepare_learning_fixture(monkeypatch)
    final_id = seed_history(fixture)
    url = f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions"
    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        final = await client.get(url, params={"intent": "submit", "limit": 1})
        assert final.status_code == 200
        assert [row["id"] for row in final.json()] == [final_id]
        assert final.headers["cache-control"] == "private, no-store"
        feedback = await client.get(url, params={"intent": "feedback", "limit": 1, "offset": 1})
        assert feedback.json()[0]["attempt_nr"] == 102
        history = await client.get(url, params={"limit": 1})
        assert history.json()[0]["attempt_nr"] == 103
        for invalid in ("draft", "", "SUBMIT"):
            rejected = await client.get(url, params={"intent": invalid})
            assert rejected.status_code == 400
            assert rejected.json()["detail"] == "invalid_intent"


async def test_preview_file_older_than_100_attempts_still_opens(monkeypatch):
    fixture = await _prepare_learning_fixture(monkeypatch)
    final_id = seed_history(fixture)
    files = importlib.import_module("backend.web.routes.learning_submission_files")

    async def download(**kwargs):
        return b"%PDF-preview"

    monkeypatch.setattr(files, "_download_storage_object_via_presign", download)
    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        response = await client.get(
            f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions/{final_id}/file"
        )
        assert response.status_code == 200, response.text
        assert response.content == b"%PDF-preview"
        assert response.headers["cache-control"] == "private, no-store"


async def test_preview_filter_and_exact_file_keep_membership_and_release_guards(monkeypatch):
    fixture = await _prepare_learning_fixture(monkeypatch)
    final_id = seed_history(fixture)
    url = f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions"
    main = importlib.import_module("backend.web.main")
    other = main.RUNTIME.session_store.create(sub=f"other-{uuid4()}", name="Other", roles=["student"])
    with psycopg.connect(os.environ["SERVICE_ROLE_DSN"]) as conn:
        conn.execute("insert into public.course_memberships(course_id, student_id) values (%s, %s)",
                     (fixture.course_id, other.sub))
    async with (await _client()) as client:
        client.cookies.set("gustav_session", other.session_id)
        assert (await client.get(url, params={"intent": "submit"})).json() == []
        assert (await client.get(f"{url}/{final_id}/file")).status_code == 404
        client.cookies.set("gustav_session", fixture.teacher_session_id)
        assert (await client.get(url, params={"intent": "submit"})).status_code == 403
        client.cookies.clear()
        assert (await client.get(url, params={"intent": "submit"})).status_code == 401
        client.cookies.set("gustav_session", fixture.student_session_id)
        with psycopg.connect(os.environ["SERVICE_ROLE_DSN"]) as conn:
            conn.execute("delete from public.course_memberships where course_id=%s and student_id=%s",
                         (fixture.course_id, fixture.student_sub))
        assert (await client.get(url, params={"intent": "submit"})).status_code == 403
        assert (await client.get(f"{url}/{final_id}/file")).status_code == 403


async def test_preview_filter_and_file_require_a_released_section(monkeypatch):
    fixture = await _prepare_learning_fixture(monkeypatch, visible=False)
    final_id = seed_history(fixture)
    url = f"/api/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submissions"
    async with (await _client()) as client:
        client.cookies.set("gustav_session", fixture.student_session_id)
        assert (await client.get(url, params={"intent": "submit"})).status_code == 404
        assert (await client.get(f"{url}/{final_id}/file")).status_code == 404
