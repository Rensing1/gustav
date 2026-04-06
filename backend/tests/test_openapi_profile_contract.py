from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_documents_profile_endpoints() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text(encoding="utf-8"))

    assert "/api/app/profile" in spec["paths"]
    assert "/api/app/profile/display-name" in spec["paths"]
    assert "/api/app/profile/name" in spec["paths"]
    assert "/auth/password" in spec["paths"]

    profile_schema = spec["components"]["schemas"]["AppProfileView"]
    assert profile_schema["required"] == [
        "user",
        "display_name",
        "email",
        "first_name",
        "last_name",
        "name_locked_until",
        "name_can_edit",
        "password_change_href",
    ]

