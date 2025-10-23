"""
GUSTAV alpha-2
"""
from pathlib import Path
import os
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from components import (
    Layout,
    MaterialCard,
    MaterialAction,
    TaskCard,
    HistoryEntry,
    TaskMetaItem,
    TextAreaField,
    FileUploadField,
    TextInputField,
    SubmitButton,
    OnPageNavigation,
    OnPageNavItem,
)
from components.navigation import Navigation
from components.pages import SciencePage
from identity_access.oidc import OIDCClient, OIDCConfig
from identity_access.stores import StateStore, SessionStore
from identity_access.domain import ALLOWED_ROLES
from datetime import datetime, timezone
from identity_access.tokens import IDTokenVerificationError, verify_id_token
# Import cookie_opts with a dual strategy to work both when importing as a
# package (backend.web.main) and when tests import this file as top-level
# module ("import main").
try:  # package-style import
    from .auth_utils import cookie_opts  # type: ignore
except Exception:  # pragma: no cover - test runner path
    from auth_utils import cookie_opts  # type: ignore

# Load .env for local dev/test so environment variables are available outside Docker
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; ignore if not available
    pass


class AuthSettings:
    """Central settings helper to derive runtime flags with optional overrides.

    Why:
        Keep environment handling (dev/prod/e2e) in one place so cookie
        hardening and other auth-related behavior can switch predictably.

    Behavior:
        - `environment` reads `GUSTAV_ENV` (default `dev`), unless overridden for tests.
        - Accepted values: `dev`, `prod` (and `e2e` treated like `dev`).
    """

    def __init__(self) -> None:
        self._env_override: str | None = None

    @property
    def environment(self) -> str:
        if self._env_override is not None:
            return self._env_override
        return os.getenv("GUSTAV_ENV", "dev").lower()

    def override_environment(self, value: str | None) -> None:
        self._env_override = value.lower() if value else None


logger = logging.getLogger("gustav.identity_access")
SETTINGS = AuthSettings()

SESSION_COOKIE_NAME = "gustav_session"

# Direct-Grant has been removed: all flows use browser-based redirects to Keycloak.


def _session_cookie_options() -> dict:
    """Return cookie policy depending on environment (dev vs prod).

    Delegates to the shared `cookie_opts` helper for consistency across
    modules. In `prod` we set `secure=True` and `SameSite=strict`; in
    `dev`/tests we keep `secure=False` and `SameSite=lax` to allow
    localhost flows.
    """
    return cookie_opts(SETTINGS.environment)


def _primary_role(roles: list[str]) -> str:
    """Return the primary role for SSR display using fixed priority.

    Why:
        Token role order is not guaranteed. To keep UI deterministic, choose
        by priority: admin > teacher > student. Defaults to 'student'.

    Examples:
        ["student", "teacher"] -> "teacher"
        ["admin"] -> "admin"
        [] -> "student"
    """
    priority = ["admin", "teacher", "student"]
    lowered = [r.lower() for r in roles if isinstance(r, str)]
    for r in priority:
        if r in lowered:
            return r
    return "student"


def _set_session_cookie(response: Response, value: str, *, max_age: int | None = None, request: Request | None = None) -> None:
    """Attach the gustav session cookie with hardened flags.

    Parameters:
        response: The outgoing response to attach the cookie to.
        value: Opaque session ID; never store PII in the cookie.

    Behavior:
        - Always sets `HttpOnly` to prevent JS access.
        - Uses environment-driven `Secure` and `SameSite` flags.
        - Path is `/` to cover the entire app; no Domain is set to avoid
          accidental subdomain leakage in multi-host setups.
    """
    opts = _session_cookie_options()
    secure_flag = opts["secure"]
    samesite_flag = opts["samesite"]
    # In production, degrade only for localhost-style hosts over plain HTTP (E2E/local reverse proxy)
    try:
        if SETTINGS.environment == "prod" and request is not None:
            host = request.headers.get("host") or request.url.hostname or ""
            xf_proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").lower()
            if ("localhost" in host or host.startswith("127.")) and xf_proto != "https":
                secure_flag = False
                samesite_flag = "lax"
    except Exception:
        pass
    if max_age is not None:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=value,
            httponly=True,
            secure=secure_flag,
            samesite=samesite_flag,
            path="/",
            max_age=max_age,
        )
    else:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=value,
            httponly=True,
            secure=secure_flag,
            samesite=samesite_flag,
            path="/",
        )


def _clear_session_cookie(response: Response) -> None:
    """Fully expire the gustav session cookie with matching flags.

    Behavior:
        - Sends an empty cookie with `Max-Age=0` so browsers delete it.
        - Uses the same `Secure`/`SameSite` profile as `_set_session_cookie`
          to ensure consistent deletion across environments.
    """
    opts = _session_cookie_options()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        httponly=True,
        secure=opts["secure"],
        samesite=opts["samesite"],
        path="/",
        expires=0,
        max_age=0,
    )


# Note: CSRF utilities removed with Direct-Grant UI removal.

# FastAPI App erstellen
# Default app (full web). For tests, an app factory may build a slimmer app.
app = FastAPI(
    title="GUSTAV alpha-2",
    description="KI-gestützte Lernplattform",
    version="0.0.2"
)

# Statische Dateien einbinden (CSS, JS, Bilder)
# Serve static assets from the app/static directory (reliable from repo root)
# Resolve static directory relative to this file, independent of CWD
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Import shared auth router and helpers from dedicated module
from routes.auth import auth_router
from routes.learning import learning_router
from routes.teaching import teaching_router
from routes.users import users_router


# --- OIDC minimal config & stores (dev) ---
def load_oidc_config() -> OIDCConfig:
    # Accept legacy KC_BASE for compatibility; prefer KC_BASE_URL
    base_url = os.getenv("KC_BASE_URL") or os.getenv("KC_BASE") or "http://localhost:8080"
    realm = os.getenv("KC_REALM", "gustav")
    client_id = os.getenv("KC_CLIENT_ID", "gustav-web")
    redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8100/auth/callback")
    public_base = os.getenv("KC_PUBLIC_BASE_URL", base_url)
    return OIDCConfig(
        base_url=base_url,
        realm=realm,
        client_id=client_id,
        redirect_uri=redirect_uri,
        public_base_url=public_base,
    )


OIDC_CFG = load_oidc_config()
OIDC = OIDCClient(OIDC_CFG)
STATE_STORE = StateStore()
# Session store: default to in-memory, allow DB-backed when configured
if os.getenv("SESSIONS_BACKEND", "memory").lower() == "db":
    try:
        from identity_access.stores_db import DBSessionStore  # optional dependency
        SESSION_STORE = DBSessionStore()
    except Exception:
        # Fallback to in-memory if DB store is not available/misconfigured
        SESSION_STORE = SessionStore()
else:
    SESSION_STORE = SessionStore()
# Note: Admin client removed; E2E tests use direct requests to Keycloak admin API


# --- Optional: Supabase Storage adapter wiring ---------------------------------
def _maybe_configure_supabase_storage() -> None:
    """Configure Supabase Storage adapter if environment and dependency are present.

    Why:
        In dev/prod we want real file uploads via Supabase. In tests, the
        dependency may not be installed and a fake adapter is injected.

    Behavior:
        - Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from env.
        - If both are set and supabase-py is importable, installs the adapter.
        - Otherwise, leaves the default NullStorageAdapter in place.

    Security:
        Does not log secrets; only logs adapter activation status.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return
    try:
        from supabase import create_client  # type: ignore
        from teaching.storage_supabase import SupabaseStorageAdapter  # type: ignore
        from routes import teaching as teaching_routes  # lazy import

        client = create_client(url, key)
        adapter = SupabaseStorageAdapter(client)
        teaching_routes.set_storage_adapter(adapter)
        logging.getLogger("gustav.storage").info("Supabase Storage adapter configured (bucket=materials)")
    except Exception as exc:  # pragma: no cover - best-effort wiring in non-test envs
        logging.getLogger("gustav.storage").warning(
            "Supabase adapter not configured (%s). Falling back to NullStorageAdapter.",
            exc.__class__.__name__,
        )


# Try to auto-configure storage for non-test environments
if os.getenv("GUSTAV_ENV", "dev").lower() in {"dev", "prod"}:
    _maybe_configure_supabase_storage()


# --- Auth Enforcement Middleware -------------------------------------------------

def _is_public_path(path: str) -> bool:
    """Paths that must remain accessible without a session (no redirect loop)."""
    return (
        path.startswith("/auth/")
        or path.startswith("/static/")
        or path == "/health"
        or path == "/favicon.ico"
    )


@app.middleware("http")
async def auth_enforcement(request: Request, call_next):
    """Enforce login for non-public routes with content-type aware responses.

    Rules:
    - Public: /auth/*, /health, /static/*, /favicon.ico
    - API (paths starting with /api/): 401 JSON when unauthenticated
    - HTMX requests: 401 with HX-Redirect header to /auth/login
    - HTML (default): 302 redirect to /auth/login when unauthenticated

    When authenticated, attaches `request.state.user` dict for SSR consumption.
    """
    path = request.url.path
    if _is_public_path(path):
        return await call_next(request)

    # API responses should be JSON 401 when not authenticated
    if path.startswith("/api/"):
        sid = request.cookies.get(SESSION_COOKIE_NAME)
        try:
            rec = SESSION_STORE.get(sid or "")
        except Exception as exc:
            # Defensive: treat backend/session DB errors as unauthenticated (fail closed)
            logger.warning("Session store get failed (API): %s", exc.__class__.__name__)
            rec = None
        if not rec:
            # Contract nuances:
            # - Learning endpoints document `private, max-age=0` for error responses.
            # - Other privacy‑sensitive APIs prefer `no-store` (e.g., /api/me).
            cache_value = "private, max-age=0" if path.startswith("/api/learning/") else "no-store"
            return JSONResponse(
                {"error": "unauthenticated"},
                status_code=401,
                headers={"Cache-Control": cache_value},
            )
        # Attach user info and proceed
        request.state.user = {"sub": rec.sub, "name": getattr(rec, "name", ""), "roles": rec.roles}
        return await call_next(request)

    # Non-API routes
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    try:
        rec = SESSION_STORE.get(sid or "")
    except Exception as exc:
        # Defensive: do not blow up the page; redirect to login instead
        logger.warning("Session store get failed (HTML): %s", exc.__class__.__name__)
        rec = None
    if not rec:
        # HTMX partial request? Use HX-Redirect
        if "HX-Request" in request.headers:
            return Response(status_code=401, headers={"HX-Redirect": "/auth/login"})
        # Default: redirect HTML to login
        return RedirectResponse(url="/auth/login", status_code=302)

    # Attach principal for SSR (deterministic primary role)
    role = _primary_role(rec.roles)
    request.state.user = {"sub": rec.sub, "name": getattr(rec, "name", ""), "role": role, "roles": rec.roles}
    return await call_next(request)


def build_home_content() -> str:
    navigation_html = OnPageNavigation(
        items=[
            OnPageNavItem(anchor="materials", label="Materialien", icon="📚"),
            OnPageNavItem(anchor="tasks", label="Aufgaben", icon="✏️"),
        ],
        orientation="horizontal",
    ).render()

    return f"""
    <div class="home">
        {build_hero_section()}
        <section class="home-section home-section--nav" aria-label="Seitenüberblick">
            {navigation_html}
        </section>
        {build_material_section()}
        {build_task_section()}
    </div>
    """


def build_hero_section() -> str:
    return """
    <section class="home-hero">
        <div class="home-hero__intro">
            <h1>Willkommen bei GUSTAV</h1>
            <p class="text-muted">
                Die KI-gestützte Lernplattform für moderne Bildung – datenschutzkonform und offen.
            </p>
        </div>
        <div class="home-hero__stats" aria-labelledby="home-stats-title">
            <h2 id="home-stats-title" class="sr-only">Heutige Kennzahlen</h2>
            <div class="home-hero__stats-grid">
                <div class="home-hero__stat">
                    <span>Neue Materialien</span>
                    <strong>3</strong>
                </div>
                <div class="home-hero__stat">
                    <span>Offene Aufgaben</span>
                    <strong>1</strong>
                </div>
                <div class="home-hero__stat">
                    <span>Feedback ausstehend</span>
                    <strong>2</strong>
                </div>
            </div>
        </div>
    </section>
    """


def build_material_section() -> str:
    materials = [
        MaterialCard(
            material_id="materials-ebook",
            title="Arbeitsblatt Photosynthese",
            icon="📄",
            badge="PDF",
            preview_html="""
                <p>
                    Lies dir das Arbeitsblatt durch und notiere drei Beobachtungen zur Pflanzenatmung.
                </p>
            """,
            meta_items=[
                ("Zuletzt aktualisiert", "12.09.2025"),
                ("Autor", "Frau Müller"),
            ],
            actions=[
                MaterialAction(
                    label="Vorschau öffnen",
                    href="/materials/ebook/preview",
                    primary=False,
                    target="_blank",
                ),
                MaterialAction(
                    label="Download",
                    href="/materials/ebook/download",
                    primary=True,
                ),
            ],
            collapse_label="Vorschau & Details",
            is_open=True,
        ).render(),
        MaterialCard(
            material_id="materials-video",
            title="Video: Lichtabhängige Reaktion",
            icon="🎬",
            badge="Video",
            preview_html="""
                <p>
                    Erklärt die lichtabhängige Reaktion mit Fokus auf Chlorophyll.
                </p>
            """,
            meta_items=[
                ("Dauer", "4:30 Minuten"),
                ("Quelle", "GUSTAV Medienarchiv"),
            ],
            actions=[
                MaterialAction(
                    label="Video ansehen",
                    href="/materials/video/play",
                    primary=True,
                ),
            ],
            collapse_label="Beschreibung anzeigen",
            is_open=False,
        ).render(),
        MaterialCard(
            material_id="materials-h5p",
            title="Interaktive Übung: Brüche addieren",
            icon="🧩",
            badge="H5P",
            preview_html="""
                <iframe
                    src="/h5p/7"
                    title="H5P Aufgabe Brüche addieren"
                    loading="lazy"
                    allowfullscreen
                ></iframe>
            """,
            meta_items=[
                ("Bearbeitungszeit", "10 Minuten"),
            ],
            actions=[
                MaterialAction(
                    label="Vollbild",
                    is_button=True,
                    data_action="toggle-fullscreen",
                ),
                MaterialAction(
                    label="Offline-Paket",
                    href="/materials/h5p/7/download",
                    primary=False,
                ),
            ],
            collapse_label="Aufgabe anzeigen",
            is_open=True,
        ).render(),
    ]

    materials.extend(
        [
            MaterialCard(
            material_id="materials-guideline",
            title="Lehrplan-Update",
            icon="📘",
            badge="Guideline",
            preview_html="""
                <p>
                    Kurzbericht zu neuen Bildungsstandards im Themenfeld Photosynthese.
                </p>
            """,
            actions=[
                MaterialAction(
                    label="Bericht lesen",
                    href="/materials/guideline",
                    primary=False,
                ),
            ],
            is_open=False,
        ).render(),
            MaterialCard(
            material_id="materials-slides",
            title="Unterrichtsfolien",
            icon="🖥️",
            badge="Präsentation",
            preview_html="""
                <p>
                    12‑seitiges Deck mit Illustrationen zur Licht- und Dunkelreaktion.
                </p>
            """,
            actions=[
                MaterialAction(
                    label="Anzeigen",
                    href="/materials/slides",
                    primary=True,
                ),
            ],
            is_open=False,
        ).render(),
        ]
    )

    return f"""
    <section class="home-section" id="materials" aria-labelledby="materials-title">
        <header class="home-section__header">
            <h2 id="materials-title">Materialien der Woche</h2>
            <p class="home-section__subtitle">
                Kuratierte Inhalte für deinen Kurs, sortiert nach Aktualität.
            </p>
        </header>
        <div class="material-list">
            {' '.join(materials)}
        </div>
    </section>
    """


def build_task_section() -> str:
    answer_field = TextAreaField(
        "answer",
        "Deine Antwort",
        required=True,
        help_text="Maximal 500 Zeichen.",
    )
    answer_html = answer_field.render(rows=6, placeholder="Beschreibe hier den Versuchsaufbau...")

    upload_field = FileUploadField(
        "attachment",
        "Arbeitsblatt hochladen (optional)",
        help_text="Unterstützt PDF, PNG oder JPG.",
    )
    upload_html = upload_field.render(accept=".pdf,.png,.jpg")

    submit_button = SubmitButton(
        "Antwort einreichen",
        loading_label="Antwort wird gespeichert...",
    )

    form_html = f"""
    <form class="task-submit-form">
        {answer_html}
        {upload_html}
        <div class="form-actions">
            {submit_button.render()}
        </div>
    </form>
    """

    history_entries = [
        HistoryEntry(
            label="Versuch 1",
            timestamp="Eingereicht am 14.09.2025, 09:14 Uhr",
            content_html="""
                <div class="history-content">
                    <p><strong>Antwort:</strong> Die Pflanze benötigt Licht, Wasser und CO₂...</p>
                </div>
            """,
            feedback_html="""
                <div class="history-feedback">
                    <p><strong>Feedback:</strong> Gute Erklärung! Erwähne noch die Rolle der Stomata.</p>
                </div>
            """,
        ),
        HistoryEntry(
            label="Versuch 2",
            timestamp="Eingereicht am 16.09.2025, 10:02 Uhr",
            content_html="""
                <div class="history-content">
                    <p><strong>Antwort:</strong> Die Lichtreaktion findet in den Thylakoiden statt...</p>
                </div>
            """,
            status_html="""
                <div class="history-status">
                    <p>Status: Feedback wird generiert...</p>
                </div>
            """,
            expanded=True,
        ),
    ]

    task_card = TaskCard(
        task_id="tasks-photosynthese",
        title="Aufgabe 3: Fotosynthese erklären",
        instruction_html="""
            <p>
                Beschreibe den Energiefluss in der lichtabhängigen Reaktion und nenne die entstehenden Produkte.
            </p>
        """,
        status_badge="Neu",
        attempts_info="Verbleibende Versuche: 1 von 3",
        meta_items=[
            TaskMetaItem(label="Fällig bis", value="20.09.2025"),
            TaskMetaItem(label="Bewertung", value="10 Punkte"),
        ],
        history_entries=history_entries,
        feedback_banner_html="""
            <div class="alert alert-info">
                KI-Feedback wird innerhalb von 30 Sekunden bereitgestellt.
            </div>
        """,
        form_html=form_html,
        form_actions_html="""
            <button class="btn btn-secondary" type="button" data-action="check-status">
                Status prüfen
            </button>
        """,
    )

    return f"""
    <section class="home-section" id="tasks" aria-labelledby="tasks-title">
        <header class="home-section__header">
            <h2 id="tasks-title">Aktuelle Aufgabe</h2>
            <p class="home-section__subtitle">
                Reiche deine Lösung ein und verfolge das Feedback der KI.
            </p>
        </header>
        <div class="task-area">
            {task_card.render()}
        </div>
    </section>
    """


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Startseite anzeigen mit Python Components"""

    content = build_home_content()

    # If this is an HTMX request, return content + sidebar (OOB) for consistent active state
    if "HX-Request" in request.headers:
        user = getattr(request.state, "user", None)
        sidebar_oob = Navigation(user, request.url.path).render_aside(oob=True)
        return HTMLResponse(content=content + sidebar_oob)

    # Use Layout component to render the full page on normal requests
    user = getattr(request.state, "user", None)
    layout = Layout(
        title="Startseite",
        content=content,
        user=user,
        show_nav=True,
        show_header=True,
        current_path=request.url.path  # Dynamically get current path from request
    )

    return HTMLResponse(content=layout.render())


@app.get("/wissenschaft", response_class=HTMLResponse)
async def wissenschaft(request: Request):
    """
    Science page route - Uses the SciencePage component for clean separation.
    Supports both full page loads and HTMX partial updates.
    """
    # Create the science page component
    science_page = SciencePage()
    content = science_page.render()

    # Check if this is an HTMX request (partial page update)
    if "HX-Request" in request.headers:
        # Return content + sidebar OOB update for consistent active highlighting
        user = getattr(request.state, "user", None)
        sidebar_oob = Navigation(user, request.url.path).render_aside(oob=True)
        return HTMLResponse(content=content + sidebar_oob)

    # For normal requests, return the full page with layout
    layout = Layout(
        title="Wissenschaft - GUSTAV",
        content=content,
        user=getattr(request.state, "user", None),
        show_nav=True,
        show_header=True,
        current_path=request.url.path  # Dynamically get current path from request
    )

    return HTMLResponse(content=layout.render())


@app.get("/health")
async def health_check():
    """Lightweight health and runtime diagnostics.

    Returns:
        JSON with service status and selected runtime diagnostics to help
        local and CI environments validate configuration quickly. Avoids
        leaking secrets; DB checks report only current_user when possible.
    """
    # Base status
    info: dict[str, object] = {
        "status": "healthy",
        "service": "gustav-v2",
        "environment": SETTINGS.environment,
    }

    # Session backend details
    backend = "memory"
    store_type = type(SESSION_STORE).__name__
    try:
        from identity_access.stores_db import DBSessionStore  # type: ignore
        if isinstance(SESSION_STORE, DBSessionStore):
            backend = "db"
    except Exception:
        pass
    info["sessions_backend"] = backend
    info["session_store"] = store_type

    # Config snapshots (non-sensitive)
    try:
        public_base = OIDC_CFG.public_base_url or OIDC_CFG.base_url
        info["oidc"] = {"base": public_base, "realm": OIDC_CFG.realm}
        info["redirect_uri"] = OIDC_CFG.redirect_uri
    except Exception:
        pass

    # Optional DB checks: report current_user for app and sessions DSNs
    def _whoami(dsn_env: str) -> str:
        import os as _os
        dsn = _os.getenv(dsn_env)
        if not dsn:
            return "unset"
        try:
            import psycopg as _pg  # type: ignore
            with _pg.connect(dsn, connect_timeout=1) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute("select current_user")
                    row = cur.fetchone()
                    return str(row[0]) if row else "unknown"
        except Exception:
            return "unavailable"

    info["db_current_user"] = _whoami("DATABASE_URL")
    info["session_db_current_user"] = _whoami("SESSION_DATABASE_URL")

    # Expose parsed DSN hosts (non-sensitive) to help diagnose connectivity
    try:
        import os as _os
        from urllib.parse import urlparse as _u
        for key in ("DATABASE_URL", "SESSION_DATABASE_URL"):
            d = _os.getenv(key)
            if d:
                p = _u(d)
                info[f"{key.lower()}_host"] = f"{p.hostname}:{p.port or ''}"
            else:
                info[f"{key.lower()}_host"] = "unset"
    except Exception:
        pass

    # Security: avoid caching diagnostics in intermediaries/browsers
    return JSONResponse(info, headers={"Cache-Control": "no-store"})


# --- Minimal Auth Adapter (stub) to satisfy contract tests ---

# Auth callback remains defined in this module to keep test monkeypatching stable

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str | None = None, state: str | None = None):
    """
    Complete the OIDC authorization code flow after Keycloak redirect.

    Why:
        Exchanges the authorization code for tokens, verifies the ID token and
        persists a server-side session so the browser only needs an opaque cookie.
    Parameters:
        code: Authorization code returned by Keycloak (query parameter).
        state: Opaque state created in /auth/login to prevent CSRF and replay.
    Behavior:
        - Validates code/state and performs the token exchange via OIDC client.
        - Verifies the ID token signature and claims, extracts e-mail and roles.
        - Creates a session, sets hardened `gustav_session` cookie, redirects.
        - Returns HTTP 400 without setting cookies on any failure path.
    Permissions:
        Only requests that present a previously issued state (from /auth/login)
        succeed. No additional course role is required; the endpoint is part of
        the public login flow.
    """
    if not code or not state:
        # Security: do not cache auth failure responses
        return JSONResponse({"error": "invalid_code_or_state"}, status_code=400, headers={"Cache-Control": "no-store"})
    # State must have been issued by /auth/login and still be valid
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

    # Phase 2: Nonce check — reject if ID token nonce does not match the stored state nonce
    # Why: `state` protects the authorization request (CSRF); `nonce` protects the
    # ID token against replay by binding it to our stored login/register intent.
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
    # Restrict roles to our known realm roles; ignore custom project roles.
    roles = [role for role in raw_roles if role in ALLOWED_ROLES]
    if len(roles) != len(raw_roles):
        unknown = [role for role in raw_roles if role not in ALLOWED_ROLES]
        if unknown:
            logger.debug("Ignoring unknown Keycloak roles: %s", unknown)
    if not roles:
        roles = ["student"]
    # Resolve display name: prefer custom claim from Keycloak user attribute mapping,
    # then standard `name`, else fallback to local part of email (privacy-friendly)
    display_name = (
        claims.get("gustav_display_name")
        or claims.get("name")
        or (email.split("@")[0] if email else "Benutzer")
    )

    # Create server-side session and retain id_token for end-session logout
    sess = SESSION_STORE.create(sub=sub, roles=roles, name=str(display_name), id_token=id_token)
    dest = rec.redirect or "/"
    resp = RedirectResponse(url=dest, status_code=302)
    # Attach hardened session cookie (opaque ID only); in PROD, align Max-Age with server-side TTL
    max_age = sess.ttl_seconds if SETTINGS.environment == "prod" else None
    _set_session_cookie(resp, sess.session_id, max_age=max_age, request=request)
    return resp


# Note: POST endpoints for login/register/forgot were removed together with
# the Direct-Grant UI flow. All interactive flows happen on Keycloak.

 # Logout route is provided by the shared auth router


@app.get("/api/me")
async def get_me(request: Request):
    """
    Return current UserContextDTO if authenticated; else 401.

    Why:
        Allow the frontend to determine login state and display principal info
        without exposing PII such as email. Follows the contract in
        `api/openapi.yml`.

    Behavior:
        - Reads `gustav_session` from cookies and looks up the server-side session.
        - On success returns `{ sub, roles, name, expires_at }`.
        - On failure returns `401 { error: "unauthenticated" }`.
        - All responses are non-cacheable and include `Cache-Control: no-store`.

    Permissions:
        Authenticated route (requires valid `gustav_session` cookie).
    """
    if SESSION_COOKIE_NAME not in request.cookies:
        # Security: prevent caching of auth state responses
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "no-store"})
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    try:
        rec = SESSION_STORE.get(sid or "")
    except Exception as exc:
        # Defensive: treat store failures like missing/expired session
        logger.warning("Session store get failed (/api/me): %s", exc.__class__.__name__)
        rec = None
    if not rec:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "no-store"})
    # Serialize expires_at as UTC ISO-8601 if available
    exp_iso = None
    if rec.expires_at:
        exp_iso = datetime.fromtimestamp(rec.expires_at, tz=timezone.utc).isoformat(timespec="seconds")
    return JSONResponse({
        "sub": rec.sub,
        "roles": rec.roles,
        "name": getattr(rec, "name", ""),
        "expires_at": exp_iso,
    }, headers={"Cache-Control": "no-store"})

# Register auth routes on the full application
app.include_router(auth_router)
app.include_router(learning_router)
app.include_router(teaching_router)
app.include_router(users_router)


# --- App factory for tests: auth-only slim app ---
def create_app_auth_only() -> FastAPI:
    """Return a minimal FastAPI app exposing only auth-related routes.

    Why: Speeds up tests by avoiding import/render cost of SSR components.
    Security/Contract: Same routes and behavior as defined in OpenAPI contract.
    """
    slim = FastAPI(title="GUSTAV auth-only", version="0.0.2")

    # Reuse the main app's auth router to avoid drift.
    # Note: Slim app still overrides /auth/callback and /api/me below for test stubs.
    slim.include_router(auth_router)

    @slim.get("/auth/callback")
    async def slim_auth_callback(code: str | None = None, state: str | None = None):
        if not code or not state:
            return JSONResponse({"error": "invalid_code_or_state"}, status_code=400)
        if not (code == "valid-code" and state == "opaque-state"):
            return JSONResponse({"error": "invalid_code_or_state"}, status_code=400)
        resp = RedirectResponse(url="/", status_code=302)
        resp.set_cookie(
            key="gustav_session",
            value="stub-session",
            httponly=True,
            samesite="lax",
            path="/",
        )
        return resp

    # Logout via shared router (GET /auth/logout) already included above

    @slim.get("/api/me")
    async def slim_get_me(request: Request):
        if "gustav_session" not in request.cookies:
            return JSONResponse({"error": "unauthenticated"}, status_code=401, headers={"Cache-Control": "no-store"})
        return JSONResponse({
            "sub": "stub-user",
            "roles": ["student"],
            "name": "Max Musterschüler",
            "expires_at": None,
        }, headers={"Cache-Control": "no-store"})

    return slim
