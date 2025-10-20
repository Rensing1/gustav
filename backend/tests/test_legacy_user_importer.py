from __future__ import annotations

import uuid
from dataclasses import dataclass

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

    importer.import_legacy_users([sample_row], client=fake_client)

    # Existing user should be deleted and replaced with a new one
    assert existing_id in fake_client.deleted
    assert len(fake_client.created) == 1
    assert fake_client.assigned  # role assigned to the new user
