"""
SSR UI — Schülerabgaben (RED)

Validiert, dass die Aufgabenkarte ein Abgabeformular mit Umschalter (Text/Bild/Dokument)
anzeigt, dass Textabgabe via PRG einen Erfolgshinweis rendert und die Historie mit
dem neuesten Eintrag geöffnet ist. Solange UI‑Routen fehlen, schlagen diese Tests fehl.
"""
from __future__ import annotations

import json
import re
import uuid
import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import os
import psycopg  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _prepare_learning_fixture():
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        # Teacher seeds course/unit/section/task and releases
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"})
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Abschnitt"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "### Aufgabe A", "criteria": ["Kriterium 1"], "max_attempts": 2},
        )
        task_id = r_task.json()["id"]
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
        module_id = r_module.json()["id"]
        await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
        )
        # Add student member
        await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name})  # type: ignore
    return student.session_id, course_id, unit_id, task_id


@pytest.mark.anyio
async def test_ui_renders_task_choice_cards():
    sid, course_id, unit_id, _task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit_id}")
    assert r.status_code == 200
    html = r.text
    # Zwei Optionen: Text | Upload (Choice Cards, Radios unter der Haube)
    assert re.search(r'name=\"mode\"[^>]*value=\"text\"', html)
    assert re.search(r'name=\"mode\"[^>]*value=\"upload\"', html)
    # Textfeld vorhanden
    assert 'textarea' in html and 'name="text_body"' in html
    # Upload-Input mit erlaubten Typen + Hinweis (kein Preview nötig)
    assert re.search(r'name=\"upload_file\"', html)
    assert 'accept="image/png,image/jpeg,application/pdf"' in html
    assert ('10 MB' in html) or ('10&nbsp;MB' in html)


@pytest.mark.anyio
async def test_ui_submit_text_prg_and_history_shows_latest_open():
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        # Erste Abgabe via UI-Route (Form POST) → PRG
        post = await c.post(
            f"/learning/courses/{course_id}/tasks/{task_id}/submit",
            data={"mode": "text", "text_body": "Meine Lösung"},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert post.status_code in (302, 303)
        # Folge GET → Banner und Historie mit neuestem Eintrag geöffnet
        follow = await c.get(post.headers.get("location", f"/learning/courses/{course_id}/units/{unit_id}"))
        assert follow.status_code == 200
        html = follow.text
        assert ("Erfolgreich eingereicht" in html) or ("role=\"alert\"" in html)
        # details open beim neuesten Eintrag
    assert re.search(r'<details[^>]*open[^>]*class=\"task-panel__history-entry\"', html)


@pytest.mark.anyio
async def test_ui_prg_redirect_includes_open_attempt_id():
    """PRG-Redirect enthält open_attempt_id für deterministisches Öffnen."""
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        post = await c.post(
            f"/learning/courses/{course_id}/tasks/{task_id}/submit",
            data={"mode": "text", "text_body": "Meine Lösung"},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert post.status_code in (302, 303)
        loc = post.headers.get("location", "")
    assert "open_attempt_id=" in loc
    # UUID v4 format (basic check)
    assert re.search(r"open_attempt_id=[0-9a-fA-F-]{8}-[0-9a-fA-F-]{4}-[0-9a-fA-F-]{4}-[0-9a-fA-F-]{4}-[0-9a-fA-F-]{12}", loc)


@pytest.mark.anyio
async def test_ui_history_lazy_load_fragment():
    sid, course_id, _, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(f"/learning/courses/{course_id}/tasks/{task_id}/history")
    assert r.status_code == 200
    html = r.text
    # Fragment enthält mindestens das Wrapper‑Element für die Historie
    assert 'class="task-panel__history"' in html


@pytest.mark.anyio
async def test_ui_unit_page_has_lazy_history_loader():
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit_id}")
    assert r.status_code == 200
    html = r.text
    # Page should include a lazy-loading placeholder for history per task
    assert f'hx-get="/learning/courses/{course_id}/tasks/{task_id}/history"' in html
    assert 'class="task-panel__history"' in html


@pytest.mark.anyio
async def test_ui_history_fragment_shows_text_when_analysis_missing():
    """History fragment must show a meaningful text even when analysis_json is null.

    We simulate a legacy record by nulling analysis_json via service DSN.
    """
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    # Create one submission via API (text)
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        resp = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            json={"kind": "text", "text_body": "Meine Lösung"},
        )
        assert resp.status_code == 202
        sub_id = resp.json().get("id")

    # Set analysis_json to NULL for this submission (simulate legacy row)
    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to modify analysis_json")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update public.learning_submissions set analysis_json = null where id = %s::uuid",
                (sub_id,),
            )

    # Fetch fragment; it should include the text from the submission as fallback
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(f"/learning/courses/{course_id}/tasks/{task_id}/history")
    assert r.status_code == 200
    html = r.text
    assert 'class="task-panel__history"' in html
    assert "Meine Lösung" in html


@pytest.mark.anyio
async def test_ui_history_fragment_shows_feedback_and_status_after_completion():
    """Completed submissions should surface feedback markdown and status details."""
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    # Create submission via API
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        resp = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            json={"kind": "text", "text_body": "Feedback Test"},
        )
        assert resp.status_code == 202
        submission = resp.json()
        sub_id = submission.get("id")
        assert sub_id

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to emulate worker completion")

    feedback_md = "### Feedback\n\n- Gut gemacht!"
    analysis = {
        "schema": "criteria.v1",
        "score": 4,
        "criteria_results": [{"criterion": "Kriterium 1", "score": 8}],
    }
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select public.learning_worker_update_completed(
                    %s::uuid,
                    %s,
                    %s,
                    %s::jsonb
                )
                """,
                (
                    sub_id,
                    "Feedback Test",
                    feedback_md,
                    json.dumps(analysis),
                ),
            )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(f"/learning/courses/{course_id}/tasks/{task_id}/history", params={"open_attempt_id": sub_id})
    assert r.status_code == 200
    html = r.text
    assert "Gut gemacht" in html
    assert "Status: completed" in html
    assert "Score: 4" in html


@pytest.mark.anyio
async def test_ui_history_fragment_renders_criteria_v2_badges_accessible():
    """Criteria.v2 payloads must render badges with clamped scores and accessible labels."""
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    # Create submission via API
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        resp = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            json={"kind": "text", "text_body": "Criteria Feedback"},
        )
        assert resp.status_code == 202
        submission = resp.json()
        sub_id = submission.get("id")
        assert sub_id

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to emulate worker completion")

    feedback_md = "### Formatives Feedback\n\n- Weiter so!"
    analysis = {
        "schema": "criteria.v2",
        "score": 3,
        "criteria_results": [
            {
                "criterion": "Struktur",
                "score": 12,  # will be clamped to 10
                "max_score": 10,
                "explanation_md": "Klare Gliederung.",
            },
            {
                "criterion": "Quellenarbeit",
                "score": 2,
                "explanation_md": "Quellenangaben fehlen.",
            },
            {
                "criterion": "Sprache",
                "explanation_md": "Lesefluss überwiegend flüssig.",
            },
        ],
    }
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select public.learning_worker_update_completed(
                    %s::uuid,
                    %s,
                    %s,
                    %s::jsonb
                )
                """,
                (
                    sub_id,
                    "Criteria Feedback",
                    feedback_md,
                    json.dumps(analysis),
                ),
            )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(
            f"/learning/courses/{course_id}/tasks/{task_id}/history",
            params={"open_attempt_id": sub_id},
        )
    assert r.status_code == 200
    html = r.text

    # Criteria container is rendered with an accessible heading
    assert '<section class="analysis-criteria"' in html
    assert "Auswertung" in html

    # First criterion: clamped score to 10/10 with success badge and aria-label
    assert "Struktur" in html
    assert 'class="badge badge-success"' in html
    assert "10/10" in html
    assert 'aria-label="Punkte 10 von 10"' in html

    # Second criterion: low score uses error badge and textual label
    assert "Quellenarbeit" in html
    assert 'class="badge badge-error"' in html
    assert "2/10" in html
    assert 'aria-label="Punkte 2 von 10"' in html

    # Third criterion: missing score omits badge entirely
    assert "Sprache" in html
    assert re.search(r"Sprache</span>\s*</header>", html)

    # Formatives Feedback section is present
    assert "Formatives Feedback" in html
    assert "Weiter so!" in html


@pytest.mark.anyio
async def test_ui_submit_upload_png_prg_and_history_shows_latest_open():
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        # Bild-Abgabe via UI-Route (Form POST) → PRG
        post = await c.post(
            f"/learning/courses/{course_id}/tasks/{task_id}/submit",
            data={
                "mode": "upload",
                "storage_key": "submissions/test/path/image.png",
                "mime_type": "image/png",
                "size_bytes": "2048",
                "sha256": "a" * 64,
            },
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert post.status_code in (302, 303)
        follow = await c.get(post.headers.get("location", f"/learning/courses/{course_id}/units/{unit_id}"))
        assert follow.status_code == 200
        html = follow.text
        assert ("Erfolgreich eingereicht" in html) or ("role=\"alert\"" in html)
        # details open beim neuesten Eintrag
    assert re.search(r'<details[^>]*open[^>]*class=\"task-panel__history-entry\"', html)


@pytest.mark.anyio
async def test_ssr_submit_csrf_guard():
    """Cross-site POST to SSR submit must be rejected with 403.

    We simulate a mismatched Origin header; the handler must block before any
    DB access is needed, so no course/task setup is required.
    """
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.post(
            f"/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submit",
            data={"mode": "text", "text_body": "CSRF"},
            headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "http://evil.local"},
            follow_redirects=False,
        )
    assert r.status_code == 403
    assert r.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_ui_submit_upload_pdf_prg_and_history_shows_latest_open():
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        # PDF-Abgabe via UI-Route (Form POST) → PRG
        post = await c.post(
            f"/learning/courses/{course_id}/tasks/{task_id}/submit",
            data={
                "mode": "upload",
                "storage_key": "submissions/test/path/doc.pdf",
                "mime_type": "application/pdf",
                "size_bytes": "4096",
                "sha256": "b" * 64,
            },
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert post.status_code in (302, 303)
        follow = await c.get(post.headers.get("location", f"/learning/courses/{course_id}/units/{unit_id}"))
        assert follow.status_code == 200
        html = follow.text
        assert ("Erfolgreich eingereicht" in html) or ("role=\"alert\"" in html)
        assert re.search(r'<details[^>]*open[^>]*class=\"task-panel__history-entry\"', html)
