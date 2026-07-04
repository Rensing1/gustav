"""Contracts for the web security header policy builder."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SOURCE = PROJECT_ROOT / "backend" / "web" / "main.py"


pytestmark = pytest.mark.anyio("asyncio")


def test_security_header_defaults_include_csp_and_prod_isolation() -> None:
    """Security headers should be built outside the FastAPI middleware."""

    from backend.web.security.headers import build_security_header_defaults

    headers = build_security_header_defaults(
        environment="prod",
        supabase_public_url="https://storage.example.test/rest/v1",
    )

    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "unsafe-eval" not in csp
    assert "connect-src 'self' https://storage.example.test" in csp
    assert "https://storage.example.test https://storage.example.test" not in csp
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_security_header_defaults_omit_prod_only_isolation_outside_prod() -> None:
    from backend.web.security.headers import build_security_header_defaults

    headers = build_security_header_defaults(environment="dev", supabase_public_url="")

    assert "Cross-Origin-Opener-Policy" not in headers
    assert "connect-src 'self';" in headers["Content-Security-Policy"]


async def test_security_header_middleware_installer_uses_runtime_environment() -> None:
    from backend.web.security.headers import install_security_headers_middleware

    app = FastAPI()
    environment = {"value": "prod"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    install_security_headers_middleware(
        app,
        environment_provider=lambda: environment["value"],
    )

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        prod_response = await client.get("/health")
        environment["value"] = "dev"
        dev_response = await client.get("/health")

    assert prod_response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "Cross-Origin-Opener-Policy" not in dev_response.headers
    assert "Strict-Transport-Security" in dev_response.headers


def test_main_delegates_security_header_policy_to_security_module() -> None:
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    wiring_source = (PROJECT_ROOT / "backend/web/main_middleware_wiring.py").read_text(encoding="utf-8")

    assert "install_security_headers_middleware(" in wiring_source
    assert "install_security_headers_middleware(" not in source
    assert "async def security_headers" not in source
    assert "build_security_header_defaults(" not in source
    assert "Content-Security-Policy" not in source
    assert "SUPABASE_PUBLIC_URL" not in source
