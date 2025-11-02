"""
Teaching API — CSRF strictness for section visibility updates.

PATCH /api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility
must require Origin/Referer presence and same-origin semantics.
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

import uuid

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402
from utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title}, headers={"Origin": "http://test"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title}, headers={"Origin": "http://test"})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections", json={"title": title}, headers={"Origin": "http://test"}
    )
    assert resp.status_code == 201
    return resp.json()


async def _attach_unit_to_course(
    client: httpx.AsyncClient, course_id: str, unit_id: str, context_notes: str | None = None
) -> dict:
    payload: dict[str, object] = {"unit_id": unit_id}
    if context_notes is not None:
        payload["context_notes"] = context_notes
    resp = await client.post(
        f"/api/teaching/courses/{course_id}/modules", json=payload, headers={"Origin": "http://test"}
    )
    assert resp.status_code == 201
    return resp.json()


def _visibility_path(course_id: str, module_id: str, section_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"


@pytest.mark.anyio
async def test_visibility_patch_requires_origin_or_referer(monkeypatch: pytest.MonkeyPatch):
    # Enforce strict CSRF policy for teaching writes in this test
    monkeypatch.setenv("STRICT_CSRF_TEACHING", "true")
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    try:
        from routes import teaching as teaching_routes  # noqa: F401  # type: ignore
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching_routes.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(client)
        unit = await _create_unit(client)
        sec = await _create_section(client, unit["id"], "A")
        mod = await _attach_unit_to_course(client, cid, unit["id"])  # noqa: F841

        # Missing Origin/Referer → 403 csrf_violation
        r1 = await client.patch(_visibility_path(cid, mod["id"], sec["id"]), json={"visible": True})
        assert r1.status_code == 403
        assert r1.json().get("detail") == "csrf_violation"

        # Foreign Origin → 403 csrf_violation
        r2 = await client.patch(
            _visibility_path(cid, mod["id"], sec["id"]),
            json={"visible": True},
            headers={"Origin": "http://evil"},
        )
        assert r2.status_code == 403
        assert r2.json().get("detail") == "csrf_violation"

        # Same-origin Origin → 200
        r3 = await client.patch(
            _visibility_path(cid, mod["id"], sec["id"]),
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r3.status_code == 200
