"""
SSR UI: /units/{unit_id}/sections/{section_id}/materials/new — Toggle + Datei-Flow

Ziele:
- Seite zeigt Umschaltung Text|Datei (nur ein Block sichtbar), No-JS-Hinweis für Datei.
- Datei-Flow nutzt Upload-Intent → Finalize (UI-Route) mit Redirect bei klassischem Submit.
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
from teaching.storage import NullStorageAdapter  # type: ignore  # noqa: E402


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
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections",
        json={"title": title},
        headers={"Origin": "http://test"},
    )
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


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
async def test_materials_new_shows_toggle_and_data_attrs():
    sess = main.SESSION_STORE.create(sub="t-ui-m-new-1", name="Lehrer MN1", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-MN1")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt M1")

        page = await c.get(
            f"/units/{unit_id}/sections/{section_id}/materials/new",
            headers={"Origin": "http://test"},
        )

    assert page.status_code == 200
    body = page.text
    assert 'name="material_mode"' in body
    assert 'class="material-form material-form--text"' in body
    assert 'class="material-form material-form--file"' in body
    assert 'data-intent-url="/api/teaching/units' in body
    assert 'data-allowed-mime="application/pdf,image/png,image/jpeg"' in body
    assert 'data-max-bytes="' in body
    # Datei-Form zeigt No-JS-Hinweis
    assert "Ohne JavaScript ist der Datei-Upload deaktiviert" in body
    # CSRF vorhanden
    assert _extract_csrf_token(body)


@pytest.mark.anyio
async def test_materials_finalize_redirects_and_creates_file_material():
    sess = main.SESSION_STORE.create(sub="t-ui-m-new-2", name="Lehrer MN2", roles=["teacher"])  # type: ignore
    fake_storage = FakeStorageAdapter()
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        teaching.set_storage_adapter(fake_storage)
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-MN2")
        section_id = await _create_section_via_api(c, unit_id=unit_id, title="Abschnitt M2")

        page = await c.get(
            f"/units/{unit_id}/sections/{section_id}/materials/new",
            headers={"Origin": "http://test"},
        )
        token = _extract_csrf_token(page.text) or ""

        intent = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
            json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
            headers={"Origin": "http://test"},
        )
        assert intent.status_code == 200
        intent_id = intent.json()["intent_id"]

        finalize = await c.post(
            f"/units/{unit_id}/sections/{section_id}/materials/finalize",
            data={
                "csrf_token": token,
                "intent_id": intent_id,
                "title": "PDF Material",
                "sha256": "a" * 64,
                "alt_text": "Kurzbeschreibung",
            },
            headers={"Origin": "http://test"},
            follow_redirects=False,
        )

        materials_resp = await c.get(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            headers={"Origin": "http://test"},
        )

    # Cleanup: restore null storage adapter to avoid leakage into other tests
    teaching.set_storage_adapter(NullStorageAdapter())

    assert finalize.status_code in (302, 303)
    assert finalize.headers.get("location", "").endswith(f"/units/{unit_id}/sections/{section_id}")

    assert materials_resp.status_code == 200
    mats = materials_resp.json()
    assert isinstance(mats, list) and len(mats) == 1
    mat = mats[0]
    assert mat.get("title") == "PDF Material"
    assert mat.get("kind") == "file"
