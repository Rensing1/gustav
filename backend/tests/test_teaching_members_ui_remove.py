"""
SSR UI: Remove member via HTMX should update list.
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


pytestmark = pytest.mark.anyio("asyncio")


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_remove_member_htmx_updates_list():
    # Arrange: teacher, course with one member
    sess = main.SESSION_STORE.create(sub="t-rem-1", name="Lehrer", roles=["teacher"])
    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.post("/api/teaching/courses", json={"title": "Mathe R"})
        assert r.status_code == 201
        cid = r.json()["id"]
        add = await c.post(f"/api/teaching/courses/{cid}/members", json={"student_sub": "student-X"})
        assert add.status_code in (200, 201, 204)
        # Open members page
        page = await c.get(f"/courses/{cid}/members")
        assert page.status_code == 200
        token = _extract_csrf_token(page.text) or ""
        assert token
        assert "student-X" in page.text
        # Act: remove via HTMX
        r_del = await c.post(
            f"/courses/{cid}/members/student-X/delete",
            data={"csrf_token": token},
            headers={"HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        assert r_del.status_code == 200
        body = r_del.text
        # Member should be gone from the current members section; may reappear as candidate
        m = re.search(r'<section class=\"members-column card\" id=\"members-current\">(.*?)</section>', body, flags=re.S)
        current_html = m.group(1) if m else body
        assert "student-X" not in current_html
        # API consistency may be eventual in some setups; UI is the source of truth here.
    assert "student-X" not in body
