"""Contracts for app profile helper ownership."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app.py"
HELPERS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app_profile_helpers.py"


def test_profile_normalization_helpers_live_outside_app_hotspot() -> None:
    app_routes = importlib.import_module("backend.web.routes.app")
    helpers = importlib.import_module("backend.web.routes.app_profile_helpers")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    helpers_source = HELPERS_SOURCE.read_text(encoding="utf-8")

    assert "def _claims_email(" not in app_source
    assert "def _parse_lock_timestamp(" not in app_source
    assert "def _profile_identity_defaults(" not in app_source
    assert "def _normalized_attributes(" not in app_source
    assert "def claims_email(" in helpers_source
    assert "def parse_lock_timestamp(" in helpers_source
    assert "def profile_identity_defaults(" in helpers_source
    assert "def normalized_attributes(" in helpers_source
    assert app_routes._claims_email is helpers.claims_email
    assert app_routes._parse_lock_timestamp is helpers.parse_lock_timestamp
    assert app_routes._profile_identity_defaults is helpers.profile_identity_defaults
    assert app_routes._normalized_attributes is helpers.normalized_attributes


def test_profile_normalization_helpers_keep_existing_rules() -> None:
    helpers = importlib.import_module("backend.web.routes.app_profile_helpers")

    assert helpers.claims_email({"preferred_username": "user@example.test"}) == "user@example.test"
    assert helpers.normalized_attributes(
        {
            "display_name": [" Lena ", "", None],
            "custom": "x",
            123: "ignored",
        }
    ) == {"display_name": [" Lena "], "custom": ["x"]}
    assert helpers.parse_lock_timestamp("2026-10-03T00:00:00Z").isoformat() == "2026-10-03T00:00:00+00:00"
    assert helpers.parse_lock_timestamp("not-a-date") is None

    defaults = helpers.profile_identity_defaults(
        {
            "email": "lena.schmidt@example.com",
            "gustav_display_name": "Lena S.",
        }
    )
    assert defaults["display_name"] == "Lena S."
    assert defaults["email"] == "lena.schmidt@example.com"
    assert defaults["name_can_edit"] is True
