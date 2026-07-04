"""API tests for the profile read/write flows."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import httpx
import pytest
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
app_routes = importlib.import_module("backend.web.routes.app")
from backend.identity_access.cli_tokens import InMemoryCLITokenStore


pytestmark = pytest.mark.anyio("asyncio")


def _install_cli_token_store(monkeypatch: pytest.MonkeyPatch, store: InMemoryCLITokenStore) -> None:
    monkeypatch.setattr(main.RUNTIME, "cli_token_store", store)


def _mock_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
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
    monkeypatch.setattr(main, "verify_bearer_token", lambda token, cfg: claims)
    monkeypatch.setattr(app_routes, "verify_bearer_token", lambda token, cfg: claims, raising=False)
    return {"Authorization": "Bearer test.jwt"}


@pytest.mark.anyio
async def test_profile_view_returns_identity_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_routes,
        "_load_profile_identity",
        lambda sub, claims, request=None: {
            "display_name": "Lena",
            "email": "lena.schmidt@example.com",
            "first_name": "Lena",
            "last_name": "Schmidt",
            "name_locked_until": None,
            "name_can_edit": True,
        },
    )
    headers = _mock_bearer_auth(monkeypatch, sub="student-profile", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/app/profile", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {
        "user": {
            "sub": "student-profile",
            "name": "Lena",
            "role": "student",
            "roles": ["student"],
        },
        "display_name": "Lena",
        "email": "lena.schmidt@example.com",
        "first_name": "Lena",
        "last_name": "Schmidt",
        "name_locked_until": None,
        "name_can_edit": True,
        "password_change_href": "/auth/password",
    }


@pytest.mark.anyio
async def test_profile_view_uses_runtime_oidc_config_for_claims_and_identity_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_cfg = SimpleNamespace(name="runtime-oidc")
    verify_cfgs: list[object] = []
    admin_cfgs: list[object] = []

    def _verify_bearer_token(token: str, cfg: object) -> dict[str, object]:
        verify_cfgs.append(cfg)
        return {
            "sub": "student-runtime-profile",
            "name": "Lena",
            "gustav_display_name": "Lena",
            "email": "lena.schmidt@example.com",
            "realm_access": {"roles": ["student"]},
            "exp": 4102444800,
        }

    class StubAdminClient:
        def __init__(self, cfg: object) -> None:
            admin_cfgs.append(cfg)

        def get_user(self, *, user_id: str) -> dict[str, object]:
            return {
                "id": user_id,
                "email": "lena.schmidt@example.com",
                "firstName": "Lena",
                "lastName": "Schmidt",
                "attributes": {"display_name": ["Lena"]},
            }

    monkeypatch.setattr(main.RUNTIME, "oidc_config", runtime_cfg)
    monkeypatch.setattr(main, "verify_bearer_token", _verify_bearer_token)
    monkeypatch.setattr(app_routes, "verify_bearer_token", _verify_bearer_token)
    monkeypatch.setattr(app_routes, "AdminClient", StubAdminClient)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/app/profile", headers={"Authorization": "Bearer test.jwt"})

    assert response.status_code == 200
    assert verify_cfgs[-1] is runtime_cfg
    assert admin_cfgs == [runtime_cfg]


@pytest.mark.anyio
async def test_profile_current_claims_use_route_verifier_not_main_module_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_claims = {
        "sub": "student-route-verifier",
        "name": "Lena",
        "gustav_display_name": "Lena",
        "email": "route-verifier@example.com",
        "realm_access": {"roles": ["student"]},
        "exp": 4102444800,
    }
    middleware_claims = {
        **route_claims,
        "email": "middleware-only@example.com",
    }
    main_calls = {"count": 0}
    captured_claims: dict[str, object] = {}

    def _main_verify_bearer_token(token: str, cfg: object) -> dict[str, object]:
        main_calls["count"] += 1
        if main_calls["count"] == 1:
            return middleware_claims
        raise AssertionError("profile route must not re-resolve claims through main.verify_bearer_token")

    def _route_verify_bearer_token(token: str, cfg: object) -> dict[str, object]:
        return route_claims

    def _load_profile_identity(sub: str, claims: dict[str, object], request=None) -> dict[str, object]:
        captured_claims.update(claims)
        return {
            "display_name": "Lena",
            "email": str(claims.get("email") or ""),
            "first_name": "Lena",
            "last_name": "",
            "name_locked_until": None,
            "name_can_edit": True,
        }

    monkeypatch.setattr(main, "verify_bearer_token", _main_verify_bearer_token)
    monkeypatch.setattr(app_routes, "verify_bearer_token", _route_verify_bearer_token, raising=False)
    monkeypatch.setattr(app_routes, "_load_profile_identity", _load_profile_identity)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/app/profile", headers={"Authorization": "Bearer test.jwt"})

    assert response.status_code == 200
    assert captured_claims["email"] == "route-verifier@example.com"
    assert main_calls["count"] == 1


@pytest.mark.anyio
async def test_profile_display_name_update_calls_identity_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        app_routes,
        "_update_profile_display_name",
        lambda sub, display_name, request=None: calls.append((sub, display_name)),
    )
    headers = _mock_bearer_auth(monkeypatch, sub="student-profile", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.patch(
            "/api/app/profile/display-name",
            headers={**headers, "Origin": "http://test"},
            json={"display_name": "Lena Neu"},
        )

    assert response.status_code == 204
    assert calls == [("student-profile", "Lena Neu")]


@pytest.mark.anyio
async def test_profile_name_update_rejects_locked_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_locked(sub: str, first_name: str, last_name: str, request=None) -> None:
        raise app_routes.ProfileNameLockedError("2026-10-03T00:00:00+00:00")

    monkeypatch.setattr(app_routes, "_update_profile_name", _raise_locked)
    headers = _mock_bearer_auth(monkeypatch, sub="student-profile", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.patch(
            "/api/app/profile/name",
            headers={**headers, "Origin": "http://test"},
            json={"first_name": "Lena", "last_name": "Schmidt"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": "name_locked",
        "detail": "2026-10-03T00:00:00+00:00",
    }


def test_update_profile_name_updates_only_names_and_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
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
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime=SimpleNamespace(oidc_config=oidc_config))))
    monkeypatch.setattr(app_routes, "AdminClient", StubAdminClient)

    app_routes._update_profile_name("student-profile", "Lena", "Schmidt", request)

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


def test_update_profile_display_name_updates_only_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
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
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime=SimpleNamespace(oidc_config=oidc_config))))
    monkeypatch.setattr(app_routes, "AdminClient", StubAdminClient)

    app_routes._update_profile_display_name("student-profile", "Lena Neu", request)

    assert recorded["get_user_id"] == "student-profile"
    assert recorded["update_user_id"] == "student-profile"
    payload = recorded["payload"]
    assert isinstance(payload, dict)
    assert payload == {
        "email": "lena.schmidt@example.com",
        "attributes": {
            "name_locked_until": ["2026-10-03T00:00:00+00:00"],
            "display_name": ["Lena Neu"],
        }
    }


@pytest.mark.anyio
async def test_profile_cli_token_lifecycle_returns_raw_token_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    now = {"value": 1_000}
    store = InMemoryCLITokenStore(now=lambda: now["value"])
    _install_cli_token_store(monkeypatch, store)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-cli-profile", roles=["teacher"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    monkeypatch.setattr(main.RUNTIME, "cli_token_store", store)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-cli-runtime", roles=["teacher"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
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
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    _install_cli_token_store(monkeypatch, store)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-cli-profile", roles=["teacher"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
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
