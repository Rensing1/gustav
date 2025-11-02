"""
SSR — Unterricht Live: Abschnitte freigeben Panel

Validates that the Live page for a course/unit renders a panel to toggle
section visibility and that the markup wires HTMX actions to a server-side
helper which delegates to the JSON API.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _attach_unit_to_course(
    client: httpx.AsyncClient, course_id: str, unit_id: str, context_notes: str | None = None
) -> dict:
    payload: dict[str, object] = {"unit_id": unit_id}
    if context_notes is not None:
        payload["context_notes"] = context_notes
    resp = await client.post(f"/api/teaching/courses/{course_id}/modules", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_live_page_renders_section_release_panel_and_toggles():
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="teacher-live-sections", name="Frau Live", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", owner.session_id)
        cid = await _create_course(client, "Kurs SSR Freigaben")
        unit = await _create_unit(client, "Einheit SSR Freigaben")
        s1 = await _create_section(client, unit["id"], "Einführung")
        s2 = await _create_section(client, unit["id"], "Experimente")
        module = await _attach_unit_to_course(client, cid, unit["id"])  # noqa: F841

        # Initially all hidden; render page
        page = await client.get(f"/teaching/courses/{cid}/units/{unit['id']}/live")
        assert page.status_code == 200
        html = page.text
        assert "section-releases-panel" in html
        assert "Einführung" in html and "Experimente" in html
        # Toggle buttons should reference a server-side visibility helper
        assert f"/teaching/courses/{cid}/modules/{module['id']}/sections/{s1['id']}/visibility" in html

        # Simulate clicking toggle to set s2 visible via SSR helper
        resp = await client.post(
            f"/teaching/courses/{cid}/modules/{module['id']}/sections/{s2['id']}/visibility",
            data={"visible": "true", "unit_id": unit["id"]},
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        panel = resp.text
        # Panel should re-render with s2 visible marker
        assert "Experimente" in panel
        assert "data-visible=\"true\"" in panel or "Freigegeben" in panel

        # Toggle back to hidden
        resp2 = await client.post(
            f"/teaching/courses/{cid}/modules/{module['id']}/sections/{s2['id']}/visibility",
            data={"visible": "false", "unit_id": unit["id"]},
            headers={"HX-Request": "true"},
        )
        assert resp2.status_code == 200
        panel2 = resp2.text
        assert "Experimente" in panel2
        assert "data-visible=\"false\"" in panel2 or "Versteckt" in panel2
