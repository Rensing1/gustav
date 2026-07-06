"""Contracts for keeping live BFF routes outside app.py."""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app.py"
LIVE_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "app_live_routes.py"


def test_live_bff_routes_live_outside_app_hotspot() -> None:
    app = importlib.import_module("backend.web.routes.app")
    live = importlib.import_module("backend.web.routes.app_live_routes")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    live_source = LIVE_SOURCE.read_text(encoding="utf-8")

    assert app.app_live_router is live.app_live_router
    route_names = (
        "get_live_unit_matrix",
        "get_live_course_units",
        "get_live_unit_dashboard",
        "get_live_detail_sheet",
    )
    for route_name in route_names:
        assert getattr(app, route_name) is getattr(live, route_name)
    assert '@app_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/matrix")' not in app_source
    assert '@app_router.get("/api/live/views/courses/{course_id}/units")' not in app_source
    assert '@app_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/dashboard")' not in app_source
    assert '@app_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/detail-sheet")' not in app_source
    assert '@app_live_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/matrix")' in live_source
    assert '@app_live_router.get("/api/live/views/courses/{course_id}/units")' in live_source
    assert '@app_live_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/dashboard")' in live_source
    assert '@app_live_router.get("/api/live/views/courses/{course_id}/units/{unit_id}/detail-sheet")' in live_source


def test_live_read_model_helpers_live_with_live_routes() -> None:
    app = importlib.import_module("backend.web.routes.app")
    live = importlib.import_module("backend.web.routes.app_live_routes")
    app_source = APP_SOURCE.read_text(encoding="utf-8")
    live_source = LIVE_SOURCE.read_text(encoding="utf-8")

    helper_names = (
        "_decode_json_response_body",
        "_live_selection_href",
        "_round_live_average",
        "_live_task_meta_by_id",
        "_live_dashboard_localpart_identifier",
    )
    for helper_name in helper_names:
        assert getattr(app, helper_name) is getattr(live, helper_name)
        assert f"def {helper_name}(" not in app_source
        assert f"def {helper_name}(" in live_source
