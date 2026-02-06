"""
Teaching API contract: members list pagination defaults remain stable.

Why:
    The endpoint documents `limit=10` as default. Passing `limit=0` should not
    silently expand the window beyond the documented default.

BDD:
- Given a course with more than 10 members
- When the owner calls GET /api/teaching/courses/{id}/members?limit=0
- Then the response returns exactly 10 items (default window) and no-store headers
"""

from __future__ import annotations

from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
import routes.teaching as teaching  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_members_limit_zero_uses_documented_default_10(monkeypatch: pytest.MonkeyPatch) -> None:
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-members-default-10", name="Teach", roles=["teacher"])  # type: ignore

    # Keep this test deterministic and fully local (no Keycloak dependency).
    monkeypatch.setattr(
        teaching,
        "resolve_student_names",
        lambda subs: {sid: f"Name:{sid}" for sid in subs},
        raising=False,
    )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        created = await c.post("/api/teaching/courses", json={"title": "Paginated Kurs"})
        assert created.status_code == 201, created.text
        course_id = str(created.json()["id"])

        for i in range(15):
            resp = await c.post(
                f"/api/teaching/courses/{course_id}/members",
                json={"student_sub": f"s-default-{i:02d}"},
            )
            assert resp.status_code in (201, 204), resp.text

        listed = await c.get(
            f"/api/teaching/courses/{course_id}/members",
            params={"limit": 0, "offset": 0},
        )

    assert listed.status_code == 200, listed.text
    assert listed.headers.get("Cache-Control") == "private, no-store"
    payload = listed.json()
    assert isinstance(payload, list)
    assert len(payload) == 10
