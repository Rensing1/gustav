"""App isolation and scheduling contracts for the profile adapter."""

from __future__ import annotations

import asyncio
import os
import threading
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest

from backend.identity_access.cli_tokens import DBCLITokenStore
from backend.tests.utils.db import is_safe_db_test_dsn, require_db_or_skip
from backend.web.main import create_app
from backend.web.profile_providers import ProfileProviders

pytestmark = pytest.mark.anyio("asyncio")


class IdentityStub:
    def __init__(self, name: str) -> None:
        self.user = {"email": "student@example.com", "attributes": {"display_name": [name]}}
        self.writes: list[str] = []

    def get_user(self, *, user_id: str) -> dict[str, object]:
        return deepcopy(self.user)

    def update_user(self, *, user_id: str, payload: dict[str, object]) -> None:
        self.writes.append(user_id)
        self.user.update(deepcopy(payload))


def client_for(
    identity: IdentityStub, *, email: str = "", sub: str = "student-profile", role: str = "student"
) -> httpx.AsyncClient:
    app = create_app(
        profile_providers=ProfileProviders(
            identity=lambda: identity, verify_claims=lambda token: {"email": email}
        ),
        access_token_verifier=lambda token, cfg: {"sub": sub, "realm_access": {"roles": [role]}},
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://test", "Authorization": "Bearer test.jwt"},
    )


async def test_two_apps_keep_profile_reads_and_writes_isolated() -> None:
    first, second = IdentityStub("First"), IdentityStub("Second")
    async with client_for(first) as a, client_for(second) as b:
        for _ in range(2):
            assert (await a.get("/api/app/profile")).json()["display_name"] == "First"
            assert (await b.get("/api/app/profile")).json()["display_name"] == "Second"
        changed = await a.patch("/api/app/profile/display-name", json={"display_name": "Changed"})
        assert changed.status_code == 204
        assert (await b.get("/api/app/profile")).json()["display_name"] == "Second"
        assert (await a.get("/api/app/profile")).json()["display_name"] == "Changed"
    assert first.writes == ["student-profile"]
    assert second.writes == []


async def test_two_apps_keep_verified_fallback_claims_isolated() -> None:
    class UnavailableIdentity(IdentityStub):
        def get_user(self, *, user_id: str) -> dict[str, object]:
            raise RuntimeError("identity unavailable")

    async with (
        client_for(UnavailableIdentity("A"), email="a@example.com") as a,
        client_for(UnavailableIdentity("B"), email="b@example.com") as b,
    ):
        for client, email in ((a, "a@example.com"), (b, "b@example.com"), (a, "a@example.com")):
            response = await client.get("/api/app/profile")
            assert response.status_code == 200
            assert response.json()["email"] == email


async def test_apps_keep_default_cli_stores_isolated() -> None:
    async with (
        client_for(IdentityStub("A"), role="teacher") as a,
        client_for(IdentityStub("B"), role="teacher") as b,
    ):
        created = await a.post(
            "/api/app/profile/cli-tokens", json={"label": "A", "scopes": ["read"]}
        )
        assert created.status_code == 201
        token_id = created.json()["record"]["id"]
        assert (await b.get("/api/app/profile/cli-tokens")).json() == []
        assert (await b.delete(f"/api/app/profile/cli-tokens/{token_id}")).status_code == 404
        assert (await a.get("/api/app/profile/cli-tokens")).json()[0]["revoked_at"] is None


@pytest.mark.db_write
async def test_profile_cli_lifecycle_and_owner_boundary_use_real_database(monkeypatch) -> None:
    require_db_or_skip()
    dsn = os.environ["SESSION_TEST_DSN"]
    assert is_safe_db_test_dsn(dsn)
    # Select the existing production adapter through the same runtime settings.
    monkeypatch.setenv("CLI_TOKENS_BACKEND", "db")
    monkeypatch.setenv("SESSION_DATABASE_URL", dsn)
    owner, stranger = str(uuid4()), str(uuid4())
    import psycopg

    try:
        async with (
            client_for(IdentityStub("Owner"), sub=owner, role="teacher") as a,
            client_for(IdentityStub("Stranger"), sub=stranger, role="teacher") as b,
        ):
            created = await a.post(
                "/api/app/profile/cli-tokens", json={"label": "DB-Test", "scopes": ["read"]}
            )
            assert created.status_code == 201
            raw_token = created.json()["token"]
            token_id = created.json()["record"]["id"]
            assert (
                DBCLITokenStore(dsn=dsn).verify_token(raw_token, required_scope="read").user_sub
                == owner
            )
            assert (await b.get("/api/app/profile/cli-tokens")).json() == []
            assert (await b.delete(f"/api/app/profile/cli-tokens/{token_id}")).status_code == 404
            metadata = (await a.get("/api/app/profile/cli-tokens")).json()
            assert len(metadata) == 1
            assert "token_hash" not in metadata[0] and "token" not in metadata[0]
            assert (await a.delete(f"/api/app/profile/cli-tokens/{token_id}")).status_code == 204
            assert DBCLITokenStore(dsn=dsn).verify_token(raw_token, required_scope="read") is None
    finally:
        # Remove only rows owned by this run's newly generated subjects.
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "delete from public.cli_tokens where user_sub in (%s, %s)", (owner, stranger)
            )


async def test_waiting_identity_adapter_does_not_block_unrelated_requests() -> None:
    started, release = threading.Event(), threading.Event()

    class WaitingIdentity(IdentityStub):
        def get_user(self, *, user_id: str) -> dict[str, object]:
            started.set()
            assert release.wait(timeout=5), "profile adapter blocked the event loop"
            return super().get_user(user_id=user_id)

    async with client_for(WaitingIdentity("Waiting")) as client:
        pending = asyncio.create_task(client.get("/api/app/profile"))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            shell = await asyncio.wait_for(client.get("/api/app/session-bootstrap"), timeout=1)
            assert shell.status_code == 200
            assert not release.is_set()
        finally:
            release.set()
            response = await pending
        assert response.status_code == 200
        assert response.json()["display_name"] == "Waiting"
