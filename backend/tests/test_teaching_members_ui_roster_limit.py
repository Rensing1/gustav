"""
SSR UI — Members page shows at most 10 current members by default.

BDD
- Given a course with >10 members
- When the owner opens /courses/{id}/members
- Then the "Aktuelle Kursmitglieder" list renders exactly 10 items.
"""
from __future__ import annotations

import re
from pathlib import Path
import sys
import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from utils.db import require_db_or_skip as _require_db_or_skip


def _count_current_members(html: str) -> int:
    m = re.search(r'<section class=\"members-column card\" id=\"members-current\">(.*?)</section>', html, flags=re.S)
    section = m.group(1) if m else html
    return len(re.findall(r'<li class=\"member-item\">', section))


@pytest.mark.anyio
async def test_members_page_renders_max_10_current_members():
    _require_db_or_skip()
    main.SESSION_STORE = SessionStore()
    t = main.SESSION_STORE.create(sub="teacher-roster-10", name="Owner", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, t.session_id)
        r = await c.post("/api/teaching/courses", json={"title": "Roster 10"})
        assert r.status_code == 201
        cid = r.json()["id"]
        for i in range(15):
            resp = await c.post(f"/api/teaching/courses/{cid}/members", json={"student_sub": f"stud-{i:02d}"})
            assert resp.status_code in (200, 201, 204)
        page = await c.get(f"/courses/{cid}/members")
        assert page.status_code == 200
        assert _count_current_members(page.text) == 10
