"""Runtime tests for the internal Browser-BFF token session API.

Why:
    The SvelteKit server calls this path without a browser session cookie.
    The endpoint must therefore behave like a machine API and never fall back
    to `/auth/login` redirects.
"""

from __future__ import annotations

from pathlib import Path
import sys

import httpx
import pytest
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.bff_sessions import BFFSessionStore  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _payload(*, access_token: str, refresh_token: str | None = "refresh-1", id_token: str = "id-1", expires_at: int = 4102444800) -> dict[str, object]:
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "expires_at": expires_at,
    }


@pytest.mark.anyio
async def test_bff_session_internal_api_supports_machine_roundtrip_without_browser_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "BFF_SESSION_STORE", BFFSessionStore())

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        created = await client.put("/backend-internal/app/bff-session", json=_payload(access_token="access-1"))

        assert created.status_code == 200
        assert created.headers.get("location") is None
        assert created.headers.get("Cache-Control") == "private, no-store"
        created_payload = created.json()
        session_id = str(created_payload["session_id"])

        loaded = await client.get(
            "/backend-internal/app/bff-session",
            headers={"x-gustav-bff-session": session_id},
        )
        assert loaded.status_code == 200
        assert loaded.headers.get("location") is None
        assert loaded.json()["access_token"] == "access-1"

        updated = await client.patch(
            "/backend-internal/app/bff-session",
            headers={"x-gustav-bff-session": session_id},
            json=_payload(access_token="access-2", refresh_token="refresh-2", id_token="id-2"),
        )
        assert updated.status_code == 200
        assert updated.headers.get("location") is None
        assert updated.json()["access_token"] == "access-2"

        deleted = await client.delete(
            "/backend-internal/app/bff-session",
            headers={"x-gustav-bff-session": session_id},
        )
        assert deleted.status_code == 204
        assert deleted.headers.get("location") is None

        missing_after_delete = await client.get(
            "/backend-internal/app/bff-session",
            headers={"x-gustav-bff-session": session_id},
        )
        assert missing_after_delete.status_code == 204
        assert missing_after_delete.headers.get("location") is None


@pytest.mark.anyio
async def test_bff_session_internal_api_missing_header_paths_keep_api_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "BFF_SESSION_STORE", BFFSessionStore())

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        read_missing = await client.get("/backend-internal/app/bff-session")
        assert read_missing.status_code == 204
        assert read_missing.headers.get("location") is None

        patch_missing = await client.patch(
            "/backend-internal/app/bff-session",
            json=_payload(access_token="access-2"),
        )
        assert patch_missing.status_code == 401
        assert patch_missing.headers.get("location") is None
        assert patch_missing.json() == {"error": "unauthenticated"}

        delete_missing = await client.delete("/backend-internal/app/bff-session")
        assert delete_missing.status_code == 204
        assert delete_missing.headers.get("location") is None
