"""Lightweight auth-only FastAPI app for focused auth contract tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import secrets
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.identity_access.stores import SessionStore, StateStore
from backend.web.auth_runtime import load_oidc_config
from backend.web.auth_session import SESSION_COOKIE_NAME, set_session_cookie
from backend.web.routes.auth import auth_router


class _AuthOnlySettings:
    """Settings facade for the lightweight auth-only runtime."""

    def __init__(self, environment_provider: Callable[[], str]) -> None:
        self._environment_provider = environment_provider

    @property
    def environment(self) -> str:
        return self._environment_provider()


def create_app_auth_only(
    *,
    environment_provider: Callable[[], str] | None = None,
    oidc_config: object | None = None,
    state_store: object | None = None,
    session_store: object | None = None,
) -> FastAPI:
    """Create the slim auth app used by auth smoke and contract tests.

    Why:
        Auth tests need login, callback, and `/api/me` behavior without pulling
        in unrelated routers or DB-dependent wiring from the full web app.

    Permissions:
        This is a test helper only. It installs the real auth router but uses a
        deliberately lightweight callback stub instead of an OIDC roundtrip.
    """

    environment = environment_provider or (lambda: "dev")
    static_dir = Path(__file__).parent / "static"
    sub = FastAPI(title="GUSTAV (auth-only)", description="Auth slice", version="0.0.4")
    sub.state.runtime = SimpleNamespace(
        settings=_AuthOnlySettings(environment),
        oidc_config=oidc_config or load_oidc_config(),
        state_store=state_store or StateStore(),
        session_store=session_store or SessionStore(),
    )
    sub.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    sub.include_router(auth_router)

    @sub.get("/auth/callback")
    async def _callback_stub(request: Request, code: str | None = None, state: str | None = None):
        if (not code or not state) or (code == "invalid" or state == "invalid"):
            return JSONResponse(
                {"error": "invalid_code_or_state"},
                status_code=400,
                headers={"Cache-Control": "private, no-store"},
            )
        sid = secrets.token_urlsafe(24)
        resp = RedirectResponse(url="/", status_code=302)
        resp.headers["Cache-Control"] = "private, no-store"
        set_session_cookie(resp, sid, environment=environment())
        return resp

    @sub.get("/api/me")
    async def me_stub(request: Request):
        if SESSION_COOKIE_NAME not in request.cookies:
            return JSONResponse(
                {"error": "unauthenticated"},
                status_code=401,
                headers={"Cache-Control": "private, no-store"},
            )
        return JSONResponse(
            {
                "sub": "test-user",
                "roles": ["student"],
                "name": "",
                "expires_at": None,
            },
            headers={"Cache-Control": "private, no-store"},
        )

    return sub
