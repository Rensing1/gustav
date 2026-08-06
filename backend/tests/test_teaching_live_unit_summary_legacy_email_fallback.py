"""
Teaching API — Summary falls back to local-only login labels when direct lookup misses.
"""
from __future__ import annotations

import os
import pytest
import httpx
from httpx import ASGITransport
import importlib

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

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
    r = await client.post("/api/teaching/courses", json={"title": title, "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
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
async def test_summary_falls_back_to_legacy_email_localpart_and_hides_random_ids(monkeypatch):
    _require_db_or_skip()
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    def _fake_dir_resolve(subs: list[str]) -> dict[str, str]:
        return {sid: "Unbekannt" for sid in subs}

    import backend.identity_access.directory as dir_mod  # type: ignore
    monkeypatch.setattr(dir_mod, "resolve_student_login_labels_by_sub", _fake_dir_resolve)

    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="t-legacy-owner", name="Owner", roles=["teacher"])

    legacy_sub = "legacy-email:student@example.com"
    random_sub = "not-a-uuid-sub-xyz"

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Kurs Legacy Names")
        unit = await _create_unit(c, "Einheit Legacy Names")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, legacy_sub)
        await _add_member(c, cid, random_sub)

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200
        rows = r.json().get("rows") or []
        assert len(rows) >= 2
        names_by_sub = {row["student"]["sub"]: row["student"]["name"] for row in rows}

        # Legacy email must fall back to the stable localpart.
        legacy_name = names_by_sub.get(legacy_sub, "")
        assert legacy_name and "@" not in legacy_name and not legacy_name.startswith("legacy-email:")
        assert legacy_name == "student"

        # Random SUB should remain Unbekannt (no false localpart derivation)
        assert names_by_sub.get(random_sub, "") == "Unbekannt"
