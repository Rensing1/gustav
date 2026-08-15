"""Router composition for the package-oriented FastAPI entry point."""

from __future__ import annotations

from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from backend.web.app_composition import include_core_routers
from backend.web.auth_bridge import AuthBridgeDependencies, create_auth_bridge_router
from backend.web.components import Layout


class LayoutResponseBuilder(Protocol):
    """Callable shape for shared Layout rendering."""

    def __call__(
        self,
        request: Request,
        layout: Layout,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> HTMLResponse:
        ...


def include_main_routers(
    app: FastAPI,
    *,
    layout_response: LayoutResponseBuilder,
    auth_bridge_dependencies: AuthBridgeDependencies,
) -> None:
    """Include the remaining web routers in their existing runtime order."""

    from backend.web.routes.app import app_router
    from backend.web.routes.auth import auth_router
    from backend.web.routes.basic_pages import create_basic_pages_router
    from backend.web.routes.teaching import _get_repo as get_teaching_repo
    from backend.web.routes.teaching_courses import teaching_courses_router
    from backend.web.routes.teaching_course_modules import teaching_course_modules_router
    from backend.web.routes.teaching_course_members import teaching_course_members_router
    from backend.web.routes.teaching_course_invitations import teaching_course_invitations_router
    from backend.web.routes.teaching_unit_modules import teaching_unit_modules_router
    from backend.web.routes.teaching_unit_materials import teaching_unit_materials_router
    from backend.web.routes.teaching_unit_sections import teaching_unit_sections_router
    from backend.web.routes.teaching_unit_tasks import teaching_unit_tasks_router
    from backend.web.routes.teaching_units import teaching_units_router
    from backend.web.routes.learning import learning_router
    from backend.web.routes.practice import practice_router
    from backend.web.routes.operations import operations_router
    from backend.web.routes.teaching_live import teaching_live_router
    from backend.web.routes.teaching_h5p import teaching_h5p_router
    from backend.web.routes.users import users_router

    include_core_routers(
        app,
        (
            create_basic_pages_router(layout_response, repo_provider=get_teaching_repo),
            auth_router,
            app_router,
            learning_router,
            practice_router,
            teaching_live_router,
            teaching_courses_router,
            teaching_course_modules_router,
            teaching_unit_sections_router,
            teaching_course_members_router,
            teaching_course_invitations_router,
            teaching_unit_modules_router,
            teaching_unit_materials_router,
            teaching_unit_tasks_router,
            teaching_units_router,
            teaching_h5p_router,
            users_router,
            operations_router,
            create_auth_bridge_router(auth_bridge_dependencies),
        ),
    )
