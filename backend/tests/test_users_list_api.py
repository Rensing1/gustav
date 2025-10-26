"""
Users API: GET /api/users/list

Scenarios
- Teachers can list students with pagination; returns [{sub,name}].
- Invalid role -> 400. Non-teacher -> 403.
"""

from __future__ import annotations

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


if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover
    main.SESSION_STORE = SessionStore()


@pytest.mark.anyio
async def test_users_list_teacher_succeeds_and_paginates(monkeypatch: pytest.MonkeyPatch):
    # Arrange fake directory results 6 users
    def fake_list_users_by_role(*, role: str, limit: int, offset: int):
        data = [{"sub": f"s{i}", "name": f"Student {i}"} for i in range(1, 7)]
        return data[offset: offset + limit]

    monkeypatch.setattr(users_routes, "list_users_by_role", fake_list_users_by_role)

    sess = main.SESSION_STORE.create(sub="t-list-1", name="Teacher", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r1 = await c.get("/api/users/list", params={"role": "student", "limit": 3, "offset": 0})
        r2 = await c.get("/api/users/list", params={"role": "student", "limit": 3, "offset": 3})

    assert r1.status_code == 200 and r2.status_code == 200
    assert [u["sub"] for u in r1.json()] == ["s1", "s2", "s3"]
    assert [u["sub"] for u in r2.json()] == ["s4", "s5", "s6"]


@pytest.mark.anyio
async def test_users_list_invalid_role_and_forbidden(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(users_routes, "list_users_by_role", lambda **kw: [])
    # Non-teacher
    stu = main.SESSION_STORE.create(sub="s-x", name="Stu", roles=["student"])
    tch = main.SESSION_STORE.create(sub="t-x", name="Tea", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, stu.session_id)
        r_forbid = await c.get("/api/users/list", params={"role": "student"})
        c.cookies.set(main.SESSION_COOKIE_NAME, tch.session_id)
        r_bad = await c.get("/api/users/list", params={"role": "invalid"})

    assert r_forbid.status_code == 403
    assert r_bad.status_code == 400

