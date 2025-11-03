"""
SSR UI — Candidate list shows at most 10 entries by default.

BDD
- Given the directory adapter returns >10 students
- When the owner opens the members page search without a query
- Then the candidate list renders at most 10 entries.
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
from routes import users as users_routes  # type: ignore
from utils.db import require_db_or_skip as _require_db_or_skip


def _count_candidate_items(html: str) -> int:
    m = re.search(r'<div id=\"search-results\">(.*?)</div>', html, flags=re.S)
    block = m.group(1) if m else html
    return len(re.findall(r'<li class=\"member-item\">', block))


@pytest.mark.anyio
async def test_candidates_list_max_10(monkeypatch: pytest.MonkeyPatch):
    _require_db_or_skip()
    main.SESSION_STORE = SessionStore()
    t = main.SESSION_STORE.create(sub="teacher-cand-10", name="Owner", roles=["teacher"])

    # Patch list_users_by_role to return 30 students
    def many_students(*, role: str, limit: int, offset: int) -> list[dict]:
        assert role == "student"
        data = [{"sub": f"stud-{i:02d}", "name": f"Schueler {i:02d}"} for i in range(30)]
        # Simulate server paging at requested window
        return data[offset: offset + limit]

    monkeypatch.setattr(users_routes, "list_users_by_role", many_students)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, t.session_id)
        r = await c.post("/api/teaching/courses", json={"title": "Cand Limit"})
        assert r.status_code == 201
        cid = r.json()["id"]
        # Load just the candidates fragment (no query)
        frag = await c.get(f"/courses/{cid}/members/search")
        assert frag.status_code == 200
        assert _count_candidate_items(frag.text) <= 10

