"""Layout fragment contracts for the retained legacy retirement shell."""

import importlib

import pytest
import httpx
from httpx import ASGITransport


from backend.tests.runtime_auth_helpers import install_session_store
from backend.web.components import Layout

main = importlib.import_module("backend.web.main")


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def session_store(monkeypatch: pytest.MonkeyPatch):
    """Install an isolated in-memory app session store for one sidebar test."""

    return install_session_store(monkeypatch, main)


async def _create_teacher_session(session_store) -> str:
    """Create a teacher session and return the session id."""
    record = session_store.create(sub="teacher-1", name="LehrerIn", roles=["teacher"])
    return record.session_id


@pytest.mark.anyio
async def test_layout_fragment_returns_content_without_duplicate_sidebar(session_store):
    user = {"sub": "teacher-1", "name": "Test Teacher", "role": "teacher", "roles": ["teacher"]}
    layout = Layout(title="Retired", content="<p>Retired content</p>", user=user, current_path="/units")
    html = layout.render_fragment()

    # Expect fragment response: no DOCTYPE/body wrapper.
    assert "<!DOCTYPE html>" not in html
    assert 'id="main-content"' not in html
    assert "Retired content" in html

    # Sidebar must only appear once and be flagged for OOB swap.
    assert html.count('id="sidebar"') == 1
    assert 'hx-swap-oob="true"' in html


@pytest.mark.anyio
async def test_layout_full_render_still_includes_single_sidebar(session_store):
    user = {"sub": "teacher-1", "name": "Test Teacher", "role": "teacher", "roles": ["teacher"]}
    layout = Layout(title="Retired", content="<p>Retired content</p>", user=user, current_path="/units")
    html = layout.render()

    # Full layout render should still include the DOCTYPE and only a single sidebar.
    assert "<!DOCTYPE html>" in html
    assert html.count('id="sidebar"') == 1


@pytest.mark.anyio
async def test_retired_legacy_page_cache_control_private_no_store_by_default(session_store):
    # Retired personalized HTML pages must not be cached by shared caches.
    session_id = await _create_teacher_session(session_store)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, session_id)
        r_full = await client.get("/units")
        r_htmx = await client.get("/units", headers={"HX-Request": "true"})

    assert r_full.status_code == 410
    assert r_htmx.status_code == 410
    assert r_full.headers.get("Cache-Control") == "private, no-store"
    assert r_htmx.headers.get("Cache-Control") == "private, no-store"
