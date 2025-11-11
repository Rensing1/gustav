"""
SSR UI: Edit/Members prefill must use GET /api/teaching/courses/{id}

Scenario: When a teacher owns many courses (> 50), prefill for a course not in
the first page should still work by using the direct GET endpoint (not a list
scan limited to 50).
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


# Ensure tests use the in-memory session store – avoids DB dependency.
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()


def _extract_value(html: str, field: str) -> str | None:
    # naive: find <input id="field" ... value="...">
    m = re.search(rf'id=\"{re.escape(field)}\"[^>]*value=\"([^\"]*)\"', html)
    return m.group(1) if m else None


@pytest.mark.anyio
async def test_edit_prefill_uses_get_by_id_beyond_first_page():
    # Arrange: teacher with 55 courses; target is #55 (outside first 50)
    sess = main.SESSION_STORE.create(sub="t-prefill-1", name="Lehrer", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # Seed 55 courses, capture IDs in order of creation
        created: list[tuple[str, str]] = []
        for i in range(55):
            title = f"Kurs {i+1}"
            r = await c.post("/api/teaching/courses", json={"title": title})
            assert r.status_code == 201
            body = r.json()
            created.append((body["id"], title))
        # Pick the 51st created (index 50), which is outside the first page of 50
        cid, expected_title = created[50]

        # Act: open edit form and assert prefill equals the target course
        r_form = await c.get(f"/courses/{cid}/edit")
        assert r_form.status_code == 200
        title_value = _extract_value(r_form.text, "title")

    assert title_value == expected_title
