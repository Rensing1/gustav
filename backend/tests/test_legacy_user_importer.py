from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict

import pytest

from backend.tools import legacy_user_import as importer


@pytest.fixture
def sample_row() -> importer.LegacyUserRow:
    return importer.LegacyUserRow(
        id=uuid.UUID("814094e1-a5df-4195-8ad1-ac634bf6ebf1"),
        email="test1@test.de",
        role="student",
        full_name="Test Eins",
        password_hash="$2a$10$fOR932YFGqWlsJOKrkwZSe8FdMBgKM0zoNWsDEPsCIglqHI8J1ztS",
    )


def test_build_user_payload_uses_full_name(sample_row: importer.LegacyUserRow) -> None:
    payload = importer.build_user_payload(sample_row)
    assert payload["username"] == "test1@test.de"
    assert payload["email"] == "test1@test.de"
    assert payload["credentials"][0]["algorithm"] == "bcrypt"
    assert payload["attributes"]["display_name"] == ["Test Eins"]


def test_build_user_payload_falls_back_to_local_part(sample_row: importer.LegacyUserRow) -> None:
    row = sample_row.__class__(
        id=sample_row.id,
        email=sample_row.email,
        role=sample_row.role,
        full_name="",
        password_hash=sample_row.password_hash,
    )
    payload = importer.build_user_payload(row)
    assert payload["attributes"]["display_name"] == ["test1"]


def test_fetch_legacy_users_returns_none_for_missing_full_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rows with NULL full_name should yield LegacyUserRow.full_name=None."""
    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql: str, params: tuple | None):
            captured["sql"] = sql
            captured["params"] = params

        def fetchall(self):
            return [
                (
                    uuid.UUID("58f5c674-83c7-47b3-ae6a-2c4b2e9983c1"),
                    "no-name@example.com",
                    "student",
                    None,
                    "$2a$10$fOR932YFGqWlsJOKrkwZSe8FdMBgKM0zoNWsDEPsCIglqHI8J1ztS",
                )
            ]

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    def fake_connect(dsn: str):
        captured["dsn"] = dsn
        return FakeConn()

    monkeypatch.setattr(importer.psycopg, "connect", fake_connect)

    rows = importer.fetch_legacy_users("postgresql://fake")
    assert rows and rows[0].full_name is None


@dataclass
class FakeKeycloakClient:
    existing: dict[str, str]

    def __post_init__(self) -> None:
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self.assigned: list[tuple[str, str]] = []

    def find_user_id(self, email: str) -> str | None:
        return self.existing.get(email)

    def delete_user(self, user_id: str) -> None:
        self.deleted.append(user_id)
        self.existing = {k: v for k, v in self.existing.items() if v != user_id}

    def create_user(self, payload: dict) -> str:
        user_id = str(uuid.uuid4())
        self.created.append(payload)
        self.existing[payload["email"]] = user_id
        return user_id

    def assign_realm_role(self, user_id: str, role: str) -> None:
        self.assigned.append((user_id, role))


def test_import_users_creates_new_user_and_assigns_role(sample_row: importer.LegacyUserRow) -> None:
    fake_client = FakeKeycloakClient(existing={})
    importer.import_legacy_users([sample_row], client=fake_client)

    assert len(fake_client.created) == 1
    payload = fake_client.created[0]
    assert payload["credentials"][0]["hashedSaltedValue"] == sample_row.password_hash
    assert fake_client.assigned and fake_client.assigned[0][1] == "student"


def test_import_users_recreates_existing_user(sample_row: importer.LegacyUserRow) -> None:
    existing_id = "existing-id"
    fake_client = FakeKeycloakClient(existing={sample_row.email: existing_id})

    importer.import_legacy_users([sample_row], client=fake_client, delete_existing=True)

    # Existing user should be deleted and replaced with a new one
    assert existing_id in fake_client.deleted
    assert len(fake_client.created) == 1
    assert fake_client.assigned  # role assigned to the new user


def test_import_users_respects_no_delete(sample_row: importer.LegacyUserRow) -> None:
    """By default, importer must not delete existing users unless forced."""
    existing_id = "existing-id"
    fake_client = FakeKeycloakClient(existing={sample_row.email: existing_id})

    importer.import_legacy_users([sample_row], client=fake_client, delete_existing=False)

    # Should create a new user without deleting the old one
    assert existing_id not in fake_client.deleted
    assert len(fake_client.created) == 1
    assert fake_client.assigned


def test_import_skips_unsupported_role(sample_row: importer.LegacyUserRow) -> None:
    bad = sample_row.__class__(
        id=sample_row.id,
        email="x@example.com",
        role="guest",
        full_name="X",
        password_hash=sample_row.password_hash,
    )
    fake_client = FakeKeycloakClient(existing={})

    importer.import_legacy_users([bad], client=fake_client)

    assert not fake_client.created and not fake_client.assigned


def test_create_user_fallback_without_location_header(monkeypatch: pytest.MonkeyPatch, sample_row: importer.LegacyUserRow) -> None:
    """Admin client should locate the created user when Location header is missing."""

    class FakeResponse:
        def __init__(self, payload: Any = None, headers: Dict[str, str] | None = None):
            self._payload = payload
            self.headers = headers or {}

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers: Dict[str, str] = {}

        def post(self, url: str, *, data=None, json=None, timeout=None):
            if "token" in url:
                return FakeResponse({"access_token": "tok"})
            if "users" in url and json is not None:
                return FakeResponse(headers={})  # no Location header
            if "role-mappings" in url:
                return FakeResponse()
            raise AssertionError(f"Unexpected POST {url}")

        def get(self, url: str, *, params=None, timeout=None):
            if "users" in url and params:
                return FakeResponse([{"id": "created-user-id"}])
            if "roles" in url:
                return FakeResponse({"id": "role-id", "name": "student"})
            return FakeResponse([])

        def delete(self, url: str, *, timeout=None):
            return FakeResponse()

    fake_session = FakeSession()
    monkeypatch.setattr(importer.requests, "Session", lambda: fake_session)

    client = importer.KeycloakAdminClient.from_credentials(
        base_url="http://kc.local",
        host_header="id.localhost",
        realm="gustav",
        username="admin",
        password="secret",
    )
    user_id = client.create_user(importer.build_user_payload(sample_row))
    assert user_id == "created-user-id"


def test_fetch_legacy_users_filters_by_emails(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params):  # accept any sql obj
            captured["sql"] = str(sql)
            captured["params"] = params

        def fetchall(self):
            return []

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(importer.psycopg, "connect", lambda dsn: FakeConn())

    _ = importer.fetch_legacy_users("postgres://fake", emails=["a@example.com", "b@example.com"])
    assert "WHERE u.email = ANY" in captured["sql"], captured["sql"]
    assert captured["params"] and list(captured["params"][0]) == ["a@example.com", "b@example.com"]


def test_admin_client_requests_include_timeouts(monkeypatch: pytest.MonkeyPatch, sample_row: importer.LegacyUserRow) -> None:
    """All admin client HTTP calls must include a timeout for robustness."""

    class FakeResponse:
        def __init__(self, payload: Any = None, headers: Dict[str, str] | None = None):
            self._payload = payload
            self.headers = headers or {}

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers: Dict[str, str] = {}
            self.calls = []

        def post(self, url: str, *, data=None, json=None, timeout=None):
            self.calls.append(("post", url, timeout))
            if "token" in url:
                return FakeResponse({"access_token": "tok"})
            if "role-mappings" in url:
                return FakeResponse()
            if "users" in url and json is not None:
                return FakeResponse(headers={"Location": "http://kc/admin/users/new-user"})
            raise AssertionError(f"Unexpected POST {url}")

        def get(self, url: str, *, params=None, timeout=None):
            self.calls.append(("get", url, timeout))
            if "users" in url and params:
                return FakeResponse([{"id": "existing-user"}])
            if "roles" in url:
                return FakeResponse({"id": "role-id", "name": "student"})
            return FakeResponse([])

        def delete(self, url: str, *, timeout=None):
            self.calls.append(("delete", url, timeout))
            return FakeResponse()

    fake_session = FakeSession()
    monkeypatch.setattr(importer.requests, "Session", lambda: fake_session)

    client = importer.KeycloakAdminClient.from_credentials(
        base_url="http://kc.local",
        host_header="id.localhost",
        realm="gustav",
        username="admin",
        password="secret",
    )

    # Exercise all HTTP verbs
    client.find_user_id(sample_row.email)
    client.delete_user("existing-user")
    client.create_user(importer.build_user_payload(sample_row))
    client.assign_realm_role("new-user", "student")

    timeouts = [entry[2] for entry in fake_session.calls]
    assert timeouts, "expected admin client to perform HTTP requests"
    assert all(t == 5 for t in timeouts), f"expected timeout=5 on all calls, got {timeouts}"


def test_validate_host_rejects_header_injection() -> None:
    """Host header must not allow control characters (header injection)."""
    with pytest.raises(SystemExit):
        importer._validate_host("id.localhost\r\nInjected: 1")
