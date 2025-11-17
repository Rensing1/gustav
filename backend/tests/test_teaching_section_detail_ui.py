"""
SSR UI: /units/{unit_id}/sections/{section_id} – Materialien & Aufgaben

Ziele (TDD/RED):
- Detailseite eines Abschnitts rendert zwei Spalten (Materialien | Aufgaben)
- UI-POSTs zum Anlegen (Markdown) und Reorder existieren und respektieren CSRF
- Reorder akzeptiert id-Parameter wie von htmx-sortable (id=material_<uuid>/id=task_<uuid>)

Hinweis: Wir seeden Unit/Section über die API. Die UI nutzt die API, um Daten zu laden
und zu mutieren (Contract-First, Clean Architecture an der UI-Schicht).
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


# Tests sollen keinen DB-Session-Store benötigen
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensiv
    main.SESSION_STORE = SessionStore()


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


async def _create_unit_via_api(client: httpx.AsyncClient, *, title: str) -> str:
    r = await client.post("/api/teaching/units", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


async def _create_section_via_api(client: httpx.AsyncClient, *, unit_id: str, title: str) -> str:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


def _find_material_id_by_title(html: str, title: str) -> str | None:
    pattern = r'<div class=\"card material-card\" id=\"material_([a-f0-9\-]+)\"[\s\S]*?<h4 class=\"card-title\">\s*' + re.escape(title) + r'\s*<'
    m = re.search(pattern, html, re.S)
    return m.group(1) if m else None


def _find_task_id_by_instruction(html: str, instruction_snippet: str) -> str | None:
    pattern = r'<div class=\"card task-card\" id=\"task_([a-f0-9\-]+)\"[\s\S]*?<div class=\"task-instruction\">[\s\S]*?' + re.escape(instruction_snippet)
    m = re.search(pattern, html, re.S)
    return m.group(1) if m else None


def _extract_materials_wrapper(html: str, section_id: str) -> str:
    m = re.search(rf'<section id=\"material-list-section-{re.escape(section_id)}\">([\s\S]*?)</section>', html)
    return m.group(1) if m else html


class FakeStorageAdapter:
    def presign_upload(self, **kwargs):
        return {
            "url": "http://storage.local/upload",
            "headers": {"authorization": "Bearer stub"},
            "expires_at": "2099-01-01T00:00:00+00:00",
        }

    def head_object(self, **kwargs):
        return {"content_type": "application/pdf", "content_length": 1024}

    def presign_download(self, **kwargs):
        return {"url": "http://storage.local/download", "expires_at": "2099-01-01T00:00:30+00:00"}


@pytest.mark.anyio
async def test_section_detail_renders_two_columns_and_wrappers():
    # Arrange: Lehrer-Session und eine Unit+Section
    sess = main.SESSION_STORE.create(sub="t-ui-sec-detail-1", name="Lehrer SD", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        # Force in-memory repo to avoid DB dependency in this UI test
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-SD1")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt A")

        page = await c.get(f"/units/{unit_id}/sections/{section_id}")

    assert page.status_code == 200
    # Privacy header must be present
    assert page.headers.get("Cache-Control") == "private, no-store"
    body = page.text
    # Two-column wrappers must exist (stable ids for HTMX targets)
    assert f'id="material-list-section-{section_id}"' in body
    assert f'id="task-list-section-{section_id}"' in body
    # Sortable enabled for both lists (at least present once) and create buttons shown
    assert 'hx-ext="sortable"' in body
    assert f'href="/units/{unit_id}/sections/{section_id}/materials/new"' in body
    assert f'href="/units/{unit_id}/sections/{section_id}/tasks/new"' in body


@pytest.mark.anyio
async def test_create_material_shows_in_list_and_keeps_sortable():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-detail-2", name="Lehrer SD2", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-SD2")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt B")
        new_page = await c.get(f"/units/{unit_id}/sections/{section_id}/materials/new")
        token = _extract_csrf_token(new_page.text) or ""
        resp = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/create",
            data={"title": "Dok A", "body_md": "Hallo Welt", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert resp.status_code in (302, 303)
    page = await httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}).__aenter__()
    try:
        page.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        detail = await page.get(f"/units/{unit_id}/sections/{section_id}")
        assert detail.status_code == 200
        assert "Dok A" in detail.text
    finally:
        await page.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_create_task_shows_in_list_and_keeps_sortable():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-detail-3", name="Lehrer SD3", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-SD3")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt C")
        new_page = await c.get(f"/units/{unit_id}/sections/{section_id}/tasks/new")
        token = _extract_csrf_token(new_page.text) or ""
        resp = await c.post(
            f"/units/{unit_id}/sections/{section_id}/tasks/create",
            data={"instruction_md": "Rechne 1+1", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )

    assert resp.status_code in (302, 303)
    page = await httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}).__aenter__()
    try:
        page.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        detail = await page.get(f"/units/{unit_id}/sections/{section_id}")
        assert detail.status_code == 200
        assert "Rechne 1+1" in detail.text
    finally:
        await page.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_materials_reorder_accepts_id_param_and_changes_order():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-detail-4", name="Lehrer SD4", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-SD4")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt D")
        # Seed two materials via UI
        new_page = await c.get(f"/units/{unit_id}/sections/{section_id}/materials/new")
        token = _extract_csrf_token(new_page.text) or ""
        r1 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/create",
            data={"title": "A", "body_md": "X", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r2 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/create",
            data={"title": "B", "body_md": "Y", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r1.status_code in (302, 303) and r2.status_code in (302, 303)
        # Load material ids via API to avoid brittle HTML parsing in tests
        lst = await c.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/materials")
        assert lst.status_code == 200
        payload = lst.json()
        assert isinstance(payload, list)
        id_map = {m.get("title"): m.get("id") for m in payload}
        a_id = id_map.get("A") or ""
        b_id = id_map.get("B") or ""
        assert a_id and b_id and a_id != b_id

        # Reorder: put B before A
        form_body = f"id=material_{b_id}&id=material_{a_id}"
        rr = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/reorder",
            content=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
                "HX-Request": "true",
            },
        )
        assert rr.status_code in (200, 204)

        # Assert: B appears before A on page
        page3 = await c.get(f"/units/{unit_id}/sections/{section_id}")
        html3 = _extract_materials_wrapper(page3.text, section_id)
        # Accept either plain text or anchor-wrapped titles inside the H4
        titles = re.findall(r'<h4 class=\"card-title\">\s*(?:<a [^>]*>)?([^<]+)', html3)
        assert titles[:2] == ["B", "A"], html3


@pytest.mark.anyio
async def test_tasks_reorder_accepts_id_param_and_changes_order():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-detail-5", name="Lehrer SD5", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-SD5")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt E")
        new_page = await c.get(f"/units/{unit_id}/sections/{section_id}/tasks/new")
        token = _extract_csrf_token(new_page.text) or ""
        r1 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/tasks/create",
            data={"instruction_md": "Alpha", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r2 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/tasks/create",
            data={"instruction_md": "Beta", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r1.status_code in (302, 303) and r2.status_code in (302, 303)

        lst = await c.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
        assert lst.status_code == 200
        payload = lst.json()
        assert isinstance(payload, list)
        # Map by instruction_md
        id_map = {t.get("instruction_md"): t.get("id") for t in payload}
        alpha_id = id_map.get("Alpha") or ""
        beta_id = id_map.get("Beta") or ""
        assert alpha_id and beta_id and alpha_id != beta_id

        form_body = f"id=task_{beta_id}&id=task_{alpha_id}"
        rr = await c.post(
            f"/units/{unit_id}/sections/{section_id}/tasks/reorder",
            content=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
                "HX-Request": "true",
            },
        )
        assert rr.status_code in (200, 204)

        page3 = await c.get(f"/units/{unit_id}/sections/{section_id}")
        html3 = page3.text
        assert html3.find("Beta") < html3.find("Alpha")


@pytest.mark.anyio
async def test_file_upload_intent_ui_returns_presign_and_requires_csrf():
    sess = main.SESSION_STORE.create(sub="t-ui-files-1", name="Lehrer FU", roles=["teacher"])  # type: ignore
    import routes.teaching as teaching  # type: ignore
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    teaching.set_storage_adapter(FakeStorageAdapter())
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = (await c.post("/api/teaching/units", json={"title": "U-Files"})).json()["id"]
        section_id = (await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "S-Files"})).json()["id"]
        page = await c.get(f"/units/{unit_id}/sections/{section_id}/materials/new")
        token = _extract_csrf_token(page.text) or ""

        # Missing CSRF
        r_bad = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/upload-intent",
            data={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": "1024"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r_bad.status_code == 403

        r = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/upload-intent",
            data={
                "filename": "doc.pdf",
                "mime_type": "application/pdf",
                "size_bytes": "1024",
                "csrf_token": token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200
        body = r.text
        assert "data-upload-url=\"http://storage.local/upload\"" in body
        # Intent id is embedded for finalize step
        assert "name=\"intent_id\"" in body


@pytest.mark.anyio
async def test_file_finalize_ui_creates_material_and_updates_list():
    sess = main.SESSION_STORE.create(sub="t-ui-files-2", name="Lehrer FF", roles=["teacher"])  # type: ignore
    import routes.teaching as teaching  # type: ignore
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    teaching.set_storage_adapter(FakeStorageAdapter())
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = (await c.post("/api/teaching/units", json={"title": "U-Files2"})).json()["id"]
        section_id = (await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "S-Files2"})).json()["id"]
        page = await c.get(f"/units/{unit_id}/sections/{section_id}/materials/new")
        token = _extract_csrf_token(page.text) or ""
        intent_resp = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/upload-intent",
            data={"filename": "a.pdf", "mime_type": "application/pdf", "size_bytes": "1024", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert intent_resp.status_code == 200
        # Extract intent_id value from returned partial
        m = re.search(r'name=\"intent_id\"\s+value=\"([^\"]+)\"', intent_resp.text)
        assert m, intent_resp.text
        intent_id = m.group(1)

        finalize_resp = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/finalize",
            data={
                "intent_id": intent_id,
                "title": "PDF Material",
                "sha256": "f" * 64,
                "alt_text": "Beschreibung",
                "csrf_token": token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded", "HX-Request": "true"},
        )
        assert finalize_resp.status_code == 200
        # Returns updated material list with the new title present
        assert "PDF Material" in finalize_resp.text


@pytest.mark.anyio
async def test_material_tabs_are_rendered_for_text_and_file():
    sess = main.SESSION_STORE.create(sub="t-ui-tabs-1", name="Lehrer Tabs", roles=["teacher"])  # type: ignore
    import routes.teaching as teaching  # type: ignore
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = (await c.post("/api/teaching/units", json={"title": "U-Tabs"})).json()["id"]
        section_id = (await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "S-Tabs"})).json()["id"]
        # Section page should not show forms; navigate to material create page
        page = await c.get(f"/units/{unit_id}/sections/{section_id}/materials/new")
        assert page.status_code == 200
        html = page.text
        assert 'id="material-create-text"' in html
        assert 'class="material-form material-form--file"' in html
        assert 'name="material_mode"' in html
        # data-intent-url present for JS helper
        assert 'data-intent-url="/api/teaching/units' in html


@pytest.mark.anyio
async def test_tasks_form_has_criteria_and_hints_and_is_sent_to_api():
    sess = main.SESSION_STORE.create(sub="t-ui-task-crit-1", name="Lehrer Criteria", roles=["teacher"])  # type: ignore
    import routes.teaching as teaching  # type: ignore
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = (await c.post("/api/teaching/units", json={"title": "U-Task"})).json()["id"]
        section_id = (await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "S-Task"})).json()["id"]
        page = await c.get(f"/units/{unit_id}/sections/{section_id}/tasks/new")
        token = _extract_csrf_token(page.text) or ""
        # Ensure 10 criteria inputs exist on create page
        assert page.text.count('name="criteria"') >= 10
        assert 'name="hints_md"' in page.text

        resp = await c.post(
            f"/units/{unit_id}/sections/{section_id}/tasks/create",
            data={
                "instruction_md": "Beschreibe den Prozess",
                "criteria": ["Vollständigkeit", "Fachbegriffe", "Struktur"],
                "hints_md": "Denke an Einleitung–Hauptteil–Schluss",
                "csrf_token": token,
            },
        )
        assert resp.status_code in (302, 303)
        # Verify via API that the task persisted with criteria and hints
        lst = await c.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
        assert lst.status_code == 200
        data = lst.json()
        assert isinstance(data, list) and data
        task = data[0]
        assert task.get("criteria") == ["Vollständigkeit", "Fachbegriffe", "Struktur"]
        assert task.get("hints_md") == "Denke an Einleitung–Hauptteil–Schluss"


@pytest.mark.anyio
async def test_ui_posts_require_csrf():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-detail-6", name="Lehrer SD6", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-SD6")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt F")

        # Missing CSRF on create (materials)
        r1 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/create",
            data={"title": "X", "body_md": "Y"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        # Missing CSRF on create (tasks)
        r2 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/tasks/create",
            data={"instruction_md": "Z"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        # Missing CSRF header on reorder
        r3 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/reorder",
            content="id=material_foo",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r4 = await c.post(
            f"/units/{unit_id}/sections/{section_id}/tasks/reorder",
            content="id=task_bar",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert r1.status_code == 403
    assert r2.status_code == 403
    assert r3.status_code == 403
    assert r4.status_code == 403


@pytest.mark.anyio
async def test_material_list_links_to_detail_page():
    sess = main.SESSION_STORE.create(sub="t-ui-link-mat", name="Lehrer LM", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="U-L")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="S-L")
        # Seed material via API
        m = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            json={"title": "LinkMat", "body_md": "x"},
            headers={"Origin": "http://test"},
        )
        assert m.status_code == 201
        mid = m.json().get("id")
        page = await c.get(f"/units/{unit_id}/sections/{section_id}")
        assert page.status_code == 200
        assert f'href="/units/{unit_id}/sections/{section_id}/materials/{mid}"' in page.text


@pytest.mark.anyio
async def test_task_list_links_to_detail_page():
    sess = main.SESSION_STORE.create(sub="t-ui-link-task", name="Lehrer LT", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="U-LT")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="S-LT")
        t = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Bitte lösen"},
            headers={"Origin": "http://test"},
        )
        assert t.status_code == 201
        tid = t.json().get("id")
        page = await c.get(f"/units/{unit_id}/sections/{section_id}")
        assert page.status_code == 200
        assert f'href="/units/{unit_id}/sections/{section_id}/tasks/{tid}"' in page.text
