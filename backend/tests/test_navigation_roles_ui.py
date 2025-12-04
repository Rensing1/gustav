"""
Sidebar navigation (rollenbasiert) – TDD: RED first

Verifiziert Sichtbarkeit, Reihenfolge und aktive Zustände für Schüler/Lehrer.
Zusätzlich Smoke-Tests für neue Platzhalterseiten (/about, /units) und
HTMX-OOB-Sidebar-Update.
"""

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


# Ensure tests use the in-memory session store – avoids DB dependency when
# running unit/contract tests locally.
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensive
    main.SESSION_STORE = SessionStore()

def _pos(html: str, label: str) -> int:
    """Return the index of a sidebar label within nav-text span.

    Keeps tests resilient to markup changes outside of the nav-text span.
    """
    token = f'nav-text">{label}'
    return html.find(token)


@pytest.mark.anyio
async def test_sidebar_for_student_contains_expected_items_in_order():
    # Arrange: authenticated session with student role
    sess = main.SESSION_STORE.create(sub="s-1", name="Schülerin A", roles=["student"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/")

    assert r.status_code == 200
    html = r.text

    # Order: Startseite -> Meine Kurse -> Über GUSTAV
    p_home = _pos(html, "Startseite")
    p_courses = _pos(html, "Meine Kurse")
    p_about = _pos(html, "Über GUSTAV")
    assert p_home != -1 and p_courses != -1 and p_about != -1
    assert p_home < p_courses < p_about

    # Removed items should not appear
    forbidden = [
        "Dashboard", "Wissenschaft", "Karteikarten", "Fortschritt",
        "Einstellungen", "Analytics", "Schüler", "Inhalte erstellen",
    ]
    for label in forbidden:
        assert _pos(html, label) == -1

    # Active state on home
    assert '<a href="/"' in html
    home_link_fragment = html.split('<a href="/"', 1)[1].split('</a>', 1)[0]
    assert 'aria-current="page"' in home_link_fragment
    assert 'sidebar-link active' in home_link_fragment


@pytest.mark.anyio
async def test_sidebar_for_teacher_contains_expected_items_in_order():
    # Arrange: authenticated session with teacher role
    sess = main.SESSION_STORE.create(sub="t-1", name="Lehrer B", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/")

    assert r.status_code == 200
    html = r.text

    # Order: Startseite -> Kurse -> Lerneinheiten -> Über GUSTAV
    p_home = _pos(html, "Startseite")
    p_courses = _pos(html, "Kurse")
    p_units = _pos(html, "Lerneinheiten")
    p_about = _pos(html, "Über GUSTAV")
    assert p_home != -1 and p_courses != -1 and p_units != -1 and p_about != -1
    assert p_home < p_courses < p_units < p_about

    forbidden = [
        "Dashboard", "Wissenschaft", "Karteikarten", "Fortschritt",
        "Einstellungen", "Analytics", "Schüler", "Inhalte erstellen",
    ]
    for label in forbidden:
        # Only check sidebar labels (nav-text), not arbitrary page content.
        assert _pos(html, label) == -1


@pytest.mark.anyio
async def test_sidebar_unknown_role_falls_back_to_minimal_menu():
    # Arrange: unknown/unsupported role -> minimal: Startseite, Über GUSTAV
    sess = main.SESSION_STORE.create(sub="u-1", name="User C", roles=["guest"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/")

    assert r.status_code == 200
    html = r.text
    assert _pos(html, "Startseite") != -1
    assert _pos(html, "Über GUSTAV") != -1
    # Should not show role-specific items
    assert _pos(html, "Meine Kurse") == -1
    assert _pos(html, "Kurse") == -1
    assert _pos(html, "Lerneinheiten") == -1


@pytest.mark.anyio
async def test_htmx_request_includes_sidebar_oob_update():
    sess = main.SESSION_STORE.create(sub="s-2", name="Schüler D", roles=["student"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r = await c.get("/", headers={"HX-Request": "true"})

    assert r.status_code == 200
    assert 'hx-swap-oob="true"' in r.text


@pytest.mark.anyio
async def test_placeholder_pages_exist_about_and_units():
    # These pages should be SSR pages returning HTML 200
    sess = main.SESSION_STORE.create(sub="t-2", name="Lehrer E", roles=["teacher"])
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        r_about = await c.get("/about")
        r_units = await c.get("/units")

    assert r_about.status_code == 200
    assert r_units.status_code == 200
    assert "GUSTAV" in r_about.text
    assert "GUSTAV" in r_units.text
