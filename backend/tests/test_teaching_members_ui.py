"""
SSR UI: /courses/{id}/members – Directory-backed search, no dummy data

User Story
As a teacher, I want to search real students via the Users API and add them to my course so that I never see hard-coded dummy entries on the members page.

BDD Scenarios
- Given a teacher on the members page, when entering a 2+ character query, then the UI shows candidates from GET /api/users/search, excluding current members.
- Given a 1-character query, when searching, then the UI shows no candidates (no API call/empty result).

Notes
- Tests seed course and memberships through the API to ensure the UI reflects DB state.
- Users search is monkeypatched at the API layer (routes.users.search_users_by_name) to avoid external dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
import sys
import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

from identity_access.stores import SessionStore
import main  # type: ignore
from routes import users as users_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


# Ensure tests use the in-memory session store – avoids DB dependency.
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()


async def _seed_course(client: httpx.AsyncClient, *, title: str, teacher_session_cookie: str) -> str:
    client.cookies.set(main.SESSION_COOKIE_NAME, teacher_session_cookie)
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    # Return created course id by listing
    lst = await client.get("/api/teaching/courses")
    assert lst.status_code == 200
    items = lst.json()
    assert items, "expected at least one course"
    return items[-1]["id"]


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_members_search_uses_api_and_excludes_existing(monkeypatch: pytest.MonkeyPatch):
    # Arrange: teacher, one course with one existing member
    sess = main.SESSION_STORE.create(sub="t-members-1", name="Lehrer", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        cid = await _seed_course(c, title="Mathe 7", teacher_session_cookie=sess.session_id)
        # Add existing member via API
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        add = await c.post(f"/api/teaching/courses/{cid}/members", json={"student_sub": "student-1"})
        assert add.status_code in (200, 201, 204)

        # Monkeypatch directory search to return three students (one already a member)
        def fake_list_users_by_role(*, role: str, limit: int, offset: int) -> list[dict]:
            assert role == "student"
            data = [
                {"sub": "student-1", "name": "Max Musterschüler"},
                {"sub": "student-2", "name": "Erika Mustermann"},
                {"sub": "student-3", "name": "Peter Pan"},
            ]
            return data[offset: offset + limit]

        monkeypatch.setattr(users_routes, "list_users_by_role", fake_list_users_by_role)

        # Get members page for CSRF token
        r_page = await c.get(f"/courses/{cid}/members")
        assert r_page.status_code == 200
        token = _extract_csrf_token(r_page.text) or ""
        assert token

        # Act: search with 2+ chars
        r_search = await c.get(f"/courses/{cid}/members/search?q=Mu")
        assert r_search.status_code == 200
        body = r_search.text

    # Assert: existing member is excluded; other candidates are present
    assert "Max Musterschüler" not in body
    assert "Erika Mustermann" in body


@pytest.mark.anyio
async def test_members_search_too_short_query_returns_empty(monkeypatch: pytest.MonkeyPatch):
    # Arrange: teacher and one course; patch search to raise if called unexpectedly
    sess = main.SESSION_STORE.create(sub="t-members-2", name="Lehrer", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        cid = await _seed_course(c, title="Deutsch 8", teacher_session_cookie=sess.session_id)

        def fail_if_called(*args, **kwargs):  # pragma: no cover - ensure API not called
            raise AssertionError("users search API should not be called for short queries")

        # We still list users but don't call search; list is patched below
        monkeypatch.setattr(users_routes, "search_users_by_name", fail_if_called)
        monkeypatch.setattr(users_routes, "list_users_by_role", lambda **kw: [])

        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # Act: query length = 1
        r = await c.get(f"/courses/{cid}/members/search?q=A")

    assert r.status_code == 200
    # Expect empty results markup
    assert "Keine Treffer." in r.text
