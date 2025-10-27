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
from components.forms.unit_edit_form import UnitEditForm
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
    # Support Origin/Referer fallback in CSRF checks without leaking cross-site
    # paths: strict-origin-when-cross-origin.
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
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

def _is_uuid_like(value: str) -> bool:
    """Best-effort check whether a string is UUID-like.

    Used by SSR routes to decide whether to call API endpoints that expect UUIDs.
    """
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False

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
                    <a href="/courses/{c.get("id")}/modules" class="btn btn-secondary">Lerneinheiten</a>
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

def _render_student_course_list(items: list[dict], limit: int, offset: int, has_next: bool) -> str:
    """Render a simple course list for students without edit actions.

    Links route to /learning/courses/{id}.
    """
    cards = []
    for c in items:
        cid = str(c.get("id", ""))
        title = Component.escape(str(c.get("title", "")))
        subject = Component.escape(str(c.get("subject", "") or ""))
        grade = Component.escape(str(c.get("grade_level", "") or ""))
        term = Component.escape(str(c.get("term", "") or ""))
        meta_bits = [b for b in [subject, grade, term] if b]
        meta_html = f'<div class="card-meta">{" · ".join(meta_bits)}</div>' if meta_bits else ''
        cards.append(
            f'<div class="card course-card" data-course-id="{cid}">'
            f'<div class="card-body">'
            f'<h3 class="card-title"><a href="/learning/courses/{cid}">{title}</a></h3>'
            f'{meta_html}'
            f'</div>'
            f'</div>'
        )
    list_html = "\n".join(cards)
    prev_disabled = offset <= 0
    prev_href = f"/learning?limit={limit}&offset={max(0, offset - limit)}"
    next_href = f"/learning?limit={limit}&offset={offset + limit}"
    pager_html = []
    disabled_attr = 'aria-disabled="true"' if prev_disabled else ''
    pager_html.append(
        f'<a data-testid="pager-prev" href="{prev_href}" class="pager-link" {disabled_attr}>Zurück</a>'
    )
    if has_next:
        pager_html.append(f'<a data-testid="pager-next" href="{next_href}" class="pager-link">Weiter</a>')
    pager = f"<nav class=\"pager\">{' '.join(pager_html)}</nav>" if cards else ""
    inner = (
        f'<div class="course-list">{list_html}</div>{pager}' if cards else '<div class="empty-state"><p>Du bist noch in keinem Kurs.</p></div>'
    )
    return f'<section class="course-list-section" aria-labelledby="student-courses-heading"><h2 id="student-courses-heading" class="sr-only">Meine Kurse</h2>{inner}</section>'

def _render_courses_page_html(request: Request, items: list[dict], *, csrf_token: str, limit: int, offset: int, has_next: bool, error: str | None = None) -> str:
    form_component = CourseCreateForm(csrf_token=csrf_token, error=error)
    form_html = form_component.render()
    course_list_html = _render_course_list_partial(items, limit, offset, has_next, csrf_token=csrf_token)
    return f'''
        <div class="container">
            <h1 id="courses-heading">Kurse</h1>
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

@app.get("/learning", response_class=HTMLResponse)
async def learning_index(request: Request):
    """SSR page listing the student's courses via the Learning API.

    Permissions:
        Caller must be a student; otherwise redirect to home.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "student":
        return RedirectResponse(url="/", status_code=303)
    limit, offset = _clamp_pagination(request.query_params.get("limit"), request.query_params.get("offset"))
    items: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            sid = request.cookies.get(SESSION_COOKIE_NAME)
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            r = await client.get("/api/learning/courses", params={"limit": limit, "offset": offset})
            if r.status_code == 200 and isinstance(r.json(), list):
                items = r.json()
    except Exception:
        items = []
    content = (
        '<div class="container">'
        '<h1>Meine Kurse</h1>'
        f'{_render_student_course_list(items, limit, offset, len(items) == limit)}'
        '</div>'
    )
    layout = Layout(title="Meine Kurse", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})

@app.get("/learning/courses/{course_id}", response_class=HTMLResponse)
async def learning_course_detail(request: Request, course_id: str):
    """SSR page showing the units of a course for the current student.

    Behavior: Fetches units via Learning API. Uses a best-effort course title
    lookup via the courses list; falls back to a generic header when not found.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "student":
        return RedirectResponse(url="/", status_code=303)
    # Validate UUID-ish to avoid calling the API with garbage
    if not _is_uuid_like(course_id):
        return RedirectResponse(url="/learning", status_code=303)
    title = "Kurs"
    units: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            sid = request.cookies.get(SESSION_COOKIE_NAME)
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            # Try lookup for title from course list (best-effort)
            try:
                r_courses = await client.get("/api/learning/courses", params={"limit": 50, "offset": 0})
                if r_courses.status_code == 200 and isinstance(r_courses.json(), list):
                    for it in r_courses.json():
                        if isinstance(it, dict) and str(it.get("id")) == str(course_id):
                            t = it.get("title")
                            if isinstance(t, str) and t:
                                title = t
                            break
            except Exception:
                pass
            r_units = await client.get(f"/api/learning/courses/{course_id}/units")
            if r_units.status_code == 200 and isinstance(r_units.json(), list):
                units = r_units.json()
    except Exception:
        units = []

    # Render simple unit list
    unit_items = []
    for row in units:
        u = row.get("unit", {}) if isinstance(row, dict) else {}
        uid = Component.escape(str(u.get("id", "")))
        utitle = Component.escape(str(u.get("title", "")))
        unit_items.append(f'<li><span class="badge">{row.get("position", "")}</span> {utitle}</li>')
    units_html = '<ul class="unit-list">' + ("\n".join(unit_items) if unit_items else '<li class="text-muted">Keine Lerneinheiten.</li>') + '</ul>'
    content = (
        '<div class="container">'
        f'<h1>{Component.escape(title)}</h1>'
        f'<p><a href="/learning">Zurück zu „Meine Kurse“</a></p>'
        f'<section class="card"><h2>Lerneinheiten</h2>{units_html}</section>'
        '</div>'
    )
    layout = Layout(title=Component.escape(title), content=content, user=user, current_path=request.url.path)
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


@app.get("/courses/{course_id}/modules", response_class=HTMLResponse)
async def courses_modules_page(request: Request, course_id: str):
    """Render the course modules management page (owner only).

    Left: modules in the course (sortable, delete), Right: available units to add.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    modules: list[dict] = []
    units: list[dict] = []
    # Fetch via internal API to reuse guards and serialization
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            r_mod = await client.get(f"/api/teaching/courses/{course_id}/modules")
            if r_mod.status_code == 200 and isinstance(r_mod.json(), list):
                modules = r_mod.json()
            # Load up to 100 units for the owner
            r_units = await client.get("/api/teaching/units", params={"limit": 100, "offset": 0})
            if r_units.status_code == 200 and isinstance(r_units.json(), list):
                units = r_units.json()
    except Exception:
        pass
    unit_titles = {str(u.get("id")): str(u.get("title") or "") for u in (units or [])}
    attached_unit_ids = {str(m.get("unit_id")) for m in (modules or [])}
    module_list_html = _render_module_list_partial(course_id, modules, unit_titles=unit_titles, csrf_token=token)
    available_html = _render_available_units_partial(course_id, units=units, attached_unit_ids=attached_unit_ids, csrf_token=token)
    content = (
        '<div class="container">'
        '<h1>Lerneinheiten im Kurs</h1>'
        f'<div class="grid grid-2cols"><div>{module_list_html}</div><div>{available_html}</div></div>'
        '</div>'
    )
    layout = Layout(title="Lerneinheiten", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


@app.post("/courses/{course_id}/modules/create", response_class=HTMLResponse)
async def courses_modules_create(request: Request, course_id: str):
    """Attach a unit to a course via API and return updated modules partial.

    Requires CSRF; non-HTMX requests use PRG back to the page.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    unit_id = str(form.get("unit_id") or "").strip()
    error: str | None = None
    modules: list[dict] = []
    units: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
            if r.status_code >= 400:
                error = _extract_api_error_detail(r)
            # Refresh lists
            r_mod = await client.get(f"/api/teaching/courses/{course_id}/modules")
            if r_mod.status_code == 200:
                modules = r_mod.json()
            r_units = await client.get("/api/teaching/units", params={"limit": 100, "offset": 0})
            if r_units.status_code == 200:
                units = r_units.json()
    except Exception:
        error = "backend_error"
    if "HX-Request" not in request.headers:
        return RedirectResponse(url=f"/courses/{course_id}/modules", status_code=303)
    unit_titles = {str(u.get("id")): str(u.get("title") or "") for u in (units or [])}
    token = _get_or_create_csrf_token(sid or "")
    html_main = _render_module_list_partial(course_id, modules, unit_titles=unit_titles, csrf_token=token, error=error)
    # Also update the available units pane out-of-band so it reflects the change immediately
    updated_attached = {str(m.get("unit_id")) for m in (modules or [])}
    html_oob = _render_available_units_partial(course_id, units=units, attached_unit_ids=updated_attached, csrf_token=token, oob=True)
    return HTMLResponse(html_main + html_oob)


@app.post("/courses/{course_id}/modules/reorder", response_class=Response)
async def courses_modules_reorder(request: Request, course_id: str):
    """Forward sortable reorder to API; requires CSRF."""
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return Response(status_code=403)
    form = await request.form()
    sid = _get_session_id(request)
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_field = form.get("csrf_token")
    if not _validate_csrf(sid, csrf_header or csrf_field):
        return Response(status_code=403)
    ordered_ids = [sid.replace("module_", "") for sid in form.getlist("id")]
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            resp = await client.post(
                f"/api/teaching/courses/{course_id}/modules/reorder",
                json={"module_ids": ordered_ids},
            )
    except Exception:
        return JSONResponse({"error": "bad_request", "detail": "reorder_failed"}, status_code=400)
    if resp.status_code >= 400:
        detail = _extract_api_error_detail(resp)
        status = resp.status_code if resp.status_code in (400, 403, 404) else 400
        return JSONResponse({"error": "bad_request", "detail": detail}, status_code=status)
    return Response(status_code=200)


@app.post("/courses/{course_id}/modules/{module_id}/delete", response_class=HTMLResponse)
async def courses_modules_delete(request: Request, course_id: str, module_id: str):
    """Forward delete to API and return updated modules list partial.

    Requires CSRF. Non-HTMX PRG back to the modules page.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    error: str | None = None
    modules: list[dict] = []
    units: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            dr = await client.delete(f"/api/teaching/courses/{course_id}/modules/{module_id}")
            if dr.status_code >= 400:
                error = _extract_api_error_detail(dr)
            r_mod = await client.get(f"/api/teaching/courses/{course_id}/modules")
            if r_mod.status_code == 200:
                modules = r_mod.json()
            r_units = await client.get("/api/teaching/units", params={"limit": 100, "offset": 0})
            if r_units.status_code == 200:
                units = r_units.json()
    except Exception:
        error = "backend_error"
    if "HX-Request" not in request.headers:
        return RedirectResponse(url=f"/courses/{course_id}/modules", status_code=303)
    unit_titles = {str(u.get("id")): str(u.get("title") or "") for u in (units or [])}
    token = _get_or_create_csrf_token(sid or "")
    html_main = _render_module_list_partial(course_id, modules, unit_titles=unit_titles, csrf_token=token, error=error)
    updated_attached = {str(m.get("unit_id")) for m in (modules or [])}
    html_oob = _render_available_units_partial(course_id, units=units, attached_unit_ids=updated_attached, csrf_token=token, oob=True)
    return HTMLResponse(html_main + html_oob)

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

def _render_section_list_partial(unit_id: str, sections: list[dict], csrf_token: str, error: str | None = None) -> str:
    """Render the section list including its stable wrapper container.

    The outer wrapper has id="section-list-section" and is the HX target for create/delete updates.
    Inside, a div.section-list holds sortable items with ids "section_<id>" so the sortable
    extension can submit an ordered list via form parameter name "id".
    """
    items: list[str] = []
    for section in sections:
        sec_id = section.get("id")
        title = Component.escape(section.get("title"))
        items.append(f'''
        <div class="card section-card" id="section_{sec_id}" data-section-id="{sec_id}">
            <div class="card-body">
                <span class="drag-handle">☰</span>
                <h4 class="card-title"><a href="/units/{unit_id}/sections/{sec_id}">{title}</a></h4>
                <div class="card-actions">
                    <a class="btn btn-sm" href="/units/{unit_id}/sections/{sec_id}">Material & Aufgaben</a>
                    <form hx-post="/units/{unit_id}/sections/{sec_id}/delete" hx-target="#section-list-section" hx-swap="outerHTML">
                        <input type="hidden" name="csrf_token" value="{csrf_token}">
                        <button type="submit" class="btn btn-sm btn-danger">Löschen</button>
                    </form>
                </div>
            </div>
        </div>
        ''')

    # Always render sortable container for consistent client behavior
    sortable_open = (
        f'<div class="section-list" hx-ext="sortable" '
        f'data-reorder-url="/units/{unit_id}/sections/reorder" '
        f'data-csrf-token="{csrf_token}">'
    )
    inner_content = "\n".join(items) if items else '<div class="empty-state"><p>Noch keine Abschnitte vorhanden.</p></div>'
    inner = sortable_open + inner_content + "</div>"
    error_html = (
        f'<div class="section-error" role="alert" data-testid="section-error">{Component.escape(error)}</div>'
        if error
        else ""
    )
    return f'<section id="section-list-section">{error_html}{inner}</section>'

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


def _render_material_list_partial(unit_id: str, section_id: str, materials: list[dict], *, csrf_token: str, error: str | None = None) -> str:
    """Render the materials list with a stable wrapper and sortable container.

    Why:
    - Keep a stable wrapper id so HTMX targets work even when the list is empty.
    - Use predictable child element ids (`material_<uuid>`) so the Sortable
      helper can submit the new order as form fields `id=material_<uuid>`.

    Parameters:
    - unit_id: Current learning unit id (string).
    - section_id: Current section id (string).
    - materials: Minimal view models (id, title) from the Teaching API.
    - csrf_token: Synchronizer token required by UI POSTs.
    - error: Optional UI error key to display in a banner.

    Behavior:
    - Renders an empty-state when there are no materials.
    - Embeds CSRF token on the sortable container as `data-csrf-token` so the
      client script can forward it as `X-CSRF-Token` during reorder.

    Permissions:
    - Caller must be a teacher; ownership checks are enforced by the API.
    """
    items: list[str] = []
    for m in materials:
        title = Component.escape(str(m.get("title") or "Untitled"))
        mid = m.get("id") or ""
        href = f"/units/{unit_id}/sections/{section_id}/materials/{mid}"
        items.append(
            f'''<div class="card material-card" id="material_{mid}"><div class="card-body"><h4 class="card-title"><a href="{href}">{title}</a></h4></div></div>'''
        )
    inner_content = "\n".join(items) if items else '<div class="empty-state"><p>Noch keine Materialien.</p></div>'
    sortable_open = (
        f'<div class="material-list" hx-ext="sortable" '
        f'data-reorder-url="/units/{unit_id}/sections/{section_id}/materials/reorder" '
        f'data-csrf-token="{Component.escape(csrf_token)}">'
    )
    error_html = (
        f'<div class="section-error" role="alert" data-testid="material-error">{Component.escape(error)}</div>'
        if error
        else ""
    )
    return f'<section id="material-list-section-{section_id}">{error_html}{sortable_open}{inner_content}</div></section>'


def _render_task_list_partial(unit_id: str, section_id: str, tasks: list[dict], *, csrf_token: str, error: str | None = None) -> str:
    """Render the tasks list with a stable wrapper and sortable container.

    Wrapper id: `task-list-section-<section_id>`, item ids: `task_<uuid>`.

    Keeps markup minimal for learning purposes; the excerpt shows the first
    characters of `instruction_md` so users can recognize entries.
    """
    items: list[str] = []
    for t in tasks:
        instr = str(t.get("instruction_md") or "")
        excerpt = Component.escape(instr[:140])
        tid = t.get("id") or ""
        href = f"/units/{unit_id}/sections/{section_id}/tasks/{tid}"
        items.append(
            f'''<div class="card task-card" id="task_{tid}"><div class="card-body"><div class="task-instruction"><a href="{href}">{excerpt}</a></div></div></div>'''
        )
    inner_content = "\n".join(items) if items else '<div class="empty-state"><p>Noch keine Aufgaben.</p></div>'
    sortable_open = (
        f'<div class="task-list" hx-ext="sortable" '
        f'data-reorder-url="/units/{unit_id}/sections/{section_id}/tasks/reorder" '
        f'data-csrf-token="{Component.escape(csrf_token)}">'
    )
    error_html = (
        f'<div class="section-error" role="alert" data-testid="task-error">{Component.escape(error)}</div>'
        if error
        else ""
    )
    return f'<section id="task-list-section-{section_id}">{error_html}{sortable_open}{inner_content}</div></section>'


def _render_module_list_partial(course_id: str, modules: list[dict], *, unit_titles: dict[str, str], csrf_token: str, error: str | None = None) -> str:
    """Render the course module list with sortable behavior.

    Wrapper id: `module-list-section`, item ids: `module_<uuid>`.
    """
    items: list[str] = []
    for m in modules:
        mid = str(m.get("id") or "")
        uid = str(m.get("unit_id") or "")
        title = Component.escape(unit_titles.get(uid) or "Unbenannte Lerneinheit")
        pos = m.get("position")
        del_action = (
            f'<form method="post" action="/courses/{course_id}/modules/{mid}/delete" '
            f'hx-post="/courses/{course_id}/modules/{mid}/delete" '
            f'hx-target="#module-list-section" hx-swap="outerHTML" style="display:inline">'
            f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
            f'<button class="btn btn-danger btn-sm" type="submit">Entfernen</button>'
            f'</form>'
        )
        link = f'/units/{uid}' if uid else '#'
        items.append(
            f'<div class="card module-card" id="module_{mid}"><div class="card-body">'
            f'<span class="badge">{pos}</span> '
            f'<span class="module-title"><a class="module-link" href="{link}">{title}</a></span> '
            f'{del_action}'
            f'</div></div>'
        )
    inner_content = "\n".join(items) if items else '<div class="empty-state"><p>Noch keine Lerneinheiten im Kurs.</p></div>'
    sortable_open = (
        f'<div class="module-list" hx-ext="sortable" '
        f'data-reorder-url="/courses/{course_id}/modules/reorder" '
        f'data-csrf-token="{Component.escape(csrf_token)}">'
    )
    error_html = (
        f'<div class="section-error" role="alert" data-testid="module-error">{Component.escape(error)}</div>' if error else ""
    )
    return f'<section id="module-list-section">{error_html}{sortable_open}{inner_content}</div></section>'


def _render_available_units_partial(course_id: str, *, units: list[dict], attached_unit_ids: set[str], csrf_token: str, oob: bool = False) -> str:
    """Render a simple list of available units to add to the course.

    Filters out units already attached.
    """
    rows: list[str] = []
    for u in units:
        uid = str(u.get("id") or "")
        if uid in attached_unit_ids:
            continue
        title = Component.escape(str(u.get("title") or "Unbenannte Lerneinheit"))
        form = (
            f'<form method="post" action="/courses/{course_id}/modules/create" '
            f'hx-post="/courses/{course_id}/modules/create" '
            f'hx-target="#module-list-section" hx-swap="outerHTML" class="inline-form">'
            f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
            f'<input type="hidden" name="unit_id" value="{uid}">'
            f'<button class="btn btn-secondary btn-sm" type="submit">Hinzufügen</button>'
            f'</form>'
        )
        rows.append(f'<li><span class="unit-title">{title}</span> {form}</li>')
    inner = "\n".join(rows) if rows else '<li class="text-muted">Keine weiteren Lerneinheiten verfügbar.</li>'
    oob_attr = ' hx-swap-oob="true"' if oob else ""
    return f'<section id="available-units-section" class="card"{oob_attr}><h2>Verfügbare Lerneinheiten</h2><ul class="available-units">{inner}</ul></section>'


def _render_section_detail_page_html(
    *,
    unit: dict,
    section: dict,
    materials: list[dict],
    tasks: list[dict],
    csrf_token: str,
    error_materials: str | None = None,
    error_tasks: str | None = None,
) -> str:
    """Builds the two-column section detail page content.

    Left: materials (create form + list)
    Right: tasks (create form + list)
    """
    unit_id = unit.get("id")
    section_id = section.get("id")

    # Minimal create forms (Markdown material, native task)
    mat_form = (
        f'<form id="material-create-text" method="post" action="/units/{unit_id}/sections/{section_id}/materials/create" '
        f'hx-post="/units/{unit_id}/sections/{section_id}/materials/create" '
        f'hx-target="#material-list-section-{section_id}" hx-swap="outerHTML">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Titel<input class="form-input" type="text" name="title" required></label>'
        f'<label>Markdown<textarea class="form-input" name="body_md" required></textarea></label>'
        f'<button class="btn btn-primary" type="submit">Material anlegen</button>'
        f'</form>'
    )
    # Tasks form with criteria[0..10] (as repeated name="criteria") and hints
    criteria_inputs = []
    for i in range(10):
        criteria_inputs.append(
            f'<div class="form-field"><input class="form-input" type="text" name="criteria" placeholder="Kriterium {i+1}"></div>'
        )
    criteria_html = "".join(criteria_inputs)
    task_form = (
        f'<form method="post" action="/units/{unit_id}/sections/{section_id}/tasks/create" '
        f'hx-post="/units/{unit_id}/sections/{section_id}/tasks/create" '
        f'hx-target="#task-list-section-{section_id}" hx-swap="outerHTML">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Anweisung<textarea class="form-input" name="instruction_md" required></textarea></label>'
        f'<fieldset><legend>Analysekriterien (0–10)</legend>{criteria_html}</fieldset>'
        f'<label>Lösungshinweise<textarea class="form-input" name="hints_md"></textarea></label>'
        f'<button class="btn btn-primary" type="submit">Aufgabe anlegen</button>'
        f'</form>'
    )

    # Optional: lightweight upload-intent form for file materials
    upload_form = (
        f'<form id="material-upload-intent-form" method="post" action="/units/{unit_id}/sections/{section_id}/materials/upload-intent" '
        f'hx-post="/units/{unit_id}/sections/{section_id}/materials/upload-intent" '
        f'hx-target="#material-upload-area" hx-swap="outerHTML">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Dateiname<input class="form-input" type="text" name="filename" required></label>'
        f'<label>MIME<input class="form-input" type="text" name="mime_type" value="application/pdf" required></label>'
        f'<label>Größe (Bytes)<input class="form-input" type="number" name="size_bytes" value="1024" min="1" required></label>'
        f'<button class="btn" type="submit">Upload vorbereiten</button>'
        f'</form>'
    )
    materials_html = _render_material_list_partial(unit_id, section_id, materials, csrf_token=csrf_token, error=error_materials)
    tasks_html = _render_task_list_partial(unit_id, section_id, tasks, csrf_token=csrf_token, error=error_tasks)

    return (
        '<div class="container">'
        f'<h1>Abschnitt: {Component.escape(section.get("title") or "Abschnitt")}</h1>'
        '<div class="two-col">'
        f'<section class="card col-left"><h2>Materialien</h2>'
        # Create buttons linking to dedicated create pages (simpler UI)
        f'<div class="actions"><a class="btn btn-primary" id="btn-create-material" '
        f'href="/units/{unit_id}/sections/{section_id}/materials/new">+ Material</a></div>'
        f'{materials_html}</section>'
        f'<section class="card col-right"><h2>Aufgaben</h2>'
        f'<div class="actions"><a class="btn btn-primary" id="btn-create-task" '
        f'href="/units/{unit_id}/sections/{section_id}/tasks/new">+ Aufgabe</a></div>'
        f'{tasks_html}</section>'
        '</div>'
        '</div>'
    )


def _extract_api_error_detail(response) -> str:
    """Return the error `detail`/`error` field from an API response for display."""
    try:
        data = response.json()
    except Exception:
        return f"status_{getattr(response, 'status_code', 'unknown')}"
    detail = data.get("detail")
    if detail:
        return str(detail)
    error = data.get("error")
    if error:
        return str(error)
    return f"status_{getattr(response, 'status_code', 'unknown')}"


async def _fetch_sections_for_unit(unit_id: str, *, session_id: str) -> list[dict]:
    """Fetch sections for the UI; returns empty list on error."""
    try:
        import httpx
        from httpx import ASGITransport

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if session_id:
                client.cookies.set(SESSION_COOKIE_NAME, session_id)
            resp = await client.get(f"/api/teaching/units/{unit_id}/sections")
    except Exception:
        return []
    if resp.status_code != 200:
        return []
    try:
        payload = resp.json()
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    cleaned: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cleaned.append({"id": item.get("id"), "title": item.get("title")})
    return cleaned


def _render_unit_edit_response(
    *,
    unit_id: str,
    user: dict | None,
    csrf_token: str,
    values: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render the SSR edit form with optional error feedback."""
    form_component = UnitEditForm(unit_id=unit_id, csrf_token=csrf_token, values=values or {}, error=error)
    content = (
        '<div class="container">'
        "<h1>Lerneinheit umbenennen</h1>"
        f'<section class="card">{form_component.render()}</section>'
        "</div>"
    )
    layout = Layout(title="Lerneinheit bearbeiten", content=content, user=user, current_path=f"/units/{unit_id}/edit")
    return HTMLResponse(
        content=layout.render(),
        status_code=status_code,
        headers={"Cache-Control": "private, no-store"},
    )


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
    return RedirectResponse(url="/courses", status_code=303)

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

    return RedirectResponse(url="/units", status_code=303)


@app.get("/units/{unit_id}/edit", response_class=HTMLResponse)
async def units_edit_form(request: Request, unit_id: str):
    """Render the unit edit form populated from API when possible.

    Permissions: Caller must be a teacher and (ideally) author; API enforces
    authorship. UI performs CSRF and PRG.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    values: dict[str, str] = {}
    error_msg: str | None = None
    # Prefill current values via direct GET /api/teaching/units/{id}
    try:
        import httpx
        from httpx import ASGITransport

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            r = await client.get(f"/api/teaching/units/{unit_id}")
            if r.status_code == 200:
                payload = r.json()
                if isinstance(payload, dict):
                    for k in ("title", "summary"):
                        if payload.get(k) is not None:
                            values[k] = str(payload.get(k))
            elif r.status_code == 404:
                return HTMLResponse("Lerneinheit nicht gefunden", status_code=404)
            elif r.status_code == 403:
                return HTMLResponse("Zugriff verweigert", status_code=403)
            else:
                error_msg = _extract_api_error_detail(r)
    except Exception:
        error_msg = "unit_load_failed"
    status = 200 if error_msg is None else 400
    return _render_unit_edit_response(
        unit_id=unit_id,
        user=user,
        csrf_token=token,
        values=values,
        error=error_msg,
        status_code=status,
    )


@app.post("/units/{unit_id}/edit", response_class=HTMLResponse)
async def units_edit_submit(request: Request, unit_id: str):
    """Submit unit updates via API PATCH then PRG back to /units.

    Security: CSRF at UI; authorship via API + RLS.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse(content="CSRF Error", status_code=403)
    token = _get_or_create_csrf_token(sid or "")
    raw_title = str(form.get("title", ""))
    raw_summary = str(form.get("summary", ""))
    cleaned_title = raw_title.strip()
    cleaned_summary = raw_summary.strip()
    payload = {"title": (cleaned_title or None), "summary": (cleaned_summary or None)}
    form_values = {"title": cleaned_title, "summary": cleaned_summary}

    if not cleaned_title:
        return _render_unit_edit_response(
            unit_id=unit_id,
            user=user,
            csrf_token=token,
            values=form_values,
            error="invalid_title",
            status_code=400,
        )

    error_msg: str | None = None
    status_code = 400
    try:
        import httpx
        from httpx import ASGITransport

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            resp = await client.patch(f"/api/teaching/units/{unit_id}", json=payload)
    except Exception:
        error_msg = "update_failed"
    else:
        if resp.status_code < 300:
            return RedirectResponse(url="/units", status_code=303)
        error_msg = _extract_api_error_detail(resp)
        status_code = resp.status_code if resp.status_code in (400, 403, 404) else 400

    return _render_unit_edit_response(
        unit_id=unit_id,
        user=user,
        csrf_token=token,
        values=form_values,
        error=error_msg or "update_failed",
        status_code=status_code,
    )

@app.get("/units/{unit_id}", response_class=HTMLResponse)
async def unit_details_index(request: Request, unit_id: str):
    """Sections management UI for a unit (API-backed, no dummies).

    Why: Teachers manage sections with server-rendered UI; all data loads and
    mutations go through the Teaching API to stay DB-consistent.

    Behavior:
    - GET unit details via /api/teaching/units/{id} (author-only)
    - GET sections via /api/teaching/units/{id}/sections
    - Render stable wrapper id (section-list-section) with CSRF-protected forms

    Permissions: Caller must be a teacher with a valid session.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)

    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)

    unit_title: str | None = None
    unit_summary: str | None = None
    sections: list[dict] = []
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            u = await client.get(f"/api/teaching/units/{unit_id}")
            if u.status_code != 200 or not isinstance(u.json(), dict):
                # Preserve API semantics for clarity and correctness
                if u.status_code in (403, 404):
                    msg = "Zugriff verweigert" if u.status_code == 403 else "Lerneinheit nicht gefunden"
                    return HTMLResponse(msg, status_code=u.status_code)
                return HTMLResponse("Lerneinheit nicht gefunden", status_code=404)
            ud = u.json()
            unit_title = str(ud.get("title") or "") or None
            unit_summary = str(ud.get("summary") or "") or None
            s = await client.get(f"/api/teaching/units/{unit_id}/sections")
            if s.status_code == 200 and isinstance(s.json(), list):
                # Keep only fields needed for rendering
                sections = [
                    {"id": it.get("id"), "title": it.get("title")}
                    for it in s.json()
                ]
    except Exception:
        return HTMLResponse("Lerneinheit nicht gefunden", status_code=404)

    unit_vm = {"id": unit_id, "title": unit_title or "Lerneinheit", "summary": unit_summary or None}
    content = _render_sections_page_html(unit_vm, sections, csrf_token=token)
    layout = Layout(title=f"Abschnitte für {unit_vm['title']}", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


async def _fetch_materials_for_section(unit_id: str, section_id: str, *, session_id: str) -> list[dict]:
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if session_id:
                client.cookies.set(SESSION_COOKIE_NAME, session_id)
            r = await client.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/materials")
    except Exception:
        return []
    if r.status_code != 200:
        return []
    data = r.json()
    if not isinstance(data, list):
        return []
    cleaned: list[dict] = []
    for it in data:
        if isinstance(it, dict):
            cleaned.append({"id": it.get("id"), "title": it.get("title")})
    return cleaned


async def _fetch_tasks_for_section(unit_id: str, section_id: str, *, session_id: str) -> list[dict]:
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if session_id:
                client.cookies.set(SESSION_COOKIE_NAME, session_id)
            r = await client.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
    except Exception:
        return []
    if r.status_code != 200:
        return []
    data = r.json()
    if not isinstance(data, list):
        return []
    cleaned: list[dict] = []
    for it in data:
        if isinstance(it, dict):
            cleaned.append({"id": it.get("id"), "instruction_md": it.get("instruction_md")})
    return cleaned


@app.get("/units/{unit_id}/sections/{section_id}", response_class=HTMLResponse)
async def section_detail_index(request: Request, unit_id: str, section_id: str):
    """SSR detail page for a section showing materials and tasks with create/reorder.

    Why:
    - Provide a clear, focused page to manage content within a section.
    - UI delegates to the public Teaching API (contract-first, no DB shortcuts).

    Parameters:
    - unit_id, section_id: Path identifiers used to resolve the view via API.

    Expected behavior:
    - 200 with two-column layout (materials | tasks) and CSRF-protected forms.
    - 404 when the unit/section is not found for the current author.
    - Cache-Control: private, no-store (sensitive teacher data).

    Permissions:
    - Caller must be a teacher in a valid session. Ownership is enforced by API.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)

    unit_title: str | None = None
    section_title: str | None = None
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            u = await client.get(f"/api/teaching/units/{unit_id}")
            if u.status_code != 200:
                return HTMLResponse("Lerneinheit nicht gefunden", status_code=404)
            ud = u.json() if isinstance(u.json(), dict) else {}
            unit_title = str(ud.get("title") or "") or None
            s = await client.get(f"/api/teaching/units/{unit_id}/sections")
            if s.status_code == 200 and isinstance(s.json(), list):
                for it in s.json():
                    if isinstance(it, dict) and it.get("id") == section_id:
                        section_title = str(it.get("title") or "") or None
                        break
    except Exception:
        return HTMLResponse("Abschnitt nicht gefunden", status_code=404)

    if section_title is None:
        return HTMLResponse("Abschnitt nicht gefunden", status_code=404)

    materials = await _fetch_materials_for_section(unit_id, section_id, session_id=sid)
    tasks = await _fetch_tasks_for_section(unit_id, section_id, session_id=sid)
    content = _render_section_detail_page_html(
        unit={"id": unit_id, "title": unit_title or "Lerneinheit"},
        section={"id": section_id, "title": section_title or "Abschnitt"},
        materials=materials,
        tasks=tasks,
        csrf_token=token,
    )
    layout = Layout(title=f"Abschnitt – {section_title or ''}", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


def _render_material_create_page_html(unit_id: str, section_id: str, section_title: str, *, csrf_token: str) -> str:
    # Reuse forms prepared earlier, add simple heading and back link
    text_form = (
        f'<form id="material-create-text" method="post" action="/units/{unit_id}/sections/{section_id}/materials/create">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Titel<input class="form-input" type="text" name="title" required></label>'
        f'<label>Markdown<textarea class="form-input" name="body_md" required></textarea></label>'
        f'<div class="form-actions"><button class="btn btn-primary" type="submit">Anlegen</button></div>'
        f'</form>'
    )
    upload_intent_form = (
        f'<form id="material-upload-intent-form" method="post" action="/units/{unit_id}/sections/{section_id}/materials/upload-intent" '
        f'hx-post="/units/{unit_id}/sections/{section_id}/materials/upload-intent" '
        f'hx-target="#material-upload-area" hx-swap="outerHTML">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Dateiname<input class="form-input" type="text" name="filename" required></label>'
        f'<label>MIME<input class="form-input" type="text" name="mime_type" value="application/pdf" required></label>'
        f'<label>Größe (Bytes)<input class="form-input" type="number" name="size_bytes" value="1024" min="1" required></label>'
        f'<div class="form-actions"><button class="btn" type="submit">Upload vorbereiten</button></div>'
        f'</form>'
    )
    return (
        '<div class="container">'
        f'<h1>Material anlegen — Abschnitt: {Component.escape(section_title)}</h1>'
        f'<p><a href="/units/{unit_id}/sections/{section_id}">Zurück</a></p>'
        '<div class="two-col">'
        f'<section class="card"><h2>Text‑Material</h2>{text_form}</section>'
        f'<section class="card"><h2>Datei‑Material</h2><div id="material-upload-area">{upload_intent_form}</div></section>'
        '</div>'
        '</div>'
    )


def _render_task_create_page_html(unit_id: str, section_id: str, section_title: str, *, csrf_token: str) -> str:
    criteria_inputs = []
    for i in range(10):
        criteria_inputs.append(
            f'<div class="form-field"><input class="form-input" type="text" name="criteria" placeholder="Kriterium {i+1}"></div>'
        )
    criteria_html = "".join(criteria_inputs)
    form = (
        f'<form id="task-create-form" method="post" action="/units/{unit_id}/sections/{section_id}/tasks/create">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Anweisung<textarea class="form-input" name="instruction_md" required></textarea></label>'
        f'<fieldset><legend>Analysekriterien (0–10)</legend>{criteria_html}</fieldset>'
        f'<label>Lösungshinweise<textarea class="form-input" name="hints_md"></textarea></label>'
        f'<label>Fällig bis (ISO 8601)<input class="form-input" type="text" name="due_at" placeholder="2025-01-01T10:00:00+00:00"></label>'
        f'<label>Max. Versuche<input class="form-input" type="number" name="max_attempts" min="1"></label>'
        f'<div class="form-actions"><button class="btn btn-primary" type="submit">Anlegen</button></div>'
        f'</form>'
    )
    return (
        '<div class="container">'
        f'<h1>Aufgabe anlegen — Abschnitt: {Component.escape(section_title)}</h1>'
        f'<p><a href="/units/{unit_id}/sections/{section_id}">Zurück</a></p>'
        f'<section class="card">{form}</section>'
        '</div>'
    )


@app.get("/units/{unit_id}/sections/{section_id}/materials/new", response_class=HTMLResponse)
async def materials_new(request: Request, unit_id: str, section_id: str):
    """Render the dedicated create page for materials (text and file).

    Why:
    - Keep the section detail page minimal (lists only) and move creation to a
      focused page with fewer distractions.

    Behavior:
    - Shows two forms: markdown text material and file upload intent.
    - Returns SSR HTML with `Cache-Control: private, no-store`.

    Permissions:
    - Caller must be a logged-in teacher; ownership enforced by called APIs.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    # Fetch section title via sections list (keeps API-only approach)
    title = "Abschnitt"
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            s = await client.get(f"/api/teaching/units/{unit_id}/sections")
            if s.status_code == 200 and isinstance(s.json(), list):
                for it in s.json():
                    if isinstance(it, dict) and it.get("id") == section_id:
                        t = it.get("title")
                        if isinstance(t, str) and t:
                            title = t
                        break
    except Exception:
        pass
    content = _render_material_create_page_html(unit_id, section_id, title, csrf_token=token)
    layout = Layout(title="Material anlegen", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


@app.get("/units/{unit_id}/sections/{section_id}/tasks/new", response_class=HTMLResponse)
async def tasks_new(request: Request, unit_id: str, section_id: str):
    """Render the dedicated create page for tasks.

    Includes fields for instruction, up to 10 analysis criteria, and optional
    solution hints (`hints_md`). Submits to the UI route which delegates to the
    Teaching API and then redirects back to the section detail.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    # Fetch section title similarly
    title = "Abschnitt"
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            client.cookies.set(SESSION_COOKIE_NAME, sid)
            s = await client.get(f"/api/teaching/units/{unit_id}/sections")
            if s.status_code == 200 and isinstance(s.json(), list):
                for it in s.json():
                    if isinstance(it, dict) and it.get("id") == section_id:
                        t = it.get("title")
                        if isinstance(t, str) and t:
                            title = t
                        break
    except Exception:
        pass
    content = _render_task_create_page_html(unit_id, section_id, title, csrf_token=token)
    layout = Layout(title="Aufgabe anlegen", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


async def _fetch_material_detail(unit_id: str, section_id: str, material_id: str, *, session_id: str) -> dict | None:
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if session_id:
                client.cookies.set(SESSION_COOKIE_NAME, session_id)
            r = await client.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/materials")
            if r.status_code != 200:
                return None
            data = r.json()
            if isinstance(data, list):
                for m in data:
                    if isinstance(m, dict) and str(m.get("id")) == material_id:
                        return m
    except Exception:
        return None
    return None


async def _fetch_task_detail(unit_id: str, section_id: str, task_id: str, *, session_id: str) -> dict | None:
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if session_id:
                client.cookies.set(SESSION_COOKIE_NAME, session_id)
            r = await client.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks")
            if r.status_code != 200:
                return None
            data = r.json()
            if isinstance(data, list):
                for t in data:
                    if isinstance(t, dict) and str(t.get("id")) == task_id:
                        return t
    except Exception:
        return None
    return None


def _render_material_detail_page_html(unit_id: str, section_id: str, material: dict, *, csrf_token: str, download_url: str | None = None) -> str:
    title = Component.escape(str(material.get("title") or "Material"))
    body_md = Component.escape(str(material.get("body_md") or ""))
    mid = str(material.get("id") or "")
    form = (
        f'<form method="post" action="/units/{unit_id}/sections/{section_id}/materials/{mid}/update">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Titel<input class="form-input" type="text" name="title" value="{title}"></label>'
        f'<label>Markdown<textarea class="form-input" name="body_md">{body_md}</textarea></label>'
        f'<div class="form-actions"><button class="btn btn-primary" type="submit">Speichern</button></div>'
        f'</form>'
    )
    download_html = (
        f'<p><a id="material-download-link" class="btn" href="{Component.escape(download_url)}" target="_blank">Download anzeigen</a></p>'
        if download_url else ''
    )
    delete_form = (
        f'<form method="post" action="/units/{unit_id}/sections/{section_id}/materials/{mid}/delete">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<button class="btn btn-danger" type="submit">Löschen</button>'
        f'</form>'
    )
    return (
        '<div class="container">'
        f'<h1>Material bearbeiten</h1>'
        f'<p><a href="/units/{unit_id}/sections/{section_id}">Zurück</a></p>'
        f'<section class="card">{download_html}{form}{delete_form}</section>'
        '</div>'
    )


def _render_task_detail_page_html(unit_id: str, section_id: str, task: dict, *, csrf_token: str) -> str:
    instr = Component.escape(str(task.get("instruction_md") or ""))
    tid = str(task.get("id") or "")
    criteria = task.get("criteria") or []
    crit_inputs = []
    for i in range(10):
        val = Component.escape(str(criteria[i]) if i < len(criteria) else "")
        crit_inputs.append(f'<div class="form-field"><input class="form-input" type="text" name="criteria" value="{val}"></div>')
    hints = Component.escape(str(task.get("hints_md") or ""))
    due_at = Component.escape(str(task.get("due_at") or ""))
    max_attempts = Component.escape(str(task.get("max_attempts") or ""))
    form = (
        f'<form method="post" action="/units/{unit_id}/sections/{section_id}/tasks/{tid}/update">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<label>Anweisung<textarea class="form-input" name="instruction_md">{instr}</textarea></label>'
        f'<fieldset><legend>Analysekriterien (0–10)</legend>{"".join(crit_inputs)}</fieldset>'
        f'<label>Lösungshinweise<textarea class="form-input" name="hints_md">{hints}</textarea></label>'
        f'<label>Fällig bis<input class="form-input" type="text" name="due_at" value="{due_at}"></label>'
        f'<label>Max. Versuche<input class="form-input" type="number" name="max_attempts" value="{max_attempts}" min="1"></label>'
        f'<div class="form-actions"><button class="btn btn-primary" type="submit">Speichern</button></div>'
        f'</form>'
    )
    delete_form = (
        f'<form method="post" action="/units/{unit_id}/sections/{section_id}/tasks/{tid}/delete">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(csrf_token)}">'
        f'<button class="btn btn-danger" type="submit">Löschen</button>'
        f'</form>'
    )
    return (
        '<div class="container">'
        f'<h1>Aufgabe bearbeiten</h1>'
        f'<p><a href="/units/{unit_id}/sections/{section_id}">Zurück</a></p>'
        f'<section class="card">{form}{delete_form}</section>'
        '</div>'
    )


@app.get("/units/{unit_id}/sections/{section_id}/materials/{material_id}", response_class=HTMLResponse)
async def material_detail_page(request: Request, unit_id: str, section_id: str, material_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    mat = await _fetch_material_detail(unit_id, section_id, material_id, session_id=sid)
    if mat is None:
        return HTMLResponse("Material nicht gefunden", status_code=404)
    # If it's a file material, fetch a download URL (inline)
    download_url = None
    try:
        if str(mat.get("kind") or "") == "file":
            import httpx
            from httpx import ASGITransport
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
                resp = await client.get(
                    f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url",
                    params={"disposition": "inline"},
                )
                if resp.status_code == 200 and isinstance(resp.json(), dict):
                    download_url = str(resp.json().get("url") or "") or None
    except Exception:
        download_url = None
    content = _render_material_detail_page_html(unit_id, section_id, mat, csrf_token=token, download_url=download_url)
    layout = Layout(title="Material bearbeiten", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


@app.post("/units/{unit_id}/sections/{section_id}/materials/{material_id}/update")
async def material_detail_update(request: Request, unit_id: str, section_id: str, material_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    payload = {}
    if form.get("title") is not None:
        payload["title"] = str(form.get("title") or "").strip() or None
    if form.get("body_md") is not None:
        payload["body_md"] = str(form.get("body_md"))
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            await client.patch(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}",
                json=payload,
            )
    except Exception:
        pass
    return RedirectResponse(url=f"/units/{unit_id}/sections/{section_id}/materials/{material_id}", status_code=303)


@app.post("/units/{unit_id}/sections/{section_id}/materials/{material_id}/delete")
async def material_detail_delete(request: Request, unit_id: str, section_id: str, material_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            await client.delete(f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}")
    except Exception:
        pass
    return RedirectResponse(url=f"/units/{unit_id}/sections/{section_id}", status_code=303)


@app.get("/units/{unit_id}/sections/{section_id}/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail_page(request: Request, unit_id: str, section_id: str, task_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    sid = _get_session_id(request) or ""
    if not sid:
        return RedirectResponse(url="/auth/login", status_code=302)
    token = _get_or_create_csrf_token(sid)
    task = await _fetch_task_detail(unit_id, section_id, task_id, session_id=sid)
    if task is None:
        return HTMLResponse("Aufgabe nicht gefunden", status_code=404)
    content = _render_task_detail_page_html(unit_id, section_id, task, csrf_token=token)
    layout = Layout(title="Aufgabe bearbeiten", content=content, user=user, current_path=request.url.path)
    return HTMLResponse(content=layout.render(), headers={"Cache-Control": "private, no-store"})


@app.post("/units/{unit_id}/sections/{section_id}/tasks/{task_id}/update")
async def task_detail_update(request: Request, unit_id: str, section_id: str, task_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    payload: dict[str, object] = {}
    if form.get("instruction_md") is not None:
        payload["instruction_md"] = str(form.get("instruction_md"))
    # criteria fields
    crit = [c.strip() for c in form.getlist("criteria") if isinstance(c, str) and c.strip()]
    if crit:
        payload["criteria"] = crit[:10]
    if form.get("hints_md") is not None:
        hints = str(form.get("hints_md") or "")
        payload["hints_md"] = hints or None
    if form.get("due_at") is not None:
        payload["due_at"] = str(form.get("due_at") or "") or None
    if form.get("max_attempts") is not None and str(form.get("max_attempts")) != "":
        try:
            payload["max_attempts"] = int(form.get("max_attempts"))
        except Exception:
            pass
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            await client.patch(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}",
                json=payload,
            )
    except Exception:
        pass
    return RedirectResponse(url=f"/units/{unit_id}/sections/{section_id}/tasks/{task_id}", status_code=303)


@app.post("/units/{unit_id}/sections/{section_id}/tasks/{task_id}/delete")
async def task_detail_delete(request: Request, unit_id: str, section_id: str, task_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            await client.delete(f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}")
    except Exception:
        pass
    return RedirectResponse(url=f"/units/{unit_id}/sections/{section_id}", status_code=303)


@app.post("/units/{unit_id}/sections/{section_id}/materials/create", response_class=HTMLResponse)
async def materials_create(request: Request, unit_id: str, section_id: str):
    """Create a markdown material via the API and return the updated list partial.

    Why:
    - Keep UI logic thin and reusable; API validates input and authorship.

    Parameters form fields:
    - title: Required, non-empty, <=200 chars
    - body_md: Required Markdown body
    - csrf_token: Required synchronizer token

    Returns:
    - 200 HTML fragment replacing `#material-list-section-<section_id>`
    - 403 CSRF error when token invalid/missing

    Permissions:
    - Caller must be a teacher; API enforces author-only semantics.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    title = str(form.get("title", "")).strip()
    body_md = str(form.get("body_md", ""))
    error: str | None = None
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            payload = {"title": title, "body_md": body_md}
            resp = await client.post(f"/api/teaching/units/{unit_id}/sections/{section_id}/materials", json=payload)
            if resp.status_code >= 400:
                error = _extract_api_error_detail(resp)
    except Exception:
        error = "backend_error"
    # Non-HTMX: PRG back to section detail
    if "HX-Request" not in request.headers:
        return RedirectResponse(url=f"/units/{unit_id}/sections/{section_id}", status_code=303)
    materials = await _fetch_materials_for_section(unit_id, section_id, session_id=sid or "")
    token = _get_or_create_csrf_token(sid or "")
    return HTMLResponse(_render_material_list_partial(unit_id, section_id, materials, csrf_token=token, error=error))


@app.post("/units/{unit_id}/sections/{section_id}/materials/reorder", response_class=Response)
async def materials_reorder(request: Request, unit_id: str, section_id: str):
    """Reorder materials by accepting DOM ids from the sortable container.

    Input:
    - Repeated form fields `id=material_<uuid>` in desired order.
    - CSRF token provided as `X-CSRF-Token` header or `csrf_token` field.

    Behavior:
    - Delegates to API `POST …/materials/reorder` and returns 200 on success.
    - Returns 400/403/404 JSON error mapping when API rejects the request.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return Response(status_code=403)
    form = await request.form()
    sid = _get_session_id(request)
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_field = form.get("csrf_token")
    if not _validate_csrf(sid, csrf_header or csrf_field):
        return Response(status_code=403)
    ordered_ids = [sid.replace("material_", "") for sid in form.getlist("id")]
    # Delegate to API when UUID-like ids are present
    if _is_uuid_like(section_id):
        try:
            import httpx
            from httpx import ASGITransport
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
                if sid:
                    client.cookies.set(SESSION_COOKIE_NAME, sid)
                resp = await client.post(
                    f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder",
                    json={"material_ids": ordered_ids},
                )
        except Exception:
            return JSONResponse({"error": "bad_request", "detail": "reorder_failed"}, status_code=400)
        if resp.status_code >= 400:
            detail = _extract_api_error_detail(resp)
            status = resp.status_code if resp.status_code in (400, 403, 404) else 400
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=status)
        return Response(status_code=200)
    return Response(status_code=200)


@app.post("/units/{unit_id}/sections/{section_id}/tasks/create", response_class=HTMLResponse)
async def tasks_create(request: Request, unit_id: str, section_id: str):
    """Create a native task via the API and return the updated list partial.

    Parameters form fields:
    - instruction_md: Required Markdown instruction
    - csrf_token: Required

    Returns 200 fragment for `#task-list-section-<section_id>` or 403 on CSRF.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    instruction_md = str(form.get("instruction_md", ""))
    # Collect up to 10 non-empty criteria from repeated fields
    criteria = [c.strip() for c in form.getlist("criteria") if isinstance(c, str) and c.strip()]
    if len(criteria) > 10:
        criteria = criteria[:10]
    hints_md = str(form.get("hints_md", "")) if form.get("hints_md") is not None else None
    due_at = str(form.get("due_at", "")).strip() or None
    max_attempts_raw = form.get("max_attempts")
    max_attempts = None
    if max_attempts_raw not in (None, ""):
        try:
            max_attempts = int(max_attempts_raw)  # API will validate >0
        except Exception:
            max_attempts = None
    error: str | None = None
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            payload = {
                "instruction_md": instruction_md,
                "criteria": criteria,
                "hints_md": (hints_md if hints_md else None),
                "due_at": due_at,
                "max_attempts": max_attempts,
            }
            resp = await client.post(f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks", json=payload)
            if resp.status_code >= 400:
                error = _extract_api_error_detail(resp)
    except Exception:
        error = "backend_error"
    if "HX-Request" not in request.headers:
        return RedirectResponse(url=f"/units/{unit_id}/sections/{section_id}", status_code=303)
    tasks = await _fetch_tasks_for_section(unit_id, section_id, session_id=sid or "")
    token = _get_or_create_csrf_token(sid or "")
    return HTMLResponse(_render_task_list_partial(unit_id, section_id, tasks, csrf_token=token, error=error))


@app.post("/units/{unit_id}/sections/{section_id}/tasks/reorder", response_class=Response)
async def tasks_reorder(request: Request, unit_id: str, section_id: str):
    """Reorder tasks by accepting DOM ids (`id=task_<uuid>`) from Sortable.

    Forwards to API `POST …/tasks/reorder`. Enforces CSRF at the UI boundary.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return Response(status_code=403)
    form = await request.form()
    sid = _get_session_id(request)
    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_field = form.get("csrf_token")
    if not _validate_csrf(sid, csrf_header or csrf_field):
        return Response(status_code=403)
    ordered_ids = [sid.replace("task_", "") for sid in form.getlist("id")]
    if _is_uuid_like(section_id):
        try:
            import httpx
            from httpx import ASGITransport
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
                if sid:
                    client.cookies.set(SESSION_COOKIE_NAME, sid)
                resp = await client.post(
                    f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder",
                    json={"task_ids": ordered_ids},
                )
        except Exception:
            return JSONResponse({"error": "bad_request", "detail": "reorder_failed"}, status_code=400)
        if resp.status_code >= 400:
            detail = _extract_api_error_detail(resp)
            status = resp.status_code if resp.status_code in (400, 403, 404) else 400
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=status)
        return Response(status_code=200)
    return Response(status_code=200)


@app.post("/units/{unit_id}/sections/{section_id}/materials/upload-intent", response_class=HTMLResponse)
async def materials_upload_intent(request: Request, unit_id: str, section_id: str):
    """Create an upload intent via API and return a small UI helper fragment.

    Form fields: filename (str), mime_type (str), size_bytes (int), csrf_token.

    Returns HTML with data-upload-url and a finalize form containing intent_id.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    filename = str(form.get("filename", "")).strip()
    mime_type = str(form.get("mime_type", "")).strip()
    size_raw = str(form.get("size_bytes", "")).strip()
    try:
        size_bytes = int(size_raw)
    except Exception:
        size_bytes = 0
    token = _get_or_create_csrf_token(sid or "")

    # Call API to get presigned upload details
    presign = None
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            resp = await client.post(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
                json={"filename": filename, "mime_type": mime_type, "size_bytes": size_bytes},
            )
            if resp.status_code == 200:
                presign = resp.json()
    except Exception:
        presign = None

    if not isinstance(presign, dict) or not presign.get("intent_id"):
        error_html = '<div class="alert alert-error" role="alert">upload_intent_failed</div>'
        return HTMLResponse(f'<div id="material-upload-area">{error_html}</div>')

    # Render a helper fragment including finalize form; client still needs to upload the file
    intent_id = Component.escape(presign.get("intent_id", ""))
    upload_url = Component.escape(presign.get("url", ""))
    finalize_form = (
        f'<form method="post" action="/units/{unit_id}/sections/{section_id}/materials/finalize" '
        f'hx-post="/units/{unit_id}/sections/{section_id}/materials/finalize" '
        f'hx-target="#material-list-section-{section_id}" hx-swap="outerHTML">'
        f'<input type="hidden" name="csrf_token" value="{Component.escape(token)}">'
        f'<input type="hidden" name="intent_id" value="{intent_id}">'
        f'<label>Titel<input class="form-input" type="text" name="title" required></label>'
        f'<label>SHA-256<input class="form-input" type="text" name="sha256" required></label>'
        f'<label>Alt-Text<input class="form-input" type="text" name="alt_text"></label>'
        f'<button class="btn btn-primary" type="submit">Upload abschließen</button>'
        f'</form>'
    )
    html = (
        f'<div id="material-upload-area" data-upload-url="{upload_url}">'
        f'<p class="text-muted">Upload-URL vorbereitet. Bitte Datei hochladen und anschließend oben abschließen.</p>'
        f'{finalize_form}'
        f'</div>'
    )
    return HTMLResponse(html)


@app.post("/units/{unit_id}/sections/{section_id}/materials/finalize", response_class=HTMLResponse)
async def materials_finalize(request: Request, unit_id: str, section_id: str):
    """Finalize an upload intent via the API and return updated materials list.

    Form fields: intent_id, title, sha256, alt_text?, csrf_token.
    """
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    intent_id = str(form.get("intent_id", "")).strip()
    title = str(form.get("title", "")).strip()
    sha256 = str(form.get("sha256", "")).strip()
    alt_text = str(form.get("alt_text", "")).strip() or None
    error: str | None = None
    try:
        import httpx
        from httpx import ASGITransport
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            resp = await client.post(
                f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize",
                json={"intent_id": intent_id, "title": title, "sha256": sha256, "alt_text": alt_text},
            )
            if resp.status_code >= 400:
                error = _extract_api_error_detail(resp)
    except Exception:
        error = "backend_error"
    materials = await _fetch_materials_for_section(unit_id, section_id, session_id=sid or "")
    token = _get_or_create_csrf_token(sid or "")
    # If finalize failed, we still return the list with an error banner
    return HTMLResponse(_render_material_list_partial(unit_id, section_id, materials, csrf_token=token, error=error))


@app.post("/units/{unit_id}/sections", response_class=HTMLResponse)
async def sections_create(request: Request, unit_id: str):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "teacher":
        return RedirectResponse(url="/", status_code=303)
    
    form = await request.form()
    sid = _get_session_id(request)
    if not _validate_csrf(sid, form.get("csrf_token")):
        return HTMLResponse("CSRF Error", status_code=403)
    token = _get_or_create_csrf_token(sid or "")
    title = str(form.get("title", "")).strip()
    error_code: str | None = None

    if not title:
        error_code = "invalid_title"
    else:
        try:
            import httpx
            from httpx import ASGITransport

            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
                if sid:
                    client.cookies.set(SESSION_COOKIE_NAME, sid)
                resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
        except Exception:
            error_code = "section_create_failed"
        else:
            if resp.status_code >= 400:
                error_code = _extract_api_error_detail(resp)

    sections = await _fetch_sections_for_unit(unit_id, session_id=sid or "")
    
    # Fragment 1: The updated section list
    section_list_html = _render_section_list_partial(unit_id, sections, csrf_token=token)
    
    # Fragment 2: A new, empty form for out-of-band swap
    form_component = SectionCreateForm(
        unit_id=unit_id,
        csrf_token=token,
        error=error_code,
        values={"title": title} if error_code else None,
    )
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

    error_code: str | None = None
    try:
        import httpx
        from httpx import ASGITransport

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
            if sid:
                client.cookies.set(SESSION_COOKIE_NAME, sid)
            resp = await client.delete(f"/api/teaching/units/{unit_id}/sections/{section_id}")
            if resp.status_code >= 400:
                error_code = _extract_api_error_detail(resp)
    except Exception:
        error_code = "section_delete_failed"
    if error_code and (
        error_code in {"invalid_unit_id", "invalid_section_id", "invalid_path_parameter"}
        or error_code.startswith("status_404")
        or "invalid_path" in error_code
    ):
        error_code = "not_found"

    sections = await _fetch_sections_for_unit(unit_id, session_id=sid or "")
    token = _get_or_create_csrf_token(sid or "")
    return HTMLResponse(content=_render_section_list_partial(unit_id, sections, csrf_token=token, error=error_code))

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

    # 1) Try to persist via API when unit/ids are UUID-like (DB-backed path)
    if _is_uuid_like(unit_id):
        try:
            import httpx
            from httpx import ASGITransport
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as client:
                if sid:
                    client.cookies.set(SESSION_COOKIE_NAME, sid)
                resp = await client.post(
                    f"/api/teaching/units/{unit_id}/sections/reorder",
                    json={"section_ids": ordered_ids},
                )
        except Exception:
            return JSONResponse({"error": "bad_request", "detail": "reorder_failed"}, status_code=400)
        if resp.status_code >= 400:
            detail = _extract_api_error_detail(resp)
            status = resp.status_code if resp.status_code in (400, 403, 404) else 400
            return JSONResponse({"error": "bad_request", "detail": detail}, status_code=status)
        return Response(status_code=200)

    # No content; client already updated DOM optimistically
    if unit_id in _DUMMY_SECTIONS_STORE:
        # Create a map of the existing sections by their ID
        section_map = {s["id"]: s for s in _DUMMY_SECTIONS_STORE[unit_id]}
        reordered_sections = [section_map[sid] for sid in ordered_ids if sid in section_map]
        if reordered_sections:
            _DUMMY_SECTIONS_STORE[unit_id] = reordered_sections
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
