"""
Cache-Control and CSP hardening tests.

Ensures sensitive API responses are not cached and production CSP avoids
unsafe-inline in `script-src` to reduce XSS surface.

Note:
    The current UI uses inline styles (style attributes + JS style mutations)
    and HTMX injects a small <style> block by default. Therefore `style-src`
    currently needs `'unsafe-inline'` even in production.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def session_store(monkeypatch: pytest.MonkeyPatch):
    """Install an isolated in-memory app session store for one cache-header test."""

    return install_session_store(monkeypatch, main)


@pytest.mark.anyio
async def test_courses_list_includes_private_no_store_cache_header(session_store):
    sess = session_store.create(sub="t-cache-1", name="Teacher", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/api/teaching/courses", params={"limit": 1, "offset": 0})

    assert r.status_code == 200
    cc = r.headers.get("Cache-Control", "")
    assert "private" in cc and "no-store" in cc


@pytest.mark.anyio
async def test_prod_csp_omits_unsafe_inline_and_sets_hsts():
    # Switch to prod and assert CSP keeps scripts strict.
    main.RUNTIME.settings.override_environment("prod")
    try:
        async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            r = await c.get("/health")
        assert r.status_code == 200
        csp = r.headers.get("Content-Security-Policy", "")
        assert csp

        # Scripts: strict (no inline, no eval).
        assert "script-src 'self'" in csp
        assert "unsafe-inline" not in csp.split("script-src", 1)[1].split(";", 1)[0]
        assert "unsafe-eval" not in csp

        # Styles: pragmatically allow inline due to current UI constraints.
        assert "style-src 'self' 'unsafe-inline'" in csp

        # Regression guard: ensure common CSP sources are syntactically valid.
        # In particular, `img-src` must allow `data:` with the colon (no stray quotes).
        assert "img-src 'self' data:" in csp
        assert "img-src 'self' data'" not in csp
        # HSTS should be set in prod (covered elsewhere, re-assert here for completeness)
        assert "Strict-Transport-Security" in r.headers
    finally:
        main.RUNTIME.settings.override_environment(None)


@pytest.mark.anyio
async def test_teaching_task_create_sets_private_no_store_cache_header(session_store):
    import routes.teaching as teaching  # type: ignore

    # Force in-memory repo to avoid DB dependencies for this header contract.
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]

    sess = session_store.create(sub="t-task-cache-create", name="Teacher", roles=["teacher"])
    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)

        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Section"})).json()

        r = await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "Task"},
        )
    assert r.status_code == 201
    cc = r.headers.get("Cache-Control", "")
    assert "private" in cc and "no-store" in cc


@pytest.mark.anyio
async def test_teaching_task_update_sets_private_no_store_cache_header(session_store):
    import routes.teaching as teaching  # type: ignore

    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]

    sess = session_store.create(sub="t-task-cache-update", name="Teacher", roles=["teacher"])
    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)

        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Section"})).json()
        created = (
            await c.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
                json={"instruction_md": "Task"},
            )
        ).json()

        r = await c.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{created['id']}",
            json={"instruction_md": "Updated"},
        )
    assert r.status_code == 200
    cc = r.headers.get("Cache-Control", "")
    assert "private" in cc and "no-store" in cc
