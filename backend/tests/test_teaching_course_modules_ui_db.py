"""
SSR UI + DB: /courses/{course_id}/modules — reorder persists via API on DB repo

Purpose:
- Ensure the UI forwarder `/courses/{course_id}/modules/reorder` works end-to-end
  against the DB-backed repository, catching schema/config regressions (e.g.,
  missing deferrable constraints) thanks to the two-phase update fallback.
"""
from __future__ import annotations

import re
from pathlib import Path
import sys

import httpx
from httpx import ASGITransport
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_course_modules_ui_reorder_persists_with_db_repo():
    _require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
    except Exception:
        pytest.skip("DB repo not available")

    # Switch to DB-backed repo for this test
    teaching.set_repo(DBTeachingRepo())  # type: ignore[attr-defined]

    # Teacher session
    sess = main.SESSION_STORE.create(sub="t-ui-mod-db", name="Lehrer DBMOD", roles=["teacher"])  # type: ignore

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)

        # Create course and two units
        r_course = await c.post("/api/teaching/courses", json={"title": "UI‑DB Kurs"})
        assert r_course.status_code == 201
        course_id = r_course.json().get("id")
        u1 = (await c.post("/api/teaching/units", json={"title": "Erste Einheit"})).json().get("id")
        u2 = (await c.post("/api/teaching/units", json={"title": "Zweite Einheit"})).json().get("id")
        assert u1 and u2

        # Attach as modules
        m1 = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u1})
        assert m1.status_code == 201
        m2 = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": u2})
        assert m2.status_code == 201

        # Load page and grab CSRF
        page = await c.get(f"/courses/{course_id}/modules")
        assert page.status_code == 200
        token = _extract_csrf_token(page.text) or ""
        assert token

        # Get module IDs via API to avoid parsing HTML
        lst = await c.get(f"/api/teaching/courses/{course_id}/modules")
        assert lst.status_code == 200
        mods = lst.json()
        id_map = {m.get("unit_id"): m.get("id") for m in mods}
        m1_id = id_map.get(u1) or ""
        m2_id = id_map.get(u2) or ""
        assert m1_id and m2_id and m1_id != m2_id

        # Reorder via UI forwarder: put m2 before m1
        form_body = f"id=module_{m2_id}&id=module_{m1_id}"
        rr = await c.post(
            f"/courses/{course_id}/modules/reorder",
            content=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
                "HX-Request": "true",
            },
        )
        assert rr.status_code in (200, 204)

        # Verify order via API list (positions 1,2 with m2 first)
        after = await c.get(f"/api/teaching/courses/{course_id}/modules")
        assert after.status_code == 200
        items = after.json()
        assert [m.get("id") for m in items] == [m2_id, m1_id]
        assert [m.get("position") for m in items] == [1, 2]
