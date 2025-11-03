"""
SSR UI: /units/{unit_id} – Abschnitte verwalten (TDD: RED zuerst)

Ziel: UI-Flows für Abschnitte (Listen, Anlegen, Löschen, Umordnen) verlässlich machen.
Fokus: Wrapper-Zielknoten bleibt konsistent, Reorder akzeptiert id-Parameter
       wie von htmx-sortable gesendet (id=section_<id>), und CSRF bei Formularen.

Hinweis: Wir seeden die Lerneinheit über die Teaching-API. Abschnitte werden
über die SSR-UI-Route angelegt (sie nutzt aktuell einen In-Memory-Store).
"""

from __future__ import annotations

import html
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
from components.forms import SectionCreateForm  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


# Tests sollen keinen DB-Session-Store benötigen
if not isinstance(main.SESSION_STORE, SessionStore):  # pragma: no cover - defensiv
    main.SESSION_STORE = SessionStore()


def _extract_csrf_token(html: str) -> str | None:
    m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


async def _create_unit_via_api(client: httpx.AsyncClient, *, title: str) -> str:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body, dict) and body.get("id")
    return body["id"]


_SECTION_CARD_RE = re.compile(
    r'<div class="card section-card" id="section_([a-f0-9\-]+)"[^>]*>.*?<h4 class="card-title"><a[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _iter_section_cards(html_doc: str):
    """Yield (section_id, title) tuples for section cards in rendered HTML."""
    for match in _SECTION_CARD_RE.finditer(html_doc):
        section_id = match.group(1)
        raw_title = html.unescape(match.group(2)).strip()
        yield section_id, raw_title


async def _create_section_via_ui(client: httpx.AsyncClient, *, unit_id: str, title: str, csrf_token: str) -> str:
    resp = await client.post(
        f"/units/{unit_id}/sections",
        data={"title": title, "csrf_token": csrf_token},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    # Der Handler liefert das aktualisierte List-Fragment zurück.
    # Finde die section-ID, die zum gerade angelegten Titel gehört.
    for section_id, card_title in _iter_section_cards(resp.text):
        if card_title == title:
            return section_id
    assert False, f"no section id found for title {title!r} in: {resp.text[:500]}"


def _find_section_id_by_title(html: str, title: str) -> str | None:
    for section_id, card_title in _iter_section_cards(html):
        if card_title == title:
            return section_id
    return None


@pytest.mark.anyio
async def test_sections_page_renders_wrapper_and_sortable():
    # Arrange: Lehrer-Session und eine Lerneinheit
    sess = main.SESSION_STORE.create(sub="t-ui-sec-1", name="Lehrer S", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-1")
        page = await c.get(f"/units/{unit_id}")

    assert page.status_code == 200
    html = page.text
    assert 'id="section-list-section"' in html  # Wrapper vorhanden
    assert 'hx-ext="sortable"' in html          # Sortable aktiviert (Client-Skript separat)


@pytest.mark.anyio
async def test_sections_delete_returns_wrapper_and_removes_item():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-2", name="Lehrer D", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-2")
        get_r = await c.get(f"/units/{unit_id}")
        token = _extract_csrf_token(get_r.text) or ""

        # Zwei Abschnitte anlegen
        a_id = await _create_section_via_ui(c, unit_id=unit_id, title="Alpha", csrf_token=token)
        b_id = await _create_section_via_ui(c, unit_id=unit_id, title="Beta", csrf_token=token)

        # Act: Alpha löschen
        del_r = await c.post(
            f"/units/{unit_id}/sections/{a_id}/delete",
            data={"csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert del_r.status_code == 200
    body = del_r.text
    # Wrapper muss weiterhin vorhanden sein, damit weitere Updates funktionieren
    assert 'id="section-list-section"' in body
    assert "Alpha" not in body and "Beta" in body


@pytest.mark.anyio
async def test_sections_reorder_accepts_id_param_and_changes_order():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-3", name="Lehrer R", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-3")
        get_r = await c.get(f"/units/{unit_id}")
        token = _extract_csrf_token(get_r.text) or ""

        # Zwei Abschnitte (Alpha, Beta) erzeugen
        # Erzeugen
        await _create_section_via_ui(c, unit_id=unit_id, title="Alpha", csrf_token=token)
        await _create_section_via_ui(c, unit_id=unit_id, title="Beta", csrf_token=token)

        # IDs zuverlässig aus ganzer Seite extrahieren
        page_after = await c.get(f"/units/{unit_id}")
        assert page_after.status_code == 200
        html_after = page_after.text
        alpha_id = _find_section_id_by_title(html_after, "Alpha") or ""
        beta_id = _find_section_id_by_title(html_after, "Beta") or ""
        assert alpha_id and beta_id
        assert alpha_id != beta_id

        # Act: Reihenfolge umdrehen – htmx-sortable sendet id=section_<id>
        form_body = f"id=section_{beta_id}&id=section_{alpha_id}"
        reorder_r = await c.post(
            f"/units/{unit_id}/sections/reorder",
            content=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
            },
        )
        assert reorder_r.status_code in (200, 204)

        # Assert: Seite neu laden und prüfen, ob 'Beta' vor 'Alpha' steht
        page = await c.get(f"/units/{unit_id}")
        html = page.text
        assert page.status_code == 200

        beta_pos = html.find("Beta")
        alpha_pos = html.find("Alpha")
        assert 0 <= beta_pos < alpha_pos, html


@pytest.mark.anyio
async def test_sections_create_preserves_existing_and_sortable_stays_active():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-4", name="Lehrer C", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-4")
        initial = await c.get(f"/units/{unit_id}")
        assert initial.status_code == 200
        initial_html = initial.text
        assert 'hx-ext="sortable"' in initial_html
        # Zähle initiale Karten
        initial_count = len(re.findall(r'<div class=\"card section-card\" id=\"section_', initial_html))
        assert initial_count >= 0

        token = _extract_csrf_token(initial_html) or ""
        # Abschnitt hinzufügen
        create_r = await c.post(
            f"/units/{unit_id}/sections",
            data={"title": "Gamma", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert create_r.status_code == 200
        body = create_r.text
        # Wrapper weiterhin vorhanden und sortable weiter aktiv
        assert 'id="section-list-section"' in body
        assert 'hx-ext="sortable"' in body
        # Vorherige Abschnitte verschwinden nicht – Anzahl >= initial_count
        new_count = len(re.findall(r'<div class=\"card section-card\" id=\"section_', body))
        assert new_count >= initial_count


@pytest.mark.anyio
async def test_sections_create_invalid_title_returns_error_fragment():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-4b", name="Lehrer CE", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-4b")
        page = await c.get(f"/units/{unit_id}")
        token = _extract_csrf_token(page.text) or ""

        resp = await c.post(
            f"/units/{unit_id}/sections",
            data={"title": "   ", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded", "HX-Request": "true"},
        )

    assert resp.status_code == 200
    assert "invalid_title" in resp.text
    assert "form-error" in resp.text


@pytest.mark.anyio
async def test_section_cards_link_to_detail_page():
    # Arrange
    sess = main.SESSION_STORE.create(sub="t-ui-sec-link-1", name="Lehrer L", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        import routes.teaching as teaching  # type: ignore
        teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-Link")
        page = await c.get(f"/units/{unit_id}")
        token = _extract_csrf_token(page.text) or ""
        # Create a section via UI
        create_r = await c.post(
            f"/units/{unit_id}/sections",
            data={"title": "Erster Abschnitt", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert create_r.status_code == 200

        # Load updated page and find section id by title
        page2 = await c.get(f"/units/{unit_id}")
        html2 = page2.text
        sid = _find_section_id_by_title(html2, "Erster Abschnitt") or ""
        assert sid, html2
        # Expect an anchor to the detail view
        assert f' href="/units/{unit_id}/sections/{sid}"' in html2


@pytest.mark.anyio
async def test_sections_reorder_requires_csrf_and_accepts_header():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-5", name="Lehrer CSRF", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-5")
        page = await c.get(f"/units/{unit_id}")
        assert page.status_code == 200
        token = _extract_csrf_token(page.text) or ""

        # Mindestens zwei Einträge sicherstellen
        await _create_section_via_ui(c, unit_id=unit_id, title="C1", csrf_token=token)
        await _create_section_via_ui(c, unit_id=unit_id, title="C2", csrf_token=token)

        page2 = await c.get(f"/units/{unit_id}")
        html2 = page2.text
        id1 = _find_section_id_by_title(html2, "C1") or ""
        id2 = _find_section_id_by_title(html2, "C2") or ""
        assert id1 and id2 and id1 != id2

        # Ohne CSRF → 403
        r_forbidden = await c.post(
            f"/units/{unit_id}/sections/reorder",
            content=f"id=section_{id2}&id=section_{id1}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r_forbidden.status_code == 403

        # Mit Header-Token → 200/204
        r_ok = await c.post(
            f"/units/{unit_id}/sections/reorder",
            content=f"id=section_{id2}&id=section_{id1}",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
            },
        )
        assert r_ok.status_code in (200, 204)


@pytest.mark.anyio
async def test_sections_reorder_calls_api_for_db_unit():
    """
    SSR reorder should call the API reorder for DB-backed units when IDs are UUID-like.
    We verify by creating sections via API, calling the SSR reorder endpoint with
    DOM-style ids, and then asserting the API list reflects the new order.
    """
    from utils.db import require_db_or_skip as _require_db_or_skip
    _require_db_or_skip()
    try:
        import routes.teaching as teaching  # noqa: F401
    except Exception:
        pytest.skip("Teaching routes unavailable")

    sess = main.SESSION_STORE.create(sub="t-ui-sec-6-db", name="Lehrer DB", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # Create unit and two sections via API
        r_unit = await c.post("/api/teaching/units", json={"title": "DB-Unit"})
        assert r_unit.status_code == 201
        uid = r_unit.json()["id"]
        a = (await c.post(f"/api/teaching/units/{uid}/sections", json={"title": "Alpha"})).json()
        b = (await c.post(f"/api/teaching/units/{uid}/sections", json={"title": "Beta"})).json()

        # Get CSRF token from SSR page (token only; list is dummy)
        page = await c.get(f"/units/{uid}")
        assert page.status_code == 200
        token = _extract_csrf_token(page.text) or ""

        # Call SSR reorder with DOM-style ids: Beta first, then Alpha
        form_body = f"id=section_{b['id']}&id=section_{a['id']}"
        r_reorder = await c.post(
            f"/units/{uid}/sections/reorder",
            content=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
            },
        )
        assert r_reorder.status_code in (200, 204)

        # API must reflect Beta before Alpha now
        lst = await c.get(f"/api/teaching/units/{uid}/sections")
        assert lst.status_code == 200
    ids = [s["id"] for s in lst.json()]
    assert ids[:2] == [b["id"], a["id"]]


@pytest.mark.anyio
async def test_sections_delete_unknown_section_returns_error_fragment():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-del-err", name="Lehrer DEL", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-DelErr")
        page = await c.get(f"/units/{unit_id}")
        token = _extract_csrf_token(page.text) or ""

        resp = await c.post(
            f"/units/{unit_id}/sections/not-real/delete",
            data={"csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded", "HX-Request": "true"},
        )

    assert resp.status_code == 200
    assert "section-error" in resp.text
    assert "not_found" in resp.text


@pytest.mark.anyio
async def test_sections_reorder_invalid_ids_returns_error_response():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-reorder-err", name="Lehrer RE", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        unit_id = await _create_unit_via_api(c, title="UI-Unit-ReorderErr")
        page = await c.get(f"/units/{unit_id}")
        token = _extract_csrf_token(page.text) or ""

        a = await _create_section_via_ui(c, unit_id=unit_id, title="Alpha", csrf_token=token)
        await _create_section_via_ui(c, unit_id=unit_id, title="Beta", csrf_token=token)

        resp = await c.post(
            f"/units/{unit_id}/sections/reorder",
            content=f"id=section_{a}&id=section_notreal",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
            },
        )

    assert resp.status_code == 400
    payload = resp.json()
    assert payload.get("detail") == "invalid_section_ids"


@pytest.mark.anyio
async def test_sections_page_supports_repo_created_unit_and_allows_create():
    """
    Given a teacher creates a unit via the Teaching API (Repo)
    When they open /units/{unit_id}
    Then the sections UI renders (wrapper present) and creating a section works.
    """
    # Arrange: authenticated teacher session
    sess = main.SESSION_STORE.create(sub="t-ui-sec-6", name="Lehrer RepoUnit", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        # Seed a unit via API to ensure its id comes from the Repo, not dummy store
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        create_resp = await c.post("/api/teaching/units", json={"title": "Repo-Unit"})
        assert create_resp.status_code == 201, create_resp.text
        unit_id = create_resp.json().get("id")
        assert unit_id, "API did not return a unit id"

        # Act: open the sections management page for that repo-created unit
        page = await c.get(f"/units/{unit_id}")
        assert page.status_code == 200
        html = page.text
        assert 'id="section-list-section"' in html  # wrapper present means dummy UI rendered

        # Extract CSRF and create a first section via the dummy UI
        token = _extract_csrf_token(html) or ""
        create_ui = await c.post(
            f"/units/{unit_id}/sections",
            data={"title": "Delta", "csrf_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert create_ui.status_code == 200
        assert "Delta" in create_ui.text


@pytest.mark.anyio
async def test_section_create_form_escapes_unit_id_and_sets_method_action():
    """SectionCreateForm must escape the unit identifier and provide method/action for accessibility."""
    malicious_unit_id = 'unit_<script>alert(1)</script>'
    form = SectionCreateForm(unit_id=malicious_unit_id, csrf_token="csrf123")
    markup = form.render()
    escaped_id = html.escape(malicious_unit_id, quote=True)
    expected_hx_post = f'hx-post="/units/{escaped_id}/sections"'
    expected_action = f'action="/units/{escaped_id}/sections"'
    assert expected_hx_post in markup, "hx-post attribute must escape the unit identifier"
    assert expected_action in markup, "Form action must escape the unit identifier"
    form_tag = re.search(r'<form[^>]+>', markup)
    assert form_tag, "Form element should be rendered"
    assert 'method="post"' in form_tag.group(0), "Section create form must declare method=post for non-HTMX fallback"
