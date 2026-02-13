"""
SSR UI — Members page renders email-localpart labels.

BDD
- Given members and candidates with email-like names
- When the owner opens/searches the members page
- Then labels are rendered as localpart only (no domain, no legacy prefix).
"""
from __future__ import annotations

from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest

from utils.db import require_db_or_skip as _require_db_or_skip


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from routes import teaching as teaching_routes  # type: ignore
from routes import users as users_routes  # type: ignore


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_members_ui_renders_localpart_for_members_and_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_db_or_skip()
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="teacher-localpart-ui", name="Owner", roles=["teacher"])

    def fake_resolve_student_names(subs: list[str]) -> dict[str, str]:
        mapping = {
            "member-a": "zoe.zebra@schule.example",
            "member-b": "legacy-email:adam.apfel@schule.example",
            "member-c": "Unbekannt",
        }
        return {sid: mapping.get(sid, "Unbekannt") for sid in subs}

    def fake_search_users_by_name(*, role: str, q: str, limit: int) -> list[dict]:
        assert role == "student"
        return [
            {"sub": "cand-a", "name": "anna.muster@schule.example"},
            {"sub": "cand-b", "name": "legacy-email:max.von.beispiel@schule.example"},
        ][:limit]

    monkeypatch.setattr(teaching_routes, "resolve_student_names", fake_resolve_student_names, raising=False)
    monkeypatch.setattr(users_routes, "search_users_by_name", fake_search_users_by_name)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        created = await c.post("/api/teaching/courses", json={"title": "Localpart Labels"})
        assert created.status_code == 201, created.text
        course_id = str(created.json()["id"])

        for sid in ("member-a", "member-b", "member-c"):
            add = await c.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": sid})
            assert add.status_code in (200, 201, 204), add.text

        page = await c.get(f"/courses/{course_id}/members")
        assert page.status_code == 200
        body = page.text
        assert "zoe.zebra" in body
        assert "adam.apfel" in body
        assert "Unbekannt" in body
        assert "@schule.example" not in body
        assert "legacy-email:" not in body

        # Sorted by final display label: adam.apfel, Unbekannt, zoe.zebra
        assert body.index("adam.apfel") < body.index("Unbekannt")
        assert body.index("Unbekannt") < body.index("zoe.zebra")

        search = await c.get(f"/courses/{course_id}/members/search?q=an")
        assert search.status_code == 200
        search_html = search.text
        assert "anna.muster" in search_html
        assert "max.von.beispiel" in search_html
        assert "@schule.example" not in search_html
        assert "legacy-email:" not in search_html
