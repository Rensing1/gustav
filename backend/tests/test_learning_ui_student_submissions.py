"""
SSR UI — Schülerabgaben (RED)

Validiert, dass die Aufgabenkarte ein Abgabeformular mit Umschalter (Text/Bild/Dokument)
anzeigt, dass Textabgabe via PRG einen Erfolgshinweis rendert und die Historie mit
dem neuesten Eintrag geöffnet ist. Solange UI‑Routen fehlen, schlagen diese Tests fehl.
"""
from __future__ import annotations

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
async def test_ui_renders_task_form_with_toggle():
    sid, course_id, unit_id, _task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit_id}")
    assert r.status_code == 200
    html = r.text
    # Umschalter (Radio) für drei Modi
    assert re.search(r'name=\"mode\"[^>]*value=\"text\"', html)
    assert re.search(r'name=\"mode\"[^>]*value=\"image\"', html)
    assert re.search(r'name=\"mode\"[^>]*value=\"file\"', html)
    # Textfeld vorhanden
    assert 'textarea' in html and 'name="text_body"' in html
    # Keine Bildvorschau erforderlich (UI-Entscheidung), also prüfen wir nicht darauf


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
        assert resp.status_code == 201
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
async def test_ui_submit_image_prg_and_history_shows_latest_open():
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        # Bild-Abgabe via UI-Route (Form POST) → PRG
        post = await c.post(
            f"/learning/courses/{course_id}/tasks/{task_id}/submit",
            data={
                "mode": "image",
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
async def test_ui_submit_pdf_prg_and_history_shows_latest_open():
    sid, course_id, unit_id, task_id = await _prepare_learning_fixture()
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        # PDF-Abgabe via UI-Route (Form POST) → PRG
        post = await c.post(
            f"/learning/courses/{course_id}/tasks/{task_id}/submit",
            data={
                "mode": "file",
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
