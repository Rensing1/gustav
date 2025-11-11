"""
SSR UI: Per-entry detail pages for materials and tasks (TDD: RED first)

Goals:
- Each entry has a dedicated detail page with minimal edit/delete flows.
- UI delegates to API (PATCH/DELETE) and enforces CSRF; PRG redirects.
- Pages are private, no-store.
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


if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover
    main.SESSION_STORE = SessionStore()


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


@pytest.mark.anyio
async def test_material_detail_edit_and_delete_prg():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    sess = main.SESSION_STORE.create(sub="t-entry-1", name="Lehrer E1", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # Seed unit/section/material via API
        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Section"})).json()
        mat = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials",
            json={"title": "Alt", "body_md": "Text"},
        )).json()

        # Detail page renders; private cache
        page = await c.get(f"/units/{unit['id']}/sections/{section['id']}/materials/{mat['id']}")
        assert page.status_code == 200
        assert page.headers.get("Cache-Control") == "private, no-store"
        assert "Alt" in page.text
        token = _extract_csrf_token(page.text) or ""

        # Update (PRG)
        upd = await c.post(
            f"/units/{unit['id']}/sections/{section['id']}/materials/{mat['id']}/update",
            data={"title": "Neu", "body_md": "NeuText", "csrf_token": token},
            follow_redirects=False,
        )
        assert upd.status_code in (302, 303)
        # Reload detail
        page2 = await c.get(f"/units/{unit['id']}/sections/{section['id']}/materials/{mat['id']}")
        assert "Neu" in page2.text

        # Delete (PRG back to section)
        token2 = _extract_csrf_token(page2.text) or ""
        dele = await c.post(
            f"/units/{unit['id']}/sections/{section['id']}/materials/{mat['id']}/delete",
            data={"csrf_token": token2},
            follow_redirects=False,
        )
        assert dele.status_code in (302, 303)
        sec_page = await c.get(f"/units/{unit['id']}/sections/{section['id']}")
        assert "Neu" not in sec_page.text


@pytest.mark.anyio
async def test_task_detail_edit_and_delete_prg():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    sess = main.SESSION_STORE.create(sub="t-entry-2", name="Lehrer E2", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Section"})).json()
        task = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "Alt Instr", "criteria": ["A"], "hints_md": "Hinweis"},
        )).json()

        page = await c.get(f"/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}")
        assert page.status_code == 200
        assert page.headers.get("Cache-Control") == "private, no-store"
        assert "Alt Instr" in page.text
        token = _extract_csrf_token(page.text) or ""

        upd = await c.post(
            f"/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/update",
            data={
                "instruction_md": "Neu Instr",
                "criteria": ["X", "Y"],
                "hints_md": "Neuer Hinweis",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert upd.status_code in (302, 303)
        page2 = await c.get(f"/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}")
        assert "Neu Instr" in page2.text
        token2 = _extract_csrf_token(page2.text) or ""
        dele = await c.post(
            f"/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/delete",
            data={"csrf_token": token2},
            follow_redirects=False,
        )
        assert dele.status_code in (302, 303)
        sec_page = await c.get(f"/units/{unit['id']}/sections/{section['id']}")
        assert "Neu Instr" not in sec_page.text


@pytest.mark.anyio
async def test_material_file_detail_shows_download_link():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    teaching.set_storage_adapter(FakeStorageAdapter())
    sess = main.SESSION_STORE.create(sub="t-entry-file", name="Lehrer File", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit = (await c.post("/api/teaching/units", json={"title": "UnitF"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "SectionF"})).json()
        # Create upload intent and finalize via API
        intent = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "a.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )).json()
        mat = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={"intent_id": intent["intent_id"], "title": "PDF", "sha256": "f" * 64},
        )).json()

        page = await c.get(f"/units/{unit['id']}/sections/{section['id']}/materials/{mat['id']}")
        assert page.status_code == 200
        assert 'id="material-download-link"' in page.text
        assert 'http://storage.local/download' in page.text


@pytest.mark.anyio
async def test_tasks_due_and_max_attempts_in_create_and_edit():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    sess = main.SESSION_STORE.create(sub="t-entry-task-due", name="Lehrer TD", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit = (await c.post("/api/teaching/units", json={"title": "UnitT"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "SectionT"})).json()
        # Create via UI with due_at and max_attempts
        new_page = await c.get(f"/units/{unit['id']}/sections/{section['id']}/tasks/new")
        token = _extract_csrf_token(new_page.text) or ""
        resp = await c.post(
            f"/units/{unit['id']}/sections/{section['id']}/tasks/create",
            data={
                "instruction_md": "Abgabe",
                "due_at": "2025-01-01T10:00:00+00:00",
                "max_attempts": "3",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        lst = await c.get(f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks")
        task = lst.json()[0]
        assert task.get("due_at", "").startswith("2025-01-01T10:00:00")
        assert task.get("max_attempts") == 3

        # Edit task due_at/max_attempts
        page = await c.get(f"/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}")
        token2 = _extract_csrf_token(page.text) or ""
        upd = await c.post(
            f"/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/update",
            data={
                "instruction_md": "Abgabe",
                "due_at": "2025-02-02T12:00:00+00:00",
                "max_attempts": "5",
                "csrf_token": token2,
            },
            follow_redirects=False,
        )
        assert upd.status_code in (302, 303)
        lst2 = await c.get(f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks")
        task2 = lst2.json()[0]
        assert task2.get("due_at", "").startswith("2025-02-02T12:00:00")
        assert task2.get("max_attempts") == 5

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
