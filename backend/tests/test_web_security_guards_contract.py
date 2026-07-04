"""Contracts for shared web security guards."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDS = REPO_ROOT / "backend" / "web" / "security" / "guards.py"


def test_shared_role_guards_cover_primary_and_roles_list() -> None:
    from backend.web.security.guards import has_any_role, has_role

    assert has_role({"role": "teacher"}, "teacher")
    assert has_role({"roles": ["student", "Teacher"]}, "teacher")
    assert not has_role({"roles": ["student"]}, "teacher")
    assert not has_role(None, "teacher")
    assert has_any_role({"roles": ["operator"]}, {"teacher", "operator"})


def test_web_routes_use_shared_role_guards_instead_of_local_duplicates() -> None:
    assert GUARDS.exists(), "Missing shared guard module"

    app_src = (REPO_ROOT / "backend" / "web" / "routes" / "app.py").read_text(encoding="utf-8")
    users_src = (REPO_ROOT / "backend" / "web" / "routes" / "users.py").read_text(encoding="utf-8")
    operations_src = (REPO_ROOT / "backend" / "web" / "routes" / "operations.py").read_text(encoding="utf-8")

    assert "from backend.web.security.guards import" in app_src
    assert "from backend.web.security.guards import" in users_src
    assert "from backend.web.security.guards import" in operations_src
    assert "def _user_has_role" not in app_src
    assert "def _is_teacher_or_admin" not in users_src
