"""Contracts for keeping diagnostics BFF routes outside app.py."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app.py"
DIAGNOSTICS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app_diagnostics_routes.py"


def test_diagnostics_bff_routes_live_outside_app_hotspot() -> None:
    app = importlib.import_module("backend.web.routes.app")
    diagnostics = importlib.import_module("backend.web.routes.app_diagnostics_routes")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    diagnostics_source = DIAGNOSTICS_SOURCE.read_text(encoding="utf-8")

    assert app.app_diagnostics_router is diagnostics.app_diagnostics_router
    assert app.get_diagnostics_course_matrix is diagnostics.get_diagnostics_course_matrix
    assert app.get_diagnostics_learner_profile is diagnostics.get_diagnostics_learner_profile
    assert '@app_router.get("/api/diagnostics/views/courses/{course_id}/matrix")' not in app_source
    assert '@app_router.get("/api/diagnostics/views/learners/{student_sub:path}/profile")' not in app_source
    assert '@app_diagnostics_router.get("/api/diagnostics/views/courses/{course_id}/matrix")' in diagnostics_source
    assert '@app_diagnostics_router.get("/api/diagnostics/views/learners/{student_sub:path}/profile")' in diagnostics_source


def test_diagnostics_read_model_helpers_live_with_diagnostics_routes() -> None:
    app = importlib.import_module("backend.web.routes.app")
    diagnostics = importlib.import_module("backend.web.routes.app_diagnostics_routes")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    diagnostics_source = DIAGNOSTICS_SOURCE.read_text(encoding="utf-8")

    helper_names = (
        "_build_diagnostics_course_matrix_rows",
        "_teacher_course_has_member",
        "_build_diagnostics_learner_profile_courses",
    )
    for helper_name in helper_names:
        assert getattr(app, helper_name) is getattr(diagnostics, helper_name)
        assert f"def {helper_name}(" not in app_source
        assert f"def {helper_name}(" in diagnostics_source
