"""
Teaching API — Live summary prefers person names and falls back safely.
"""
from __future__ import annotations

import os
import pytest
import httpx
from httpx import ASGITransport
import importlib

pytestmark = pytest.mark.anyio("asyncio")

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip
os.environ["ALLOW_SERVICE_DSN_FOR_TESTING"] = "true"
main = importlib.import_module("backend.web.main")
teaching = importlib.import_module("backend.web.routes.teaching")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


@pytest.mark.anyio
async def test_summary_prefers_person_names_and_uses_localpart_only_as_fallback(monkeypatch):
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    def _fake_live_resolve(subs: list[str]) -> dict[str, str]:
        return {
            str(subs[0]): "Lena Beispiel",
            str(subs[1]): "alice",
        }

    import backend.identity_access.directory as dir_mod  # type: ignore
    monkeypatch.setattr(dir_mod, "resolve_live_student_names_by_sub", _fake_live_resolve)

    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="t-humanize-owner", name="Owner", roles=["teacher"])
    s1 = "sub-1"
    s2 = "sub-2"

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Kurs Namen")
        unit = await _create_unit(c, "Einheit Namen")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, s1)
        await _add_member(c, cid, s2)

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200
        body = r.json()
        rows = body.get("rows") or []
        assert rows, "expected rows with members"
        names = [row["student"]["name"] for row in rows]
        assert "Lena Beispiel" in names
        assert "alice" in names
        assert not any(n.startswith("legacy-email:") for n in names)
        assert not any("@" in n for n in names)
