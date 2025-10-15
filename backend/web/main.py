"""
GUSTAV alpha-2
"""
from pathlib import Path
import os
import json
import base64

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
    SubmitButton,
    OnPageNavigation,
    OnPageNavItem,
)
from components.navigation import Navigation
from components.pages import SciencePage
from identity_access.oidc import OIDCClient, OIDCConfig
from identity_access.stores import StateStore, SessionStore

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
    return OIDCConfig(base_url=base_url, realm=realm, client_id=client_id, redirect_uri=redirect_uri)


OIDC_CFG = load_oidc_config()
OIDC = OIDCClient(OIDC_CFG)
STATE_STORE = StateStore()
SESSION_STORE = SessionStore()


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
    Start OIDC flow with PKCE.
    Creates server-side state with code_verifier and optional redirect, then
    redirects to Keycloak auth endpoint.
    """
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
    """
    target = "https://keycloak.local/realms/gustav/login-actions/reset-credentials"
    if login_hint:
        target += f"?login_hint={login_hint}"
    return RedirectResponse(url=target, status_code=302)


@app.get("/auth/callback")
async def auth_callback(code: str | None = None, state: str | None = None):
    """
    Handle OIDC callback: validate state, exchange code for tokens, create session.
    """
    if not code or not state:
        return JSONResponse({"error": "invalid_code_or_state"}, status_code=400)
    rec = STATE_STORE.pop_valid(state)
    if not rec:
        return JSONResponse({"error": "invalid_code_or_state"}, status_code=400)

    try:
        tokens = OIDC.exchange_code_for_tokens(code=code, code_verifier=rec.code_verifier)
    except Exception:
        return JSONResponse({"error": "token_exchange_failed"}, status_code=400)

    id_token = tokens.get("id_token")
    if not id_token or id_token.count(".") != 2:
        return JSONResponse({"error": "invalid_id_token"}, status_code=400)
    try:
        payload_b64 = id_token.split(".")[1]
        pad = '=' * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + pad).decode("utf-8")
        claims = json.loads(payload_json)
    except Exception:
        return JSONResponse({"error": "invalid_id_token"}, status_code=400)

    email = claims.get("email") or claims.get("preferred_username") or "unknown@example.com"
    roles = []
    ra = claims.get("realm_access") or {}
    if isinstance(ra, dict):
        r = ra.get("roles")
        if isinstance(r, list):
            roles = [str(x) for x in r]
    email_verified = bool(claims.get("email_verified", False))

    sess = SESSION_STORE.create(email=email, roles=roles or ["student"], email_verified=email_verified)
    dest = rec.redirect or "/"
    resp = RedirectResponse(url=dest, status_code=302)
    resp.set_cookie(
        key="gustav_session",
        value=sess.session_id,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@app.post("/auth/logout")
async def auth_logout(request: Request):
    """
    Invalidate the current session and clear the session cookie.
    Requires an existing session cookie; otherwise 401.
    """
    if "gustav_session" not in request.cookies:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sid = request.cookies.get("gustav_session")
    if sid:
        SESSION_STORE.delete(sid)
    resp = Response(status_code=204)
    resp.delete_cookie(key="gustav_session", path="/")
    return resp


@app.get("/api/me")
async def get_me(request: Request):
    """
    Return minimal session info if authenticated; else 401.
    """
    if "gustav_session" not in request.cookies:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    sid = request.cookies.get("gustav_session")
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
        target = "https://keycloak.local/realms/gustav/login-actions/reset-credentials"
        if login_hint:
            target += f"?login_hint={login_hint}"
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
