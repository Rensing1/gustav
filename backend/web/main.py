"GUSTAV alpha-2"
from pathlib import Path
import os
import logging
import uuid
import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Component Imports
from components import Layout, CourseCreateForm, UnitCreateForm, SectionCreateForm
from components.base import Component
from components.navigation import Navigation
from components.pages import SciencePage
from components.forms.course_edit_form import CourseEditForm

# Auth & OIDC Imports
from identity_access.oidc import OIDCClient, OIDCConfig
from identity_access.stores import StateStore, SessionStore
from identity_access.domain import ALLOWED_ROLES
from identity_access.tokens import IDTokenVerificationError, verify_id_token

try:
    from .auth_utils import cookie_opts
except ImportError:
    from auth_utils import cookie_opts

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- App & Settings Setup -------------------------------------------------------

class AuthSettings:
    def __init__(self) -> None:
        self._env_override: str | None = None

    @property
    def environment(self) -> str:
        if self._env_override is not None:
            return self._env_override
        return os.getenv("GUSTAV_ENV", "dev").lower()

    def override_environment(self, env: str | None) -> None:
        """Override environment for tests (e.g., "prod"), or reset with None."""
        self._env_override = env

logger = logging.getLogger("gustav.identity_access")
SETTINGS = AuthSettings()
SESSION_COOKIE_NAME = "gustav_session"

app = FastAPI(title="GUSTAV alpha-2", description="KI-gestützte Lernplattform", version="0.0.2")

# --- Static Files & Routers -----------------------------------------------------

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

from routes.auth import auth_router
from routes.learning import learning_router
from routes.teaching import teaching_router
from routes.users import users_router

# --- OIDC & Storage Setup ------------------------------------------------------

def load_oidc_config() -> OIDCConfig:
    base_url = os.getenv("KC_BASE_URL", "http://localhost:8080")
    realm = os.getenv("KC_REALM", "gustav")
    client_id = os.getenv("KC_CLIENT_ID", "gustav-web")
    redirect_uri = os.getenv("REDIRECT_URI", "http://app.localhost:8100/auth/callback")
    public_base = os.getenv("KC_PUBLIC_BASE_URL", base_url)
    return OIDCConfig(base_url=base_url, realm=realm, client_id=client_id, redirect_uri=redirect_uri, public_base_url=public_base)

OIDC_CFG = load_oidc_config()
OIDC = OIDCClient(OIDC_CFG)
STATE_STORE = StateStore()

if os.getenv("SESSIONS_BACKEND", "memory").lower() == "db":
    try:
        from identity_access.stores_db import DBSessionStore
        SESSION_STORE = DBSessionStore()
    except ImportError:
        SESSION_STORE = SessionStore()
else:
    SESSION_STORE = SessionStore()

# --- Auth Helpers & Middleware --------------------------------------------------

def _session_cookie_options() -> dict:
    return cookie_opts(SETTINGS.environment)

def _primary_role(roles: list[str]) -> str:
    priority = ["admin", "teacher", "student"]
    lowered = [r.lower() for r in roles if isinstance(r, str)]
    for r in priority:
        if r in lowered:
            return r
    return "student"

def _set_session_cookie(response: Response, value: str, *, max_age: int | None = None, request: Request | None = None) -> None:
    opts = _session_cookie_options()
    secure_flag = opts["secure"]
    samesite_flag = opts["samesite"]
    try:
        if SETTINGS.environment == "prod" and request is not None:
            host = request.headers.get("host") or request.url.hostname or ""
            xf_proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
            if ("localhost" in host or host.startswith("127.")) and xf_proto != "https":
                secure_flag = False
                samesite_flag = "lax"
    except Exception:
        pass
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=value,
        httponly=True,
        secure=secure_flag,
        samesite=samesite_flag,
        path="/",
        max_age=max_age if max_age is not None else None,
    )

def _is_public_path(path: str) -> bool:
    return path.startswith(("/auth/", "/static/")) or path in ("/health", "/favicon.ico")

@app.middleware("http")
async def auth_enforcement(request: Request, call_next):
    path = request.url.path
    if _is_public_path(path):
        return await call_next(request)

    sid = request.cookies.get(SESSION_COOKIE_NAME)
    rec = None
    if sid:
        try:
            rec = SESSION_STORE.get(sid)
        except Exception as exc:
            logger.warning("Session store get failed: %s", exc.__class__.__name__)

    if not rec:
        if path.startswith("/api/"):
            if path.startswith("/api/learning/"):
                cache = "private, max-age=0"
            elif path == "/api/me":
                cache = "no-store"
            else:
                cache = "no-store"
            return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": cache})
        if "HX-Request" in request.headers:
            return Response(status_code=401, headers={"HX-Redirect": "/auth/login"})
        return RedirectResponse(url="/auth/login", status_code=302)

    request.state.user = {"sub": rec.sub, "name": getattr(rec, "name", ""), "role": _primary_role(rec.roles), "roles": rec.roles}
    return await call_next(request)

# --- Security Headers Middleware ----------------------------------------------

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # Baseline defensive headers
    if SETTINGS.environment == "prod":
        # Harden CSP in production: avoid 'unsafe-inline' to reduce XSS surface.
        csp = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self' data:; connect-src 'self';"
        )
    else:
        # Developer experience: allow inline for local SSR templates/components.
        csp = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self' data:; connect-src 'self';"
        )
    response.headers.setdefault("Content-Security-Policy", csp)
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if SETTINGS.environment == "prod":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

# --- Dummy Data Stores ----------------------------------------------------------

_DUMMY_COURSES_STORE = [
    {"id": "c1", "title": "Mathematik 10a", "subject": "Mathematik", "grade_level": "10", "term": "2025/26"},
    {"id": "c2", "title": "Englisch Q1", "subject": "Englisch", "grade_level": "Q1", "term": "2025/26"},
]
_DUMMY_UNITS_STORE = [
    {"id": "u1", "title": "Einführung in die Algebra", "summary": "Grundlagen der Algebra für die Mittelstufe."},
    {"id": "u2", "title": "Shakespeare's Sonnets", "summary": "Analyse und Interpretation ausgewählter Sonette."},
]
_DUMMY_SECTIONS_STORE = {
    "u1": [
        {"id": "s1-1", "title": "Grundbegriffe"},
        {"id": "s1-2", "title": "Termumformungen"},
        {"id": "s1-3", "title": "Lineare Gleichungen"},
    ],
    "u2": [
        {"id": "s2-1", "title": "Historical Context"},
        {"id": "s2-2", "title": "Sonnet 18 Analysis"},
    ]
}
# Note: Members UI is fully API-backed. No dummy data here by design.

# --- CSRF & Pagination Helpers --------------------------------------------------

_CSRF_BY_SESSION: dict[str, str] = {}

def _get_session_id(request: Request) -> Optional[str]:
    return request.cookies.get(SESSION_COOKIE_NAME)

def _get_or_create_csrf_token(session_id: str) -> str:
    token = _CSRF_BY_SESSION.get(session_id)
    if not token:
        token = secrets.token_urlsafe(24)
        _CSRF_BY_SESSION[session_id] = token
    return token

def _validate_csrf(session_id: Optional[str], form_value: Optional[str]) -> bool:
    if not session_id or not form_value:
        return False
    expected = _CSRF_BY_SESSION.get(session_id)
    if not expected:
        return False
    import hmac
    return hmac.compare_digest(expected, str(form_value))

def _clamp_pagination(limit_raw: str | None, offset_raw: str | None) -> tuple[int, int]:
    try:
        limit = int(limit_raw) if limit_raw is not None else 20
    except (ValueError, TypeError):
        limit = 20
    try:
        offset = int(offset_raw) if offset_raw is not None else 0
    except (ValueError, TypeError):
        offset = 0
    return max(1, min(50, limit)), max(0, offset)

# --- Page Rendering Helpers -----------------------------------------------------

def _render_course_list_partial(items: list[dict], limit: int, offset: int, has_next: bool, *, csrf_token: str) -> str:
    """Render the course list within a stable wrapper element.

    Always renders a section with id="course-list-section" so HTMX targets are
    available even when the list is empty. This prevents no-op updates when
    creating the very first course via hx-post.
    """
    cards = []
    for c in items:
        cards.append(f'''
        <div class="card course-card" data-course-id="{c.get("id", "")}">
            <div class="card-body">
                <h3 class="card-title"><a href="/courses/{c.get("id")}">{Component.escape(c.get("title"))}</a></h3>
                <div class="card-meta">
                    <span><strong>Fach:</strong> {Component.escape(c.get("subject"))}</span>
                    <span><strong>Stufe:</strong> {Component.escape(c.get("grade_level"))}</span>
                </div>
                <div class="card-actions">
                    <a href="/courses/{c.get("id")}/edit" class="btn btn-secondary">Bearbeiten</a>
                    <a href="/courses/{c.get("id")}/members" class="btn btn-secondary">Mitglieder</a>
                    <form hx-post="/courses/{c.get("id")}/delete" hx-target="#course-list-section" hx-swap="outerHTML" style="display: inline;">
                        <input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">
                        <button type="submit" class="btn btn-danger">Löschen</button>
                    </form>
                </div>
            </div>
        </div>
        ''')
    list_html = "\n".join(cards)
    pager_html = []
    prev_disabled = offset <= 0
    prev_href = f"/courses?limit={limit}&offset={max(0, offset - limit)}"
    next_href = f"/courses?limit={limit}&offset={offset + limit}"
    disabled_attr = 'aria-disabled="true"' if prev_disabled else ''
    pager_html.append(
        f'<a data-testid="pager-prev" href="{prev_href}" class="pager-link" {disabled_attr}>Zurück</a>'
    )
    if has_next:
        pager_html.append(f'<a data-testid="pager-next" href="{next_href}" class="pager-link">Weiter</a>')
    pager = f"<nav class=\"pager\">{' '.join(pager_html)}</nav>" if cards else ""
    inner = (
        f'<div class="course-list">{list_html}</div>{pager}' if cards else '<div class="empty-state"><p>Noch keine Kurse vorhanden.</p></div>'
    )
    return (
        f'<section class="course-list-section" id="course-list-section" aria-labelledby="course-list-heading">'
        f'<h2 id="course-list-heading" class="sr-only">Kursliste</h2>'
        f'{inner}'
        f'</section>'
    )

def _render_courses_page_html(request: Request, items: list[dict], *, csrf_token: str, limit: int, offset: int, has_next: bool, error: str | None = None) -> str:
    form_component = CourseCreateForm(csrf_token=csrf_token, error=error)
    form_html = form_component.render()
    course_list_html = _render_course_list_partial(items, limit, offset, has_next, csrf_token=csrf_token)
    return f'''
        <div class="container">
            <h1 id="courses-heading">Meine Kurse</h1>
            <section class="card create-course-section" aria-labelledby="create-course-heading" id="create-course-form-container">
                <h2 id="create-course-heading">Neuen Kurs erstellen</h2>
                {form_html}
            </section>
            {course_list_html}
        </div>
    '''

@app.get("/courses/{course_id}/edit", response_class=HTMLResponse)
async def courses_edit_form(request: Request, course_id: str):
    """Render the course edit form populated from API when possible.

    Permissions: Caller must be a teacher and (ideally) owner; we keep UI open
    but the API PATCH will enforce ownership.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    # Prefill current values via direct GET /api/teaching/courses/{id}
    values: dict[str, str] = {}
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            r = await client.get(f"/api/teaching/courses/{course_id}")
            if r.status_code == 200 and isinstance(r.json(), dict):
                it = r.json()
                for k in ("title", "subject", "grade_level", "term"):
                    if it.get(k) is not None:
                        values[k] = str(it.get(k))
    except Exception:
        pass
    form_component = CourseEditForm(course_id=course_id, csrf_token=token, values=values)
    content = f'<div class="container"><h1>Kurs bearbeiten</h1><section class="card">{form_component.render()}</section></div>'
    layout = Layout(title="Kurs bearbeiten", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})

@app.post("/courses/{course_id}/edit", response_class=HTMLResponse)
async def courses_edit_submit(request: Request, course_id: str):
    """Submit course updates via API PATCH then PRG back to /courses.

    Security: CSRF at UI; ownership via API + RLS.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse(content="CSRF Error", status_code=403)
    payload = {
        "title": (str(form.get("title", "")).strip() or None),
        "subject": (str(form.get("subject", "")).strip() or None),
        "grade_level": (str(form.get("grade_level", "")).strip() or None),
        "term": (str(form.get("term", "")).strip() or None),
    }
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            await client.patch(f"/api/teaching/courses/{course_id}", json=payload)
    except Exception:
        pass
    return RedirectResponse(url="/courses", status_code=303)

def _render_unit_list_partial(items: list[dict]) -> str:
    cards = []
    for u in items:
        cards.append(f'''
        <div class="card unit-card" data-unit-id="{u.get("id", "")}">
            <div class="card-body">
                <h3 class="card-title"><a href="/units/{u.get("id")}">{Component.escape(u.get("title"))}</a></h3>
                <p class="text-muted">{Component.escape(u.get("summary"))}</p>
                <div class="card-actions">
                    <a href="/units/{u.get("id")}/edit" class="btn btn-secondary">Umbenennen</a>
                    <a href="/units/{u.get("id")}" class="btn btn-primary">Abschnitte verwalten</a>
                </div>
            </div>
        </div>
        ''')
    joined_cards = "\n".join(cards)
    if cards:
        inner = f'<div class="unit-list">{joined_cards}</div>'
    else:
        inner = '<div class="empty-state"><p>Noch keine Lerneinheiten vorhanden.</p></div>'
    return f'<section id="unit-list-section">{inner}</section>'

def _render_units_page_html(items: list[dict], csrf_token: str, error: str | None = None) -> str:
    from components import UnitCreateForm
    form_component = UnitCreateForm(csrf_token=csrf_token, error=error)
    create_form_html = form_component.render()
    unit_list_html = _render_unit_list_partial(items)
    return f'''
        <div class="container">
            <h1 id="units-heading">Lerneinheiten</h1>
            <section class="card create-unit-section" id="create-unit-form-container">
                <h2 id="create-unit-heading">Neue Lerneinheit erstellen</h2>
                {create_form_html}
            </section>
            {unit_list_html}
        </div>
    '''

def _render_section_list_partial(unit_id: str, sections: list[dict], csrf_token: str) -> str:
    """Render the section list including its stable wrapper container.

    The outer wrapper has id="section-list-section" and is the HX target for create/delete updates.
    Inside, a div.section-list holds sortable items with ids "section_<id>" so the sortable
    extension can submit an ordered list via form parameter name "id".
    """
    items: list[str] = []
    for section in sections:
        items.append(f'''
        <div class="card section-card" id="section_{section.get("id")}" data-section-id="{section.get("id")}">
            <div class="card-body">
                <span class="drag-handle">☰</span>
                <h4 class="card-title">{Component.escape(section.get("title"))}</h4>
                <div class="card-actions">
                    <form hx-post="/units/{unit_id}/sections/{section.get("id")}/delete" hx-target="#section-list-section" hx-swap="outerHTML">
                        <input type="hidden" name="csrf_token" value="{csrf_token}">
                        <button type="submit" class="btn btn-sm btn-danger">Löschen</button>
                    </form>
                </div>
            </div>
        </div>
        ''')

    if items:
        inner = (
            f'<div class="section-list" hx-ext="sortable" '
            f'hx-post="/units/{unit_id}/sections/reorder" hx-trigger="end" hx-swap="none" '
            f'data-csrf-token="{csrf_token}">'
            + "\n".join(items)
            + "</div>"
        )
    else:
        inner = '<div class="empty-state"><p>Noch keine Abschnitte vorhanden.</p></div>'
    return f'<section id="section-list-section">{inner}</section>'

def _render_sections_page_html(unit: dict, sections: list[dict], csrf_token: str, error: str | None = None) -> str:
    """Build the sections management page content HTML."""
    from components import SectionCreateForm
    form_component = SectionCreateForm(unit_id=unit["id"], csrf_token=csrf_token, error=error)
    create_form_html = form_component.render()
    section_list_html = _render_section_list_partial(unit["id"], sections, csrf_token=csrf_token)

    return f'''
        <div class="container">
            <h1 id="sections-heading">Abschnitte für: {Component.escape(unit.get("title", ""))}</h1>
            <section class="card create-section-section" id="create-section-form-container">
                <h2 id="create-section-heading">Neuen Abschnitt erstellen</h2>
                {create_form_html}
            </section>
            {section_list_html}
        </div>
    '''

def _render_members_list_partial(course_id: str, members: list[dict], *, csrf_token: str) -> str:
    items = []
    for member in members:
        items.append(
            f'''<li class="member-item">
                <span>{Component.escape(member.get("name"))}</span>
                <form hx-post="/courses/{course_id}/members/{member['sub']}/delete" hx-target="#members-layout" hx-swap="outerHTML">
                    <input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">
                    <button type="submit" class="btn btn-sm btn-danger">Entfernen</button>
                </form>
            </li>'''
        )
    joined_items = "\n".join(items)
    return f'<ul class="member-list">{joined_items}</ul>' if items else "<p>Keine Mitglieder.</p>"

def _render_candidate_list(course_id: str, current_members: list[dict], candidates: list[dict] | None, *, csrf_token: str) -> str:
    """Render only the <ul> with candidate add-actions, excluding current members."""
    """Render the add-student search UI using API-provided candidates.

    Parameters:
    - course_id: Target course identifier
    - current_members: List of current members (dicts with keys 'sub' and 'name')
    - candidates: Optional list of candidate students from directory search API
    - csrf_token: Synchronizer token required for POST

    Behavior:
    - Renders up to 50 candidate results with an add form each
    - Excludes candidates that are already members
    """
    member_subs = {m['sub'] for m in current_members}
    safe_candidates = []
    for s in (candidates or [])[:50]:
        sub = str(s.get('sub', ''))
        name = str(s.get('name', ''))
        if not sub or not name:
            continue
        if sub in member_subs:
            continue
        safe_candidates.append({'sub': sub, 'name': name})

    items = []
    for student in safe_candidates:
        items.append(
            f'''<li class="member-item">
                <span>{Component.escape(student.get("name"))}</span>
                <form hx-post="/courses/{course_id}/members" hx-target="#members-layout" hx-swap="outerHTML">
                    <input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">
                    <input type="hidden" name="student_sub" value="{student['sub']}">
                    <button type="submit" class="btn btn-sm btn-primary">Hinzufügen</button>
                </form>
            </li>'''
        )
    search_list_html = "\n".join(items)
    if not items:
        search_list_html = '<li class="member-item text-muted">Keine Treffer.</li>'
    return f'<ul class="member-list">{search_list_html}</ul>'


def _render_add_student_wrapper(course_id: str, *, csrf_token: str) -> str:
    """Render the search input and a results container that auto-loads candidates."""
    search_input_html = (
        f'<input type="search" name="q" class="form-input" placeholder="Schüler suchen..." '
        f'hx-get="/courses/{course_id}/members/search" hx-trigger="keyup changed delay:300ms" hx-target="#search-results">'
    )
    # Auto-load candidate list on initial render
    results_div = (
        f'<div id="search-results" hx-get="/courses/{course_id}/members/search?limit=50&offset=0" '
        f'hx-trigger="load" hx-swap="innerHTML">'
        f'<ul class="member-list"><li class="member-item text-muted">Lade Kandidaten…</li></ul></div>'
    )
    return f'<div class="search-form">{search_input_html}</div>{results_div}'

def _render_members_page_html(request: Request, course: dict, members: list[dict], *, csrf_token: str, error: str | None = None) -> str:
    members_list_html = _render_members_list_partial(course['id'], members, csrf_token=csrf_token)
    add_student_html = _render_add_student_wrapper(course['id'], csrf_token=csrf_token)
    error_html = f'<div class="alert alert-error" role="alert">{Component.escape(error)}</div>' if error else ''
    return f'''<div class="container"><h1 id="members-heading">Mitglieder für: {Component.escape(course.get("title", ""))}</h1><div class="members-layout" id="members-layout">{error_html}<section class="members-column card" id="members-current"><h2>Aktuelle Kursmitglieder</h2>{members_list_html}</section><section class="members-column card" id="members-add"><h2>Schüler hinzufügen</h2>{add_student_html}</section></div></div>'''

# --- Route Handlers -------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Minimal, neutral start page without science copy
    user = getattr(request.state, "user", None)
    content = """
    <div class=\"container\">
        <h1>Willkommen bei GUSTAV</h1>
        <p class=\"text-muted\">Offene Lernplattform für Schulen.</p>
    </div>
    """
    layout = Layout(title="Startseite", content=content, user=user, current_path=request.url.path)
    html = layout.render()
    if request.headers.get("HX-Request"):
        aside_oob = Navigation(user, request.url.path).render_aside(oob=True)
        html = html + aside_oob
    return HTMLResponse(content=html)

@app.get("/courses", response_class=HTMLResponse)
async def courses_index(request: Request):
    """SSR page that renders the teacher's courses by calling the JSON API.

    Why:
        Keep UI strictly behind the public API contract. This ensures the page
        shows the same data as API clients and avoids bypassing DB/authorization
        checks. The session cookie is forwarded to the internal API call.

    Behavior:
        - Redirects non-teachers to "/" (UI policy).
        - Calls GET /api/teaching/courses with clamped pagination.
        - Renders the list and pager; sets private, no-store cache headers.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    limit, offset = _clamp_pagination(request.query_params.get("limit"), request.query_params.get("offset"))

    # Call the in-process API to fetch real courses from the DB-backed repo.
    items: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            sid = request.cookies.get(SESSION_COOKIE_NAME)
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            r = await client.get("/api/teaching/courses", params={"limit": limit, "offset": offset})
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    items = data
            # Else: keep empty items to render an empty state gracefully
    except Exception:
        items = []

    has_next = len(items) == limit
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    content = _render_courses_page_html(request, items, csrf_token=token, limit=limit, offset=offset, has_next=has_next)
    layout = Layout(title="Meine Kurse", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})

@app.post("/courses", response_class=HTMLResponse)
async def courses_create(request: Request):
    """Handle course creation via the API and update the list/form.

    Why:
        The UI delegates creation to POST /api/teaching/courses to keep one
        contract. We still enforce CSRF at the UI boundary and use PRG or HTMX
        partial swap depending on the request.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    title = str(form.get("title", "")).strip()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse(content="CSRF Error", status_code=403)

    # Call the API endpoint; map 400 errors back into the form.
    api_status = 0
    try:
        import httpx
        from httpx import ASGITransport

        payload = {
            "title": title,
            "subject": (str(form.get("subject", "")).strip() or None),
            "grade_level": (str(form.get("grade_level", "")).strip() or None),
            "term": (str(form.get("term", "")).strip() or None),
        }
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            resp = await client.post("/api/teaching/courses", json=payload)
            api_status = resp.status_code
    except Exception:
        api_status = 500

    if api_status != 201:
        # Re-render the form with a friendly error. Preserve entered values.
        token = _get_or_create_csrf_token(sid or "")
        # Map API invalid_input to our UI message key; otherwise generic backend_error
        error_key = "invalid_title" if title == "" else "backend_error"
        form_component = CourseCreateForm(csrf_token=token, error=error_key, values=dict(form))
        return HTMLResponse(form_component.render(), headers={"HX-Reswap": "outerHTML"})

    # HTMX: return updated course list partial + refreshed form via OOB swap
    if "HX-Request" in request.headers:
        limit, offset = _clamp_pagination(None, None)
        items: list[dict] = []
        try:
            import httpx
            from httpx import ASGITransport

            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
                if sid:
                    client.cookies.set(SESSION_COOKIE_NAME, sid)
                r = await client.get("/api/teaching/courses", params={"limit": limit, "offset": offset})
                if r.status_code == 200 and isinstance(r.json(), list):
                    items = r.json()
        except Exception:
            items = []
        token = _get_or_create_csrf_token(sid or "")
        course_list_html = _render_course_list_partial(items, limit, offset, len(items) == limit, csrf_token=token)
        form_component = CourseCreateForm(csrf_token=token)
        form_html = f'<div id="create-course-form-container" hx-swap-oob="true">{form_component.render()}</div>'
        return HTMLResponse(content=course_list_html + form_html)

    # PRG: redirect back to the listing page
    return RedirectResponse(url="/courses", status_code=302)

@app.post("/courses/{course_id}/delete", response_class=HTMLResponse)
async def delete_course_htmx(request: Request, course_id: str):
    """Delete a course via the public API and return the updated list partial.

    Why:
        Keep SSR behavior aligned with API semantics and DB/RLS. CSRF is enforced
        at the UI boundary; authorization and ownership are enforced by the API.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse(content="CSRF Error", status_code=403)
    # Call DELETE /api/teaching/courses/{id}
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            await client.delete(f"/api/teaching/courses/{course_id}")
    except Exception:
        # On network or unexpected error, fall through to re-render current list
        pass
    # Re-fetch list from API and render partial
    limit, offset = _clamp_pagination(None, None)
    items: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            r = await client.get("/api/teaching/courses", params={"limit": limit, "offset": offset})
            if r.status_code == 200 and isinstance(r.json(), list):
                items = r.json()
    except Exception:
        items = []
    token = _get_or_create_csrf_token(sid or "")
    return HTMLResponse(content=_render_course_list_partial(items, limit, offset, len(items) == limit, csrf_token=token))

@app.get("/units", response_class=HTMLResponse)
async def units_index(request: Request):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    # Fetch units from Teaching repo for this teacher
    limit, offset = _clamp_pagination(request.query_params.get("limit"), request.query_params.get("offset"))
    items: list[dict] | list = []
    try:
        from routes import teaching as teaching_routes  # type: ignore
        items = teaching_routes.REPO.list_units_for_author(
            author_id=str((user or {}).get("sub") or ""), limit=limit, offset=offset
        )
        vm = [
            {
                "id": getattr(u, "id", None) if not isinstance(u, dict) else u.get("id"),
                "title": getattr(u, "title", None) if not isinstance(u, dict) else u.get("title"),
                "summary": getattr(u, "summary", None) if not isinstance(u, dict) else u.get("summary"),
            }
            for u in (items or [])
        ]
    except Exception:
        vm = []
        items = []

    # Build page content and append a simple pager beneath the list
    base_content = _render_units_page_html(vm, csrf_token=token)
    has_next = isinstance(items, list) and len(items) == limit
    pager = ""
    if vm:
        prev_disabled = offset <= 0
        prev_href = f"/units?limit={limit}&offset={max(0, offset - limit)}"
        next_href = f"/units?limit={limit}&offset={offset + limit}"
        disabled_attr = 'aria-disabled="true"' if prev_disabled else ''
        links = [
            f'<a data-testid="pager-prev" href="{prev_href}" class="pager-link" {disabled_attr}>Zurück</a>'
        ]
        if has_next:
            links.append(f'<a data-testid="pager-next" href="{next_href}" class="pager-link">Weiter</a>')
        pager = f"<nav class=\"pager\">{' '.join(links)}</nav>"
    # Append pager after the main units content
    content = base_content + (pager if pager else "")
    layout = Layout(title="Lerneinheiten", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})

@app.post("/units", response_class=HTMLResponse)
async def units_create(request: Request):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    
    form = await request.form()
    title = str(form.get("title", "")).strip()
    summary = str(form.get("summary", "")).strip()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)

    if not title:
        token = _get_or_create_csrf_token(sid or "")
        form_component = UnitCreateForm(csrf_token=token, error="invalid_title", values=dict(form))
        return HTMLResponse(form_component.render(), headers={"HX-Reswap": "outerHTML"})

    try:
        from routes import teaching as teaching_routes  # type: ignore
        teaching_routes.REPO.create_unit(title=title, summary=summary or None, author_id=str((user or {}).get("sub") or ""))
    except Exception:
        pass

    if "HX-Request" in request.headers:
        try:
            from routes import teaching as teaching_routes  # type: ignore
            items = teaching_routes.REPO.list_units_for_author(author_id=str((user or {}).get("sub") or ""), limit=50, offset=0)
            vm = [
                {
                    "id": getattr(u, "id", None) if not isinstance(u, dict) else u.get("id"),
                    "title": getattr(u, "title", None) if not isinstance(u, dict) else u.get("title"),
                    "summary": getattr(u, "summary", None) if not isinstance(u, dict) else u.get("summary"),
                }
                for u in items
            ]
        except Exception:
            vm = []
        unit_list_html = _render_unit_list_partial(vm)
        token = _get_or_create_csrf_token(sid or "")
        form_component = UnitCreateForm(csrf_token=token)
        form_html = f'<div id="create-unit-form-container" hx-swap-oob="true">{form_component.render()}</div>'
        return HTMLResponse(content=unit_list_html + form_html)

    return RedirectResponse(url="/units", status_code=302)


@app.get("/units/{unit_id}", response_class=HTMLResponse)
async def unit_details_index(request: Request, unit_id: str):
    """Sections management UI for a unit.

    Why: Teachers need a simple, server-rendered page to add/delete/reorder
    sections. Until full DB integration for sections is ready, this page uses a
    dummy in-memory store for the sections themselves.

    Behavior:
    - Resolves the unit metadata by preferring the Teaching repo (DB/in-memory)
      for the current teacher; if not found, falls back to the local dummy list
      to keep the page functional in demos.
    - Renders the sections list with stable wrapper id (section-list-section)
      and CSRF-protected forms.

    Permissions: Caller must be a teacher; requires a valid session (CSRF ties
    to session id).
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)

    # 1) Resolve unit meta (title/summary) – prefer Repo, fallback to dummy
    unit_title: str | None = None
    unit_summary: str | None = None
    try:
        from routes import teaching as teaching_routes  # type: ignore
        author_sub = str((user or {}).get("sub") or "")
        # Preferred: direct lookup when available
        u = None
        try:
            u = teaching_routes.REPO.get_unit_for_author(unit_id, author_sub)  # type: ignore[attr-defined]
        except Exception:
            u = None
        if u is None:
            # Fallback: scan author's units to find matching id (works for DB/in-memory)
            try:
                items = teaching_routes.REPO.list_units_for_author(author_id=author_sub, limit=50, offset=0)
                for item in (items or []):
                    if getattr(item, "id", None) == unit_id or (isinstance(item, dict) and item.get("id") == unit_id):
                        u = item
                        break
            except Exception:
                u = None
        if u is not None:
            unit_title = getattr(u, "title", None) if not isinstance(u, dict) else u.get("title")
            unit_summary = getattr(u, "summary", None) if not isinstance(u, dict) else u.get("summary")
    except Exception:
        # Repo import or calls failed; continue to dummy fallback
        pass

    if unit_title is None:
        dummy = next((u for u in _DUMMY_UNITS_STORE if u.get("id") == unit_id), None)
        if dummy:
            unit_title = str(dummy.get("title") or "Lerneinheit")
            unit_summary = str(dummy.get("summary") or "") or None

    if unit_title is None:
        return HTMLResponse("Lerneinheit nicht gefunden", status_code=404)

    # 2) Load sections from the local dummy store keyed by unit_id
    sections = _DUMMY_SECTIONS_STORE.get(unit_id, [])

    # 3) CSRF token tied to session id
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)

    unit_vm = {"id": unit_id, "title": unit_title, "summary": unit_summary}
    content = _render_sections_page_html(unit_vm, sections, csrf_token=token)
    layout = Layout(title=f"Abschnitte für {unit_title}", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


@app.post("/units/{unit_id}/sections", response_class=HTMLResponse)
async def sections_create(request: Request, unit_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    
    form = await request.form()
    title = str(form.get("title", "")).strip()
    # Note: No debug prints to avoid leaking PII into logs.
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)

    if title:
        new_section = {"id": str(uuid.uuid4()), "title": title}
        _DUMMY_SECTIONS_STORE.setdefault(unit_id, []).append(new_section)

    sections = _DUMMY_SECTIONS_STORE.get(unit_id, [])
    token = _get_or_create_csrf_token(sid or "")
    
    # Fragment 1: The updated section list
    section_list_html = _render_section_list_partial(unit_id, sections, csrf_token=token)
    
    # Fragment 2: A new, empty form for out-of-band swap
    form_component = SectionCreateForm(unit_id=unit_id, csrf_token=token)
    form_html = f'<div id="create-section-form-container" hx-swap-oob="true">{form_component.render()}</div>'
    
    return HTMLResponse(content=section_list_html + form_html)


@app.post("/units/{unit_id}/sections/{section_id}/delete", response_class=HTMLResponse)
async def sections_delete(request: Request, unit_id: str, section_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)

    sid = _get_session_id(request)
    form = await request.form()
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)

    sections = _DUMMY_SECTIONS_STORE.get(unit_id, [])
    _DUMMY_SECTIONS_STORE[unit_id] = [s for s in sections if s.get("id") != section_id]
    
    token = _get_or_create_csrf_token(sid or "")
    return HTMLResponse(content=_render_section_list_partial(unit_id, _DUMMY_SECTIONS_STORE.get(unit_id, []), csrf_token=token))

@app.post("/units/{unit_id}/sections/reorder", response_class=Response)
async def sections_reorder(request: Request, unit_id: str):
    """Reorder the sections of a unit based on client-provided order.

    Why: Allows teachers to adjust the pedagogical sequence of a unit's sections.

    Behavior:
    - Expects form fields named 'id' for each child element in display order.
      Values are DOM ids like 'section_<uuid>'; the '<uuid>' part is used.
    - Updates only the order; drops items not present in the submitted list.

    Permissions: Caller must be a teacher (UI-only dummy store here).
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return Response(status_code=403)
    
    form = await request.form()
    # CSRF validation: accept header or form field
    sid = _get_session_id(request)
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_field = form.get("csrf_token")
    if not _validate_csrf(sid, csrf_header or csrf_field):
        return Response(status_code=403)

    # htmx-sortable submits the ordered child element ids as repeated form fields
    # with the parameter name 'id', e.g.: id=section_<uuid>
    ordered_ids = [sid.replace("section_", "") for sid in form.getlist("id")]

    if unit_id in _DUMMY_SECTIONS_STORE:
        # Create a map of the existing sections by their ID
        section_map = {s["id"]: s for s in _DUMMY_SECTIONS_STORE[unit_id]}
        # Create the new ordered list
        reordered_sections = [section_map[sid] for sid in ordered_ids if sid in section_map]
        _DUMMY_SECTIONS_STORE[unit_id] = reordered_sections

    # No content response, as the UI is already updated optimistically
    return Response(status_code=200)

@app.get("/courses/{course_id}/members", response_class=HTMLResponse)
async def members_index(request: Request, course_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    # Fetch members via API and course title via direct GET
    members: list[dict] = []
    course_title = "Kurs"
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            m = await client.get(f"/api/teaching/courses/{course_id}/members", params={"limit": 50, "offset": 0})
            if m.status_code == 200 and isinstance(m.json(), list):
                members = m.json()
            # Course title via direct GET
            c = await client.get(f"/api/teaching/courses/{course_id}")
            if c.status_code == 200 and isinstance(c.json(), dict):
                it = c.json()
                t = it.get("title")
                if isinstance(t, str) and t:
                    course_title = t
    except Exception:
        members = []
    course_vm = {"id": course_id, "title": course_title}
    content = _render_members_page_html(request, course=course_vm, members=members, csrf_token=token)
    layout = Layout(title=f"Mitglieder für {course_vm['title']}", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})

@app.get("/courses/{course_id}/members/search", response_class=HTMLResponse)
async def search_students_for_course(request: Request, course_id: str):
    q = request.query_params.get("q", "")
    # Read sid/token
    sid = _get_session_id(request) or ""
    token = _get_or_create_csrf_token(sid) if sid else ""
    # Fetch current members via API to filter candidates
    members: list[dict] = []
    candidates: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            m = await client.get(f"/api/teaching/courses/{course_id}/members", params={"limit": 50, "offset": 0})
            if m.status_code == 200 and isinstance(m.json(), list):
                members = m.json()
            # Always list students (pagination), then filter by q locally
            limit = int(request.query_params.get("limit", 50) or 50)
            offset = int(request.query_params.get("offset", 0) or 0)
            u = await client.get("/api/users/list", params={"role": "student", "limit": limit, "offset": offset})
            if u.status_code == 200 and isinstance(u.json(), list):
                candidates = u.json()
    except Exception:
        members = []
        candidates = []
    # Filter candidates by q (case-insensitive)
    q_norm = (q or "").strip().lower()
    if q_norm:
        candidates = [c for c in candidates if q_norm in str(c.get("name", "")).lower()]
    # Return only the list portion for injection into #search-results
    return HTMLResponse(content=_render_candidate_list(course_id, members, candidates, csrf_token=token))

# Removed dummy handler — all member changes reflect the API state.

@app.post("/courses/{course_id}/members", response_class=HTMLResponse)
async def add_member_htmx(request: Request, course_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request)
    form = await request.form()
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse(content="CSRF Error", status_code=403)
    student_sub = str(form.get("student_sub"))
    error_msg: str | None = None
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            if student_sub:
                resp = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
                if resp.status_code not in (200, 201, 204):
                    error_msg = f"Hinzufügen fehlgeschlagen ({resp.status_code})."
    except Exception:
        error_msg = "Hinzufügen fehlgeschlagen (Netzwerkfehler)."
    # Re-render layout
    return await _handle_member_change_api(course_id, sid, error=error_msg)

@app.post("/courses/{course_id}/members/{student_sub}/delete", response_class=HTMLResponse)
async def remove_member_htmx(request: Request, course_id: str, student_sub: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request)
    form = await request.form()
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse(content="CSRF Error", status_code=403)
    error_msg: str | None = None
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            resp = await client.delete(f"/api/teaching/courses/{course_id}/members/{student_sub}")
            if resp.status_code not in (200, 204):
                error_msg = f"Entfernen fehlgeschlagen ({resp.status_code})."
    except Exception:
        error_msg = "Entfernen fehlgeschlagen (Netzwerkfehler)."
    # Ensure UI consistency even with eventual consistency: filter removed sub locally
    return await _handle_member_change_api(course_id, sid, error=error_msg, removed_sub=student_sub)

async def _handle_member_change_api(course_id: str, sid: str | None, *, error: str | None = None, removed_sub: str | None = None) -> HTMLResponse:
    members: list[dict] = []
    title = "Kurs"
    token = _get_or_create_csrf_token(sid or "")
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            m = await client.get(f"/api/teaching/courses/{course_id}/members", params={"limit": 50, "offset": 0})
            if m.status_code == 200 and isinstance(m.json(), list):
                members = m.json()
            c = await client.get(f"/api/teaching/courses/{course_id}")
            if c.status_code == 200 and isinstance(c.json(), dict):
                it = c.json()
                t = it.get("title")
                if isinstance(t, str) and t:
                    title = t
    except Exception:
        members = []
    # Fallback filter if backend is not yet consistent
    if removed_sub:
        members = [m for m in members if str(m.get("sub")) != str(removed_sub)]
    members_list_html = _render_members_list_partial(course_id, members, csrf_token=token)
    # Refresh candidates from list endpoint so removed users reappear
    candidates: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            u = await client.get("/api/users/list", params={"role": "student", "limit": 50, "offset": 0})
            if u.status_code == 200 and isinstance(u.json(), list):
                candidates = u.json()
    except Exception:
        candidates = []
    add_student_html = _render_add_student_wrapper(course_id, csrf_token=token)
    error_html = f'<div class="alert alert-error" role="alert">{Component.escape(error)}</div>' if error else ''
    return HTMLResponse(content=f'<div class="members-layout" id="members-layout">{error_html}<section class="members-column card" id="members-current"><h2>Aktuelle Kursmitglieder</h2>{members_list_html}</section><section class="members-column card" id="members-add"><h2>Schüler hinzufügen</h2>{add_student_html}</section></div>', headers={"Cache-Control": "no-store"})

# --- Other Routes & App Includes -----------------------------------------------

app.include_router(auth_router)
app.include_router(learning_router)
app.include_router(teaching_router)
app.include_router(users_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    user = getattr(request.state, "user", None)
    content = """
    <div class=\"container\">
        <h1>Über GUSTAV</h1>
        <p>GUSTAV ist eine offene Lernplattform für Schulen.</p>
    </div>
    """
    layout = Layout(title="Über GUSTAV", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str | None = None, state: str | None = None):
    if not code or not state:
        return JSONResponse({"error": "invalid_code_or_state"}, status_code=400, headers={"Cache-Control": "no-store"})
    rec = STATE_STORE.pop_valid(state)
    if not rec:
        return JSONResponse({"error": "invalid_code_or_state"}, status_code=400, headers={"Cache-Control": "no-store"})
    try:
        tokens = OIDC.exchange_code_for_tokens(code=code, code_verifier=rec.code_verifier)
    except Exception as exc:
        logger.warning("Token exchange failed: %s", exc.__class__.__name__)
        return JSONResponse({"error": "token_exchange_failed"}, status_code=400, headers={"Cache-Control": "no-store"})
    id_token = tokens.get("id_token")
    if not id_token or not isinstance(id_token, str):
        return JSONResponse({"error": "invalid_id_token"}, status_code=400, headers={"Cache-Control": "no-store"})
    try:
        claims = verify_id_token(id_token=id_token, cfg=OIDC_CFG)
    except IDTokenVerificationError as exc:
        logger.warning("ID token verification failed: %s", exc.code)
        return JSONResponse({"error": "invalid_id_token"}, status_code=400, headers={"Cache-Control": "no-store"})
    claim_nonce = claims.get("nonce")
    if getattr(rec, "nonce", None) and claim_nonce != rec.nonce:
        return JSONResponse({"error": "invalid_nonce"}, status_code=400, headers={"Cache-Control": "no-store"})

    sub = str(claims.get("sub") or "unknown-sub")
    email = claims.get("email") or claims.get("preferred_username") or ""
    raw_roles: list[str] = []
    ra = claims.get("realm_access") or {}
    if isinstance(ra, dict):
        r = ra.get("roles")
        if isinstance(r, list):
            raw_roles = [str(x) for x in r]
    
    roles = [role for role in raw_roles if role in ALLOWED_ROLES]
    if not roles:
        roles = ["student"]
    
    display_name = claims.get("gustav_display_name") or claims.get("name") or (email.split("@")[0] if email else "Benutzer")

    sess = SESSION_STORE.create(sub=sub, roles=roles, name=str(display_name), id_token=id_token)
    dest = rec.redirect or "/"
    resp = RedirectResponse(url=dest, status_code=302)
    max_age = sess.ttl_seconds if SETTINGS.environment == "prod" else None
    _set_session_cookie(resp, sess.session_id, max_age=max_age, request=request)
    return resp

@app.get("/api/me")
async def get_me(request: Request):
    if SESSION_COOKIE_NAME not in request.cookies:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "no-store"})
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    rec = SESSION_STORE.get(sid or "")
    if not rec:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "no-store"})
    
    exp_iso = datetime.fromtimestamp(rec.expires_at, tz=timezone.utc).isoformat(timespec="seconds") if rec.expires_at else None
    return JSONResponse({
        "sub": rec.sub,
        "roles": rec.roles,
        "name": getattr(rec, "name", ""),
        "expires_at": exp_iso,
    }, headers={"Cache-Control": "no-store"})
def create_app_auth_only() -> FastAPI:
    """Factory returning a lightweight FastAPI app exposing only auth routes.

    Why: Tests import this to exercise authentication contracts in isolation
    without pulling in unrelated routers or DB-dependent wiring.
    """
    sub = FastAPI(title="GUSTAV alpha-2 (auth-only)", description="Auth slice", version="0.0.2")
    sub.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    sub.include_router(auth_router)
    # Lightweight callback stub for contract tests
    @sub.get("/auth/callback")
    async def _callback_stub(request: Request, code: str | None = None, state: str | None = None):
        # Treat explicit "invalid" values as invalid for negative-path tests
        if (not code or not state) or (code == "invalid" or state == "invalid"):
            return JSONResponse({"error": "invalid_code_or_state"}, status_code=400, headers={"Cache-Control": "no-store"})
        sid = secrets.token_urlsafe(24)
        resp = RedirectResponse(url="/", status_code=302)
        _set_session_cookie(resp, sid, request=request)
        return resp
    # Provide a lightweight /api/me for auth-only tests
    @sub.get("/api/me")
    async def me_stub(request: Request):
        if SESSION_COOKIE_NAME not in request.cookies:
            return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "no-store"})
        return JSONResponse({
            "sub": "test-user",
            "roles": ["student"],
            "name": "",
            "expires_at": None,
        }, headers={"Cache-Control": "no-store"})
    # Note: A single callback stub is defined above to avoid duplicate routes.
    return sub
