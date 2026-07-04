"""Contracts for retired legacy product entry handling."""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SOURCE = PROJECT_ROOT / "backend" / "web" / "main.py"


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("test", 80),
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


def test_retired_legacy_product_response_handles_role_scoped_paths() -> None:
    from backend.web.legacy_retirement import retired_legacy_product_response

    teacher_response = retired_legacy_product_response(
        _request("/courses"),
        {"role": "teacher", "roles": ["teacher"]},
    )
    student_response = retired_legacy_product_response(
        _request("/courses"),
        {"role": "student", "roles": ["student"]},
    )
    active_response = retired_legacy_product_response(
        _request("/about"),
        {"role": "teacher", "roles": ["teacher"]},
    )

    assert teacher_response is not None
    assert teacher_response.status_code == 410
    assert teacher_response.headers["Cache-Control"] == "private, no-store"
    assert student_response is not None
    assert student_response.status_code == 303
    assert student_response.headers["location"] == "/"
    assert active_response is None


def test_deep_teaching_live_legacy_path_detection_is_centralized() -> None:
    from backend.web.legacy_retirement import is_deep_teaching_live_legacy_path

    assert is_deep_teaching_live_legacy_path(
        "/teaching/courses/course-1/units/unit-1/live/matrix/delta"
    )
    assert is_deep_teaching_live_legacy_path(
        "/teaching/courses/course-1/modules/module-1/sections/section-1/visibility"
    )
    assert not is_deep_teaching_live_legacy_path("/teaching/live")
    assert not is_deep_teaching_live_legacy_path("/api/teaching/courses")


def test_main_delegates_legacy_retirement_to_dedicated_module() -> None:
    source = MAIN_SOURCE.read_text(encoding="utf-8")
    auth_middleware_source = (PROJECT_ROOT / "backend/web/auth_middleware.py").read_text(encoding="utf-8")

    assert "retired_legacy_product_response(" in auth_middleware_source
    assert "def _retired_legacy_product_response" not in source
    assert "def _render_retired_legacy_entry" not in source
    assert "def _is_deep_teaching_live_legacy_path" not in source
    assert "def _user_has_role" not in source
    assert "Legacy route retired" not in source
