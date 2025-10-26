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


UNIT_ID = "u1"  # vorbefüllte Dummy-Einheit in main._DUMMY_UNITS_STORE


async def _create_section_via_ui(client: httpx.AsyncClient, *, unit_id: str, title: str, csrf_token: str) -> str:
    resp = await client.post(
        f"/units/{unit_id}/sections",
        data={"title": title, "csrf_token": csrf_token},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    # Der Handler liefert das aktualisierte List-Fragment zurück.
    # Finde die section-ID, die zum gerade angelegten Titel gehört.
    pattern = r'<div class=\"card section-card\" id=\"section_([a-f0-9\-]+)\"[\s\S]*?</div>\s*</div>\s*</div>'
    m = None
    for block in re.finditer(pattern, resp.text, re.S):
        if f'<h4 class=\"card-title\">{re.escape(title)}<' in re.sub(r"\\s+", " ", block.group(0)):
            m = block
            break
    assert m, f"no section id found for title {title!r} in: {resp.text[:500]}"
    # type: ignore[union-attr]
    return m.group(1)  # noqa: E1101


def _find_section_id_by_title(html: str, title: str) -> str | None:
    pattern = r'<div class=\"card section-card\" id=\"section_([a-f0-9\-]+)\"[\s\S]*?</div>\s*</div>\s*</div>'
    for m in re.finditer(pattern, html, re.S):
        block = m.group(0)
        if f'<h4 class=\"card-title\">{title}<' in block:
            return m.group(1)
    return None


@pytest.mark.anyio
async def test_sections_page_renders_wrapper_and_sortable():
    # Arrange: Lehrer-Session und eine Lerneinheit
    sess = main.SESSION_STORE.create(sub="t-ui-sec-1", name="Lehrer S", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # Act: Seite der Dummy-Einheit abrufen
        page = await c.get(f"/units/{UNIT_ID}")

    assert page.status_code == 200
    html = page.text
    assert 'id="section-list-section"' in html  # Wrapper vorhanden
    assert 'hx-ext="sortable"' in html          # Sortable aktiviert (Client-Skript separat)


@pytest.mark.anyio
async def test_sections_delete_returns_wrapper_and_removes_item():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-2", name="Lehrer D", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        # CSRF besorgen aus Dummy-Einheit
        get_r = await c.get(f"/units/{UNIT_ID}")
        token = _extract_csrf_token(get_r.text) or ""

        # Zwei Abschnitte anlegen
        a_id = await _create_section_via_ui(c, unit_id=UNIT_ID, title="Alpha", csrf_token=token)
        b_id = await _create_section_via_ui(c, unit_id=UNIT_ID, title="Beta", csrf_token=token)

        # Act: Alpha löschen
        del_r = await c.post(
            f"/units/{UNIT_ID}/sections/{a_id}/delete",
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
        # CSRF besorgen aus Dummy-Einheit
        get_r = await c.get(f"/units/{UNIT_ID}")
        token = _extract_csrf_token(get_r.text) or ""

        # Zwei Abschnitte (Alpha, Beta) erzeugen
        # Erzeugen
        await _create_section_via_ui(c, unit_id=UNIT_ID, title="Alpha", csrf_token=token)
        await _create_section_via_ui(c, unit_id=UNIT_ID, title="Beta", csrf_token=token)

        # IDs zuverlässig aus ganzer Seite extrahieren
        page_after = await c.get(f"/units/{UNIT_ID}")
        assert page_after.status_code == 200
        html_after = page_after.text
        alpha_id = _find_section_id_by_title(html_after, "Alpha") or ""
        beta_id = _find_section_id_by_title(html_after, "Beta") or ""
        assert alpha_id and beta_id
        assert alpha_id != beta_id

        # Act: Reihenfolge umdrehen – htmx-sortable sendet id=section_<id>
        form_body = f"id=section_{beta_id}&id=section_{alpha_id}"
        reorder_r = await c.post(
            f"/units/{UNIT_ID}/sections/reorder",
            content=form_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
            },
        )
        assert reorder_r.status_code in (200, 204)

        # Assert: Seite neu laden und prüfen, ob 'Beta' vor 'Alpha' steht
        page = await c.get(f"/units/{UNIT_ID}")
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
        initial = await c.get(f"/units/{UNIT_ID}")
        assert initial.status_code == 200
        initial_html = initial.text
        assert 'hx-ext="sortable"' in initial_html
        # Zähle initiale Karten
        initial_count = len(re.findall(r'<div class=\"card section-card\" id=\"section_', initial_html))
        assert initial_count >= 1

        token = _extract_csrf_token(initial_html) or ""
        # Abschnitt hinzufügen
        create_r = await c.post(
            f"/units/{UNIT_ID}/sections",
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
async def test_sections_reorder_requires_csrf_and_accepts_header():
    sess = main.SESSION_STORE.create(sub="t-ui-sec-5", name="Lehrer CSRF", roles=["teacher"])  # type: ignore
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, sess.session_id)
        page = await c.get(f"/units/{UNIT_ID}")
        assert page.status_code == 200
        token = _extract_csrf_token(page.text) or ""

        # Mindestens zwei Einträge sicherstellen
        await _create_section_via_ui(c, unit_id=UNIT_ID, title="C1", csrf_token=token)
        await _create_section_via_ui(c, unit_id=UNIT_ID, title="C2", csrf_token=token)

        page2 = await c.get(f"/units/{UNIT_ID}")
        html2 = page2.text
        id1 = _find_section_id_by_title(html2, "C1") or ""
        id2 = _find_section_id_by_title(html2, "C2") or ""
        assert id1 and id2 and id1 != id2

        # Ohne CSRF → 403
        r_forbidden = await c.post(
            f"/units/{UNIT_ID}/sections/reorder",
            content=f"id=section_{id2}&id=section_{id1}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r_forbidden.status_code == 403

        # Mit Header-Token → 200/204
        r_ok = await c.post(
            f"/units/{UNIT_ID}/sections/reorder",
            content=f"id=section_{id2}&id=section_{id1}",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-Token": token,
            },
        )
        assert r_ok.status_code in (200, 204)


@pytest.mark.anyio
async def test_sections_page_supports_repo_created_unit_and_allows_create():
    """
    Given a teacher creates a unit via the Teaching API (Repo)
    When they open /units/{unit_id}
    Then the dummy sections UI renders (wrapper present) and creating a section works.
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
