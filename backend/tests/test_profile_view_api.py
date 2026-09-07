"""API tests for the profile read/write flows."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from httpx import ASGITransport

from backend.identity_access.cli_tokens import InMemoryCLITokenStore
from backend.identity_access.profile import ProfileService
from backend.web.main import create_app
from backend.web.profile_providers import ProfileProviders, create_profile_providers

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def app():
    """Use a fresh app with an explicit verifier, never a global auth override."""
    claims = {}
    created_app = create_app(access_token_verifier=lambda token, cfg: claims)
    created_app.state.verified_claims = claims
    return created_app


def _install_cli_token_store(
    monkeypatch: pytest.MonkeyPatch, app, store: InMemoryCLITokenStore
) -> None:
    monkeypatch.setattr(app.state.runtime, "cli_token_store", store)


def _mock_bearer_auth(
    app,
    *,
    sub: str,
    roles: list[str],
    name: str,
    email: str = "lena.schmidt@example.com",
) -> dict[str, str]:
    claims = {
        "sub": sub,
        "name": name,
        "gustav_display_name": name,
        "email": email,
        "realm_access": {"roles": roles},
        "exp": 4102444800,
    }
    app.state.verified_claims.update(claims)
    return {"Authorization": "Bearer test.jwt"}


def _install_identity(monkeypatch, app, user, *, update=lambda **kwargs: None, claims=None):
    identity = SimpleNamespace(get_user=lambda **kwargs: user, update_user=update)
    providers = ProfileProviders(
        identity=lambda: identity, verify_claims=lambda token: claims or {}
    )
    monkeypatch.setattr(app.state, "profile_providers", providers)


async def test_profile_view_returns_identity_fields(app, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_identity(
        monkeypatch,
        app,
        {
            "email": "lena.schmidt@example.com",
            "firstName": "Lena",
            "lastName": "Schmidt",
            "attributes": {"display_name": ["Lena"]},
        },
    )
    headers = _mock_bearer_auth(app, sub="student-profile", roles=["student"], name="Lena")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/app/profile", headers=headers)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.json() == {
        "user": {"sub": "student-profile", "name": "Lena", "role": "student", "roles": ["student"]},
        "display_name": "Lena",
        "email": "lena.schmidt@example.com",
        "first_name": "Lena",
        "last_name": "Schmidt",
        "name_locked_until": None,
        "name_can_edit": True,
        "password_change_href": "/auth/password",
    }


def test_default_profile_providers_use_own_runtime_oidc_config(monkeypatch):
    wiring = importlib.import_module("backend.web.profile_providers")
    cfg = object()
    runtime = SimpleNamespace(oidc_config=cfg)
    seen = []
    monkeypatch.setattr(wiring, "AdminClient", lambda config: seen.append(config))
    monkeypatch.setattr(wiring, "verify_bearer_token", lambda *, token, cfg: {"cfg": cfg})
    providers = create_profile_providers(runtime)
    providers.identity()
    assert seen == [cfg]
    assert providers.verify_claims("test.jwt") == {"cfg": cfg}


async def test_profile_claims_come_from_app_provider_not_main_alias(app, monkeypatch):
    _install_identity(monkeypatch, app, {}, claims={"email": "route-verifier@example.com"})
    headers = _mock_bearer_auth(
        app,
        sub="student-profile",
        roles=["student"],
        name="Lena",
        email="middleware-only@example.com",
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/app/profile", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "route-verifier@example.com"


async def test_profile_display_name_update_calls_identity_adapter(app, monkeypatch):
    calls = []
    _install_identity(
        monkeypatch,
        app,
        {"email": "student@example.com"},
        update=lambda **kwargs: calls.append(kwargs),
    )
    headers = _mock_bearer_auth(app, sub="student-profile", roles=["student"], name="Lena")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/api/app/profile/display-name",
            headers={**headers, "Origin": "http://test"},
            json={"display_name": "  Lena Neu  "},
        )
    assert response.status_code == 204
    assert calls == [
        {
            "user_id": "student-profile",
            "payload": {
                "email": "student@example.com",
                "attributes": {"display_name": ["Lena Neu"]},
            },
        }
    ]


async def test_profile_name_update_rejects_locked_names(app, monkeypatch):
    calls = []
    lock = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    _install_identity(
        monkeypatch,
        app,
        {"attributes": {"name_locked_until": [lock]}},
        update=lambda **kwargs: calls.append(kwargs),
    )
    headers = _mock_bearer_auth(app, sub="student-profile", roles=["student"], name="Lena")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/api/app/profile/name",
            headers={**headers, "Origin": "http://test"},
            json={"first_name": "Lena", "last_name": "Schmidt"},
        )
    assert response.status_code == 409
    assert response.json() == {"error": "name_locked", "detail": lock}
    assert calls == []


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/api/app/profile", None),
        ("PATCH", "/api/app/profile/name", {"first_name": "A"}),
        ("PATCH", "/api/app/profile/display-name", {"display_name": "A"}),
        ("GET", "/api/app/profile/cli-tokens", None),
        ("POST", "/api/app/profile/cli-tokens", {"label": "A", "scopes": ["read"]}),
        ("DELETE", "/api/app/profile/cli-tokens/absent", None),
    ],
)
async def test_anonymous_profile_requests_never_access_identity_or_store(
    app, monkeypatch, method, path, payload
):
    def forbidden():
        pytest.fail("unauthenticated request accessed a provider")

    monkeypatch.setattr(
        app.state,
        "profile_providers",
        ProfileProviders(identity=forbidden, verify_claims=lambda token: {}),
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.request(
            method, path, json=payload, headers={"Origin": "http://test"}
        )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path,payload",
    [
        ("name", {"first_name": "  ", "last_name": ""}),
        ("display-name", {"display_name": "  "}),
    ],
)
async def test_empty_profile_fields_are_rejected_before_identity_access(
    app, monkeypatch, path, payload
):
    def forbidden():
        pytest.fail("invalid input accessed identity")

    monkeypatch.setattr(
        app.state,
        "profile_providers",
        ProfileProviders(identity=forbidden, verify_claims=lambda token: {}),
    )
    headers = _mock_bearer_auth(app, sub="student-profile", roles=["student"], name="Lena")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/app/profile/{path}", json=payload, headers={**headers, "Origin": "http://test"}
        )
    assert response.status_code == 400


def test_update_profile_name_updates_only_names_and_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    class StubAdminClient:
        def __init__(self, cfg: object) -> None:
            recorded["cfg"] = cfg

        def get_user(self, *, user_id: str) -> dict[str, object]:
            recorded["get_user_id"] = user_id
            return {
                "id": user_id,
                "email": "lena.schmidt@example.com",
                "username": "legacy-email:lena.schmidt@example.com",
                "attributes": {
                    "display_name": ["Lena"],
                    "custom_flag": ["keep-me"],
                },
            }

        def update_user(self, *, user_id: str, payload: dict[str, object]) -> None:
            recorded["update_user_id"] = user_id
            recorded["payload"] = payload

    oidc_config = object()
    service = ProfileService(StubAdminClient(oidc_config))

    service.update_name("student-profile", "Lena", "Schmidt")

    assert recorded["get_user_id"] == "student-profile"
    assert recorded["update_user_id"] == "student-profile"
    payload = recorded["payload"]
    assert isinstance(payload, dict)
    assert payload["firstName"] == "Lena"
    assert payload["lastName"] == "Schmidt"
    assert payload["email"] == "lena.schmidt@example.com"
    assert "username" not in payload
    assert "enabled" not in payload
    assert "emailVerified" not in payload
    assert isinstance(payload["attributes"], dict)
    assert payload["attributes"]["display_name"] == ["Lena"]
    assert payload["attributes"]["custom_flag"] == ["keep-me"]
    lock_values = payload["attributes"]["name_locked_until"]
    assert isinstance(lock_values, list)
    assert len(lock_values) == 1
    assert isinstance(lock_values[0], str)


def test_update_profile_display_name_updates_only_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    class StubAdminClient:
        def __init__(self, cfg: object) -> None:
            recorded["cfg"] = cfg

        def get_user(self, *, user_id: str) -> dict[str, object]:
            recorded["get_user_id"] = user_id
            return {
                "id": user_id,
                "email": "lena.schmidt@example.com",
                "username": "legacy-email:lena.schmidt@example.com",
                "attributes": {
                    "name_locked_until": ["2026-10-03T00:00:00+00:00"],
                },
            }

        def update_user(self, *, user_id: str, payload: dict[str, object]) -> None:
            recorded["update_user_id"] = user_id
            recorded["payload"] = payload

    oidc_config = object()
    service = ProfileService(StubAdminClient(oidc_config))

    service.update_display_name("student-profile", "Lena Neu")

    assert recorded["get_user_id"] == "student-profile"
    assert recorded["update_user_id"] == "student-profile"
    payload = recorded["payload"]
    assert isinstance(payload, dict)
    assert payload == {
        "email": "lena.schmidt@example.com",
        "attributes": {
            "name_locked_until": ["2026-10-03T00:00:00+00:00"],
            "display_name": ["Lena Neu"],
        },
    }


@pytest.mark.anyio
async def test_profile_cli_token_lifecycle_returns_raw_token_only_once(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = {"value": 1_000}
    store = InMemoryCLITokenStore(now=lambda: now["value"])
    _install_cli_token_store(monkeypatch, app, store)
    headers = _mock_bearer_auth(app, sub="teacher-cli-profile", roles=["teacher"], name="Lena")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/app/profile/cli-tokens",
            headers={**headers, "Origin": "http://test"},
            json={"label": "Laptop", "scopes": ["read"], "ttl_days": 30},
        )
        listed = await client.get("/api/app/profile/cli-tokens", headers=headers)
        token_id = created.json()["record"]["id"]
        revoked = await client.delete(
            f"/api/app/profile/cli-tokens/{token_id}",
            headers={**headers, "Origin": "http://test"},
        )
        listed_after_revoke = await client.get("/api/app/profile/cli-tokens", headers=headers)

    assert created.status_code == 201
    created_body = created.json()
    assert created_body["token"].startswith("gustav_cli_")
    assert created_body["record"]["label"] == "Laptop"
    assert created_body["record"]["scopes"] == ["read"]

    assert listed.status_code == 200
    listed_body = listed.json()
    assert len(listed_body) == 1
    assert "token" not in listed_body[0]
    assert "token_hash" not in listed_body[0]

    assert revoked.status_code == 204
    assert listed_after_revoke.status_code == 200
    assert listed_after_revoke.json()[0]["revoked_at"] is not None


@pytest.mark.anyio
async def test_profile_cli_tokens_use_app_runtime_store(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    monkeypatch.setattr(app.state.runtime, "cli_token_store", store)
    headers = _mock_bearer_auth(app, sub="teacher-cli-runtime", roles=["teacher"], name="Lena")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/app/profile/cli-tokens",
            headers={**headers, "Origin": "http://test"},
            json={"label": "Laptop", "scopes": ["read"], "ttl_days": 30},
        )
        listed = await client.get("/api/app/profile/cli-tokens", headers=headers)

    assert created.status_code == 201
    assert listed.status_code == 200
    assert [record["label"] for record in listed.json()] == ["Laptop"]
    assert len(store.list_tokens("teacher-cli-runtime")) == 1


@pytest.mark.anyio
async def test_student_cannot_list_create_or_revoke_cli_tokens(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    teacher_token = store.create_token(
        user_sub="teacher-cli-owner",
        label="Laptop",
        scopes=["read"],
        ttl_seconds=30 * 24 * 60 * 60,
    )
    _install_cli_token_store(monkeypatch, app, store)
    headers = _mock_bearer_auth(app, sub="student-cli-profile", roles=["student"], name="Lena")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        listed = await client.get("/api/app/profile/cli-tokens", headers=headers)
        created = await client.post(
            "/api/app/profile/cli-tokens",
            headers={**headers, "Origin": "http://test"},
            json={"label": "Nicht erlaubt", "scopes": ["read"], "ttl_days": 30},
        )
        revoked = await client.delete(
            f"/api/app/profile/cli-tokens/{teacher_token.record.id}",
            headers={**headers, "Origin": "http://test"},
        )

    for response in (listed, created, revoked):
        assert response.status_code == 403
        assert response.json() == {"error": "forbidden"}
        assert response.headers.get("Cache-Control") == "private, no-store"
    assert store.list_tokens("student-cli-profile") == []
    assert store.list_tokens("teacher-cli-owner")[0].revoked_at is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"label": "", "scopes": ["read"], "ttl_days": 30},
        {"label": "Laptop", "scopes": [], "ttl_days": 30},
        {"label": "Laptop", "scopes": ["admin"], "ttl_days": 30},
        {"label": "Laptop", "scopes": ["read"], "ttl_days": 0},
        {"label": "Laptop", "scopes": ["read"], "ttl_days": 91},
    ],
)
async def test_profile_cli_token_create_invalid_payload_returns_contract_400(
    app,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    _install_cli_token_store(monkeypatch, app, store)
    headers = _mock_bearer_auth(app, sub="teacher-cli-profile", roles=["teacher"], name="Lena")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/app/profile/cli-tokens",
            headers={**headers, "Origin": "http://test"},
            json=payload,
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "bad_request"
    assert "detail" in body
    assert store.list_tokens("teacher-cli-profile") == []
