"""
Cache-Control hardening for teaching materials/tasks lists.

Validates that runtime responses for section-scoped list endpoints include
`Cache-Control: private, no-store` to avoid caching of teacher-scoped data.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402

from utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    # Strict CSRF is always enforced (dev = prod). Provide same-origin header by default.
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_materials_and_tasks_list_include_private_no_store():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    # Ensure DB-backed repo is in use; otherwise this test is not meaningful
    import routes.teaching as teaching
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    teacher = main.SESSION_STORE.create(sub="t-cache-mat-task", name="Autor", roles=["teacher"])  # type: ignore

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Create unit and section
        unit = (await client.post("/api/teaching/units", json={"title": "Cache Test"})).json()
        section = (
            await client.post(
                f"/api/teaching/units/{unit['id']}/sections", json={"title": "A"}
            )
        ).json()

        # Materials list
        r_mat = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials"
        )
        assert r_mat.status_code == 200
        cc_mat = r_mat.headers.get("Cache-Control", "")
        assert "private" in cc_mat and "no-store" in cc_mat

        # Tasks list
        r_task = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks"
        )
        assert r_task.status_code == 200
        cc_task = r_task.headers.get("Cache-Control", "")
        assert "private" in cc_task and "no-store" in cc_task
