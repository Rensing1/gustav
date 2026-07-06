"""Contracts for keeping teacher unit BFF routes outside app.py."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app.py"
UNIT_ROUTES_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app_teacher_unit_routes.py"


def test_teacher_unit_bff_routes_live_outside_app_hotspot() -> None:
    app = importlib.import_module("backend.web.routes.app")
    unit_routes = importlib.import_module("backend.web.routes.app_teacher_unit_routes")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    unit_source = UNIT_ROUTES_SOURCE.read_text(encoding="utf-8")

    assert app.app_teacher_unit_router is unit_routes.app_teacher_unit_router
    assert app.get_teacher_units_catalog is unit_routes.get_teacher_units_catalog
    assert app.get_teacher_unit_workspace is unit_routes.get_teacher_unit_workspace
    assert '@app_router.get("/api/teaching/views/units/catalog")' not in app_source
    assert '@app_router.get("/api/teaching/views/units/{unit_id}/workspace")' not in app_source
    assert '@app_teacher_unit_router.get("/api/teaching/views/units/catalog")' in unit_source
    assert '@app_teacher_unit_router.get("/api/teaching/views/units/{unit_id}/workspace")' in unit_source


def test_teacher_unit_read_model_helpers_live_with_teacher_unit_routes() -> None:
    app = importlib.import_module("backend.web.routes.app")
    unit_routes = importlib.import_module("backend.web.routes.app_teacher_unit_routes")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    unit_source = UNIT_ROUTES_SOURCE.read_text(encoding="utf-8")

    helper_names = (
        "_list_teacher_course_units",
        "_list_teacher_units",
        "_list_teacher_unit_sections",
        "_list_teacher_unit_phases",
        "_list_teacher_unit_modules",
        "_list_teacher_unit_edges",
        "_build_teacher_unit_course_refs",
        "_list_submission_pairs_for_students",
        "_list_unit_task_ids",
        "_find_course_unit",
    )
    for helper_name in helper_names:
        assert getattr(app, helper_name) is getattr(unit_routes, helper_name)
        assert f"def {helper_name}(" not in app_source
        assert f"def {helper_name}(" in unit_source
