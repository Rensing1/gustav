"""
Sidebar toggle state sync after HTMX navigation – RED

Validates that HTMX responses only deliver the main-content fragment plus a
single out-of-band sidebar. Guards against regressions that render duplicate
sidebar containers and break the toggle logic.
"""

from pathlib import Path
import sys

import pytest
import httpx
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from identity_access.stores import SessionStore  # noqa: E402
import main  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


# Ensure we are using the in-memory session store so test isolation holds.
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()


async def _create_teacher_session() -> str:
    """Create a teacher session and return the session id."""
    record = main.SESSION_STORE.create(sub="teacher-1", name="LehrerIn", roles=["teacher"])
    return record.session_id


@pytest.mark.anyio
async def test_htmx_courses_response_returns_fragment_without_duplicate_sidebar():
    # Arrange: authenticated teacher with sidebar access.
    session_id = await _create_teacher_session()

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session_id)

        response = await client.get("/courses", headers={"HX-Request": "true"})

    assert response.status_code == 200
    html = response.text

    # Expect fragment response: no DOCTYPE/body wrapper.
    assert "<!DOCTYPE html>" not in html
    assert 'id="main-content"' not in html
    assert 'class="breadcrumb"' in html

    # Sidebar must only appear once and be flagged for OOB swap.
    assert html.count('id="sidebar"') == 1
    assert 'hx-swap-oob="true"' in html


@pytest.mark.anyio
async def test_full_page_load_still_includes_layout_and_single_sidebar():
    session_id = await _create_teacher_session()

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session_id)

        response = await client.get("/courses")

    assert response.status_code == 200
    html = response.text

    # Full layout render should still include the DOCTYPE and only a single sidebar.
    assert "<!DOCTYPE html>" in html
    assert html.count('id="sidebar"') == 1


@pytest.mark.anyio
async def test_htmx_request_without_session_redirects_to_login():
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/courses", headers={"HX-Request": "true"})

    assert response.status_code == 401
    assert response.headers.get("HX-Redirect") == "/auth/login"


@pytest.mark.anyio
async def test_courses_cache_control_private_no_store_by_default():
    # Personalized SSR pages must not be cached by shared caches.
    session_id = await _create_teacher_session()

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session_id)
        r_full = await client.get("/courses")
        r_htmx = await client.get("/courses", headers={"HX-Request": "true"})

    assert r_full.headers.get("Cache-Control") == "private, no-store"
    assert r_htmx.headers.get("Cache-Control") == "private, no-store"
