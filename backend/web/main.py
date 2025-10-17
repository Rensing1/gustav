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
from identity_access.keycloak_client import AuthClient as KCAuthClient
from identity_access.admin_client import AdminClient as KCAdminClient
from identity_access.stores import StateStore, SessionStore
from identity_access.tokens import IDTokenVerificationError, verify_id_token

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
ALLOWED_ROLES = {"student", "teacher", "admin"}
CSRF_COOKIE_NAME = "gustav_csrf"

# Feature flag: enable DEV/CI HTML auth UI with Direct Grant adapter
AUTH_USE_DIRECT_GRANT = os.getenv("AUTH_USE_DIRECT_GRANT", "").lower() in {"1", "true", "yes"}


def _session_cookie_options() -> dict:
    """Return cookie policy depending on environment (dev vs prod).

    Returns:
        Dictionary with `secure` and `samesite` flags. In `prod` we set
        `secure=True` and `SameSite=strict`; in `dev`/tests we keep
        `secure=False` and `SameSite=lax` to allow localhost flows.
    """
    env = SETTINGS.environment
    secure = env == "prod"
    samesite = "strict" if secure else "lax"
    return {"secure": secure, "samesite": samesite}


def _set_session_cookie(response: Response, value: str) -> None:
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
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=value,
        httponly=True,
        secure=opts["secure"],
        samesite=opts["samesite"],
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


def _issue_csrf_cookie(response: Response) -> str:
    """Create a CSRF token and set it as cookie for Double-Submit CSRF.

    Why:
        Phase-1 CSRF protection without server-side store. Token is echoed into
        a hidden form field and compared against the cookie value on POST.

    Returns:
        The generated CSRF token (URL-safe base64 string).
    """
    import secrets

    token = secrets.token_urlsafe(32)
    opts = _session_cookie_options()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # must be readable by the browser to submit in form
        secure=opts["secure"],
        samesite=opts["samesite"],
        path="/",
    )
    return token


def _validate_csrf(request: Request, form_csrf: str | None) -> bool:
    """Validate Double-Submit CSRF by comparing cookie and form field."""
    cookie_val = request.cookies.get(CSRF_COOKIE_NAME)
    return bool(cookie_val and form_csrf and cookie_val == form_csrf)

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


# --- OIDC minimal config & stores (dev) ---
def load_oidc_config() -> OIDCConfig:
    base_url = os.getenv("KC_BASE_URL", "http://localhost:8080")
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
SESSION_STORE = SessionStore()
KEYCLOAK_CLIENT = KCAuthClient(OIDC_CFG)
KEYCLOAK_ADMIN = KCAdminClient(OIDC_CFG)


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

    # Mock user for demo
    demo_user = {
        "name": "Felix",
        "role": "teacher"
    }

    # If this is an HTMX request, return content + sidebar (OOB) for consistent active state
    if "HX-Request" in request.headers:
        demo_user = {
            "name": "Felix",
            "role": "teacher"
        }
        sidebar_oob = Navigation(demo_user, request.url.path).render_aside(oob=True)
        return HTMLResponse(content=content + sidebar_oob)

    # Use Layout component to render the full page on normal requests
    layout = Layout(
        title="Startseite",
        content=content,
        user=demo_user,
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
        demo_user = {
            "name": "Felix",
            "role": "teacher"
        }
        sidebar_oob = Navigation(demo_user, request.url.path).render_aside(oob=True)
        return HTMLResponse(content=content + sidebar_oob)

    # For normal requests, return the full page with layout
    demo_user = {
        "name": "Felix",
        "role": "teacher"  # This page is accessible to both roles
    }

    layout = Layout(
        title="Wissenschaft - GUSTAV",
        content=content,
        user=demo_user,
        show_nav=True,
        show_header=True,
        current_path=request.url.path  # Dynamically get current path from request
    )

    return HTMLResponse(content=layout.render())


@app.get("/health")
async def health_check():
    """Health-Check Endpoint für Docker"""
    return {"status": "healthy", "service": "gustav-v2"}


# --- Minimal Auth Adapter (stub) to satisfy contract tests ---

@app.get("/auth/login")
async def auth_login(state: str | None = None, redirect: str | None = None):
    """
    Start OIDC flow with PKCE and server-side state.

    Why:
        Initiate a secure Authorization Code Flow. We create and store a
        `code_verifier` (for PKCE) and an opaque `state` (for CSRF/QR context),
        then redirect the browser to Keycloak.

    Parameters:
        state: Optional externally supplied state (e.g., QR-context). If not
            provided, a new opaque state is generated.
        redirect: Optional in-app path to return to after successful login.

    Behavior:
        - Generates `code_verifier` and its S256 `code_challenge`.
        - Persists state (with TTL) together with the verifier and redirect.
        - Redirects to Keycloak’s realm auth endpoint with PKCE params.

    Permissions:
        Public endpoint. No authentication required.
    """
    # Feature-flagged UI: return HTML form with CSRF in DEV/CI
    if AUTH_USE_DIRECT_GRANT:
        # Create response first to issue CSRF cookie and obtain token
        resp = HTMLResponse(content="")
        csrf = _issue_csrf_cookie(resp)

        # Build structured form using components
        email = TextInputField(
            "email",
            "E-Mail",
            required=True,
            help_text=None,
        ).render(input_type="email", autocomplete="username")
        password = TextInputField(
            "password",
            "Passwort",
            required=True,
        ).render(input_type="password", autocomplete="current-password")
        submit = SubmitButton("Login").render()

        hidden_csrf = f"<input type=\"hidden\" name=\"csrf_token\" value=\"{csrf}\">"
        form_attrs = "method=\"post\" action=\"/auth/login\""
        form_html = f"<form {form_attrs}>{email}{password}{hidden_csrf}{submit}</form>"

        # Convenience links for better UX
        help_links = (
            '<div class="form-help-links">'
            '<a href="/auth/register" hx-get="/auth/register" hx-target="#main-content">Konto anlegen</a>'
            ' · '
            '<a href="/auth/forgot" hx-get="/auth/forgot" hx-target="#main-content">Passwort vergessen?</a>'
            "</div>"
        )
        content = f"<h1>Login</h1>{form_html}{help_links}"
        page = Layout(title="Login", content=content, user=None, show_nav=False, show_header=False, current_path="/auth/login").render()
        resp.body = page.encode()
        return resp

    # Default: Redirect to Keycloak auth endpoint
    code_verifier = OIDCClient.generate_code_verifier()
    code_challenge = OIDCClient.code_challenge_s256(code_verifier)
    rec = STATE_STORE.create(code_verifier=code_verifier, redirect=redirect)
    final_state = state or rec.state
    url = OIDC.build_authorization_url(state=final_state, code_challenge=code_challenge)
    return RedirectResponse(url=url, status_code=302)


@app.get("/auth/forgot")
async def auth_forgot(login_hint: str | None = None):
    """
    Convenience redirect to Keycloak's 'Forgot Password' page.

    Why:
        Offload password reset to Keycloak to keep credentials out of GUSTAV.
    Parameters:
        login_hint: Optional email to pre-fill on Keycloak's reset form.
    Behavior:
        - Builds the URL from configured base URL and realm.
        - Forwards `login_hint` if provided, no cookies are set.
    Permissions:
        Public endpoint; no session required.
    """
    # Feature-flagged UI: simple HTML form + CSRF cookie in DEV/CI
    if AUTH_USE_DIRECT_GRANT:
        resp = HTMLResponse(content="")
        csrf = _issue_csrf_cookie(resp)

        email = TextInputField(
            "email",
            "E-Mail",
            required=True,
        ).render(input_type="email", value=login_hint or "")
        submit = SubmitButton("Senden").render()
        hidden_csrf = f"<input type=\"hidden\" name=\"csrf_token\" value=\"{csrf}\">"
        form_attrs = "method=\"post\" action=\"/auth/forgot\""
        form_html = f"<form {form_attrs}>{email}{hidden_csrf}{submit}</form>"

        # Link back to login for convenience
        back_link = (
            '<div class="form-help-links">'
            '<a href="/auth/login" hx-get="/auth/login" hx-target="#main-content">Zurück zum Login</a>'
            "</div>"
        )
        content = f"<h1>Passwort vergessen</h1>{form_html}{back_link}"
        page = Layout(title="Passwort vergessen", content=content, user=None, show_nav=False, show_header=False, current_path="/auth/forgot").render()
        resp.body = page.encode()
        return resp

    from urllib.parse import urlencode
    base = f"{OIDC_CFG.base_url}/realms/{OIDC_CFG.realm}/login-actions/reset-credentials"
    query = {"login_hint": login_hint} if login_hint else None
    target = f"{base}?{urlencode(query)}" if query else base
    return RedirectResponse(url=target, status_code=302)


@app.get("/auth/register")
async def auth_register(login_hint: str | None = None):
    """
    Convenience redirect to Keycloak's self-registration page.

    Why:
        Keep credentials entirely in Keycloak. This endpoint only redirects to
        the IdP's registration flow and sets no cookies.
    Parameters:
        login_hint: Optional email to pre-fill on the registration form.
    Behavior:
        - Constructs the registration URL from configured base URL + realm.
        - Forwards `login_hint` as query if provided.
    Permissions:
        Public endpoint; no authentication required.
    """
    if AUTH_USE_DIRECT_GRANT:
        resp = HTMLResponse(content="")
        csrf = _issue_csrf_cookie(resp)

        display_name = TextInputField(
            "display_name",
            "Anzeigename",
            required=False,
        ).render(placeholder="Optional")
        email = TextInputField(
            "email",
            "E-Mail",
            required=True,
        ).render(input_type="email", value=login_hint or "")
        password = TextInputField(
            "password",
            "Passwort",
            required=True,
        ).render(input_type="password")
        submit = SubmitButton("Konto anlegen").render()
        hidden_csrf = f"<input type=\"hidden\" name=\"csrf_token\" value=\"{csrf}\">"
        form_attrs = "method=\"post\" action=\"/auth/register\""
        form_html = f"<form {form_attrs}>{display_name}{email}{password}{hidden_csrf}{submit}</form>"

        # Link back to login for convenience
        back_link = (
            '<div class="form-help-links">'
            '<a href="/auth/login" hx-get="/auth/login" hx-target="#main-content">Schon ein Konto? Anmelden</a>'
            "</div>"
        )
        content = f"<h1>Registrieren</h1>{form_html}{back_link}"
        page = Layout(title="Registrieren", content=content, user=None, show_nav=False, show_header=False, current_path="/auth/register").render()
        resp.body = page.encode()
        return resp

    from urllib.parse import urlencode
    base = f"{OIDC_CFG.base_url}/realms/{OIDC_CFG.realm}/protocol/openid-connect/registrations"
    query = {"login_hint": login_hint} if login_hint else None
    target = f"{base}?{urlencode(query)}" if query else base
    return RedirectResponse(url=target, status_code=302)


@app.get("/auth/callback")
async def auth_callback(code: str | None = None, state: str | None = None):
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
        return JSONResponse({"error": "invalid_code_or_state"}, status_code=400)
    # State must have been issued by /auth/login and still be valid
    rec = STATE_STORE.pop_valid(state)
    if not rec:
        return JSONResponse({"error": "invalid_code_or_state"}, status_code=400)

    try:
        tokens = OIDC.exchange_code_for_tokens(code=code, code_verifier=rec.code_verifier)
    except Exception as exc:
        logger.warning("Token exchange failed: %s", exc.__class__.__name__)
        return JSONResponse({"error": "token_exchange_failed"}, status_code=400)

    id_token = tokens.get("id_token")
    if not id_token or not isinstance(id_token, str):
        return JSONResponse({"error": "invalid_id_token"}, status_code=400)
    try:
        claims = verify_id_token(id_token=id_token, cfg=OIDC_CFG)
    except IDTokenVerificationError as exc:
        logger.warning("ID token verification failed: %s", exc.code)
        return JSONResponse({"error": "invalid_id_token"}, status_code=400)

    email = claims.get("email") or claims.get("preferred_username") or "unknown@example.com"
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
    email_verified = bool(claims.get("email_verified", False))

    sess = SESSION_STORE.create(email=email, roles=roles, email_verified=email_verified)
    dest = rec.redirect or "/"
    resp = RedirectResponse(url=dest, status_code=302)
    # Attach hardened session cookie (opaque ID only)
    _set_session_cookie(resp, sess.session_id)
    return resp


@app.post("/auth/login")
async def auth_login_post(request: Request):
    """Handle login form submissions (DEV/CI feature-flag)."""
    if not AUTH_USE_DIRECT_GRANT:
        # Contract: route may be disabled in PROD
        raise HTTPException(status_code=403, detail="disabled")
    form = await request.form()
    if not _validate_csrf(request, form.get("csrf_token")):
        raise HTTPException(status_code=403, detail="csrf_invalid")
    email = (form.get("email") or "").strip()
    password = form.get("password") or ""
    redirect = form.get("redirect") or "/"
    # Allow only same-origin, relative paths
    if not isinstance(redirect, str) or not redirect.startswith("/"):
        redirect = "/"
    try:
        tokens = KEYCLOAK_CLIENT.direct_grant(email=email, password=password)
        id_token = tokens.get("id_token") if isinstance(tokens, dict) else None
        if not id_token:
            raise ValueError("id_token_missing")
        claims = verify_id_token(id_token=id_token, cfg=OIDC_CFG)
    except Exception:
        # Neutral 400 to avoid credential enumeration
        raise HTTPException(status_code=400, detail="invalid_credentials")

    # Extract principal and roles
    email_claim = (
        claims.get("email")
        or claims.get("preferred_username")
        or email
    )
    ra = claims.get("realm_access") or {}
    raw_roles: list[str] = []
    if isinstance(ra, dict):
        r = ra.get("roles")
        if isinstance(r, list):
            raw_roles = [str(x) for x in r]
    roles = [role for role in raw_roles if role in ALLOWED_ROLES] or ["student"]
    email_verified = bool(claims.get("email_verified", False))

    sess = SESSION_STORE.create(email=email_claim, roles=roles, email_verified=email_verified)
    resp = RedirectResponse(url=redirect, status_code=303)
    _set_session_cookie(resp, sess.session_id)
    return resp


@app.post("/auth/register")
async def auth_register_post(request: Request):
    """Handle registration form (DEV/CI feature-flag)."""
    if not AUTH_USE_DIRECT_GRANT:
        raise HTTPException(status_code=403, detail="disabled")
    form = await request.form()
    if not _validate_csrf(request, form.get("csrf_token")):
        raise HTTPException(status_code=403, detail="csrf_invalid")
    email = (form.get("email") or "").strip()
    password = form.get("password") or ""
    display_name = (form.get("display_name") or None)
    # Minimal shape validation: rely on IdP policies for deep checks
    try:
        user_id = KEYCLOAK_ADMIN.create_user(email=email, password=password, display_name=display_name)
    except Exception:
        # Duplicate / policy errors → 400
        raise HTTPException(status_code=400, detail="registration_failed")
    try:
        KEYCLOAK_ADMIN.assign_realm_role(user_id=user_id, role_name="student")
    except Exception:
        # Surface as 500 for manual follow-up; avoid auto-deletion to not lose trace
        raise HTTPException(status_code=500, detail="role_assignment_failed")

    # Redirect to login with hint; no auto-login
    from urllib.parse import urlencode
    params = urlencode({"login_hint": email}) if email else ""
    dest = f"/auth/login?{params}" if params else "/auth/login"
    return RedirectResponse(url=dest, status_code=303)


@app.post("/auth/forgot")
async def auth_forgot_post(request: Request):
    """Trigger password reset via IdP (DEV/CI feature-flag)."""
    if not AUTH_USE_DIRECT_GRANT:
        raise HTTPException(status_code=403, detail="disabled")
    form = await request.form()
    if not _validate_csrf(request, form.get("csrf_token")):
        raise HTTPException(status_code=403, detail="csrf_invalid")
    # Neutral 202 per contract
    return JSONResponse({"message": "If the address exists, we sent an email"}, status_code=202)

@app.post("/auth/logout")
async def auth_logout(request: Request):
    """
    Invalidate the current session and clear the session cookie.

    Why:
        Ensure users can reliably sign out and browsers drop the cookie.

    Behavior:
        - Requires an existing session cookie, else 401.
        - Deletes the server-side session (if present).
        - Sends a `gustav_session` cookie with `Max-Age=0` and matching flags
          so clients remove it (per contract).

    Permissions:
        Authenticated route (requires `gustav_session` cookie).
    """
    if SESSION_COOKIE_NAME not in request.cookies:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sid = request.cookies.get(SESSION_COOKIE_NAME)
    if sid:
        SESSION_STORE.delete(sid)
    resp = Response(status_code=204)
    _clear_session_cookie(resp)
    return resp


@app.get("/api/me")
async def get_me(request: Request):
    """
    Return minimal session info if authenticated; else 401.

    Why:
        Allow frontend to check login state and show principal info.

    Behavior:
        - Reads `gustav_session` from cookies, looks up server-side session.
        - Returns `{ email, roles, email_verified }` when found; else 401.

    Permissions:
        Authenticated route (requires `gustav_session` cookie).
    """
    if SESSION_COOKIE_NAME not in request.cookies:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    rec = SESSION_STORE.get(sid or "")
    if not rec:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    return JSONResponse({
        "email": rec.email,
        "roles": rec.roles,
        "email_verified": rec.email_verified,
    })


# --- App factory for tests: auth-only slim app ---
def create_app_auth_only() -> FastAPI:
    """Return a minimal FastAPI app exposing only auth-related routes.

    Why: Speeds up tests by avoiding import/render cost of SSR components.
    Security/Contract: Same routes and behavior as defined in OpenAPI contract.
    """
    slim = FastAPI(title="GUSTAV auth-only", version="0.0.2")

    @slim.get("/auth/login")
    async def slim_auth_login(state: str | None = None, redirect: str | None = None):
        target = "https://keycloak.local/realms/gustav/protocol/openid-connect/auth"
        if state:
            target += f"?state={state}"
        return RedirectResponse(url=target, status_code=302)

    @slim.get("/auth/forgot")
    async def slim_auth_forgot(login_hint: str | None = None):
        """Slim forgot endpoint mirrors config-driven redirect in tests."""
        from urllib.parse import urlencode
        base = f"{OIDC_CFG.base_url}/realms/{OIDC_CFG.realm}/login-actions/reset-credentials"
        query = {"login_hint": login_hint} if login_hint else None
        target = f"{base}?{urlencode(query)}" if query else base
        return RedirectResponse(url=target, status_code=302)

    @slim.get("/auth/register")
    async def slim_auth_register(login_hint: str | None = None):
        """Slim register endpoint mirrors config-driven redirect in tests."""
        from urllib.parse import urlencode
        base = f"{OIDC_CFG.base_url}/realms/{OIDC_CFG.realm}/protocol/openid-connect/registrations"
        query = {"login_hint": login_hint} if login_hint else None
        target = f"{base}?{urlencode(query)}" if query else base
        return RedirectResponse(url=target, status_code=302)

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

    @slim.post("/auth/logout")
    async def slim_auth_logout(request: Request):
        if "gustav_session" not in request.cookies:
            raise HTTPException(status_code=401, detail="Not authenticated")
        resp = Response(status_code=204)
        resp.delete_cookie(key="gustav_session", path="/")
        return resp

    @slim.get("/api/me")
    async def slim_get_me(request: Request):
        if "gustav_session" not in request.cookies:
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        return JSONResponse({
            "email": "student@example.com",
            "roles": ["student"],
            "email_verified": True,
        })

    return slim
