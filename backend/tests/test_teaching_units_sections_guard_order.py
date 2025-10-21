"""
Guard-order tests to prevent error-oracle leaks for Units and Sections.

Intent:
    Non-authors must not learn about payload validation outcomes. The handler
    must check ownership (author) before validating the JSON body for PATCH.

Scenarios:
    - PATCH Unit with empty body as non-author → 403/404 (not 400).
    - PATCH Section with empty body as non-author → 403/404 (not 400).
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


def _require_db_or_skip() -> None:
    dsn = os.getenv("DATABASE_URL") or ""
    try:
        import psycopg  # type: ignore

        with psycopg.connect(dsn, connect_timeout=1):
            return
    except Exception:
        pytest.skip("Database not reachable; ensure migrations applied and DATABASE_URL set")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


@pytest.mark.anyio
async def test_non_author_unit_patch_empty_body_returns_403_or_404():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-guard-unit-author", name="A", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-guard-unit-other", name="B", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, "Mechanik")

        # Switch to non-author
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.patch(f"/api/teaching/units/{unit['id']}", json={})
        assert resp.status_code in (403, 404), resp.text


@pytest.mark.anyio
async def test_non_author_section_patch_empty_body_returns_403_or_404():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-guard-sec-author", name="A", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-guard-sec-other", name="B", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, "Optik")
        sec = await _create_section(client, unit["id"], "Einführung")

        # Switch to non-author
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{sec['id']}", json={}
        )
        assert resp.status_code in (403, 404), resp.text

