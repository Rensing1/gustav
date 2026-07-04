"""
Routes repo swapping contract.

Why:
    Several tests switch between DB-backed and in-memory repos via `set_repo(...)`.
    The public module attribute (`routes.<x>.REPO`) must reflect that change,
    because other tests use it for `isinstance(...)` guards.

    A mismatch causes order-dependent skips in full-suite runs.
"""

from __future__ import annotations

import importlib


def test_teaching_set_repo_updates_public_repo_alias():
    teaching = importlib.import_module("backend.web.routes.teaching")

    original = teaching._get_repo()  # type: ignore[attr-defined]
    replacement = teaching._Repo()  # type: ignore[attr-defined]
    try:
        teaching.set_repo(replacement)  # type: ignore[attr-defined]
        assert teaching._get_repo() is replacement  # type: ignore[attr-defined]
        assert teaching.REPO is replacement  # type: ignore[attr-defined]
    finally:
        teaching.set_repo(original)  # type: ignore[attr-defined]


def test_learning_set_repo_updates_public_repo_alias():
    learning = importlib.import_module("backend.web.routes.learning")

    class _StubRepo:
        def list_released_sections(self, **kwargs):
            return []

        def create_submission(self, data):
            return {}

        def list_submissions(self, **kwargs):
            return []

    original = learning._get_repo()  # type: ignore[attr-defined]
    replacement = _StubRepo()
    try:
        learning.set_repo(replacement)  # type: ignore[attr-defined]
        assert learning._get_repo() is replacement  # type: ignore[attr-defined]
        assert learning.REPO is replacement  # type: ignore[attr-defined]
    finally:
        learning.set_repo(original)  # type: ignore[attr-defined]


def test_learning_set_repo_updates_existing_route_get_repo_after_reload():
    """Reloaded Learning modules must retarget old route globals to the current repo accessor."""

    import sys
    from fastapi.routing import APIRoute
    main = importlib.import_module("backend.web.main")
    original_learning = importlib.import_module("backend.web.routes.learning")

    def _find_sections_endpoint():
        for route in main.app.routes:
            if isinstance(route, APIRoute) and route.path == "/api/learning/courses/{course_id}/sections":
                return route.endpoint
        raise AssertionError("learning sections route not registered")

    endpoint = _find_sections_endpoint()
    original_repo = original_learning._get_repo()  # type: ignore[attr-defined]
    original_get_repo = endpoint.__globals__["_get_repo"]

    for name in ("routes.learning", "backend.web.routes.learning"):
        sys.modules.pop(name, None)

    fresh_learning = importlib.import_module("routes.learning")
    assert fresh_learning is not original_learning

    class _StubRepo:
        def list_released_sections(self, **kwargs):
            return []

    replacement = _StubRepo()
    try:
        fresh_learning.set_repo(replacement)  # type: ignore[attr-defined]
        assert endpoint.__globals__["_get_repo"] is fresh_learning._get_repo  # type: ignore[attr-defined]
        assert endpoint.__globals__["_get_repo"]() is replacement
    finally:
        fresh_learning.set_repo(original_repo)  # type: ignore[attr-defined]
        endpoint.__globals__["_get_repo"] = original_get_repo


def test_teaching_set_storage_adapter_updates_existing_route_globals_after_reload():
    """Reloaded Teaching modules must still retarget already-registered route globals."""

    import sys
    from fastapi.routing import APIRoute
    main = importlib.import_module("backend.web.main")
    original_teaching = importlib.import_module("backend.web.routes.teaching")

    def _find_upload_intent_endpoint():
        for route in main.app.routes:
            if (
                isinstance(route, APIRoute)
                and route.path
                == "/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents"
            ):
                return route.endpoint
        raise AssertionError("teaching upload-intent route not registered")

    original_adapter = original_teaching.STORAGE_ADAPTER
    endpoint = _find_upload_intent_endpoint()
    original_globals = endpoint.__globals__
    assert "STORAGE_ADAPTER" in original_globals

    for name in ("routes.teaching", "backend.web.routes.teaching"):
        sys.modules.pop(name, None)

    fresh_teaching = importlib.import_module("routes.teaching")
    assert fresh_teaching is not original_teaching

    class _Adapter:
        pass

    adapter = _Adapter()
    try:
        fresh_teaching.set_storage_adapter(adapter)
        assert fresh_teaching.STORAGE_ADAPTER is adapter
        assert endpoint.__globals__["STORAGE_ADAPTER"] is adapter
    finally:
        fresh_teaching.set_storage_adapter(original_adapter)
        assert endpoint.__globals__["STORAGE_ADAPTER"] is original_adapter


def test_teaching_route_guard_uses_endpoint_repo_accessor_after_reload():
    """Teaching guard adapters must honor the repo accessor installed on route globals."""

    import uuid
    from fastapi.routing import APIRoute

    main = importlib.import_module("backend.web.main")

    def _find_phases_endpoint():
        for route in main.app.routes:
            if isinstance(route, APIRoute) and route.path == "/api/teaching/units/{unit_id}/phases":
                return route.endpoint
        raise AssertionError("teaching phases route not registered")

    endpoint = _find_phases_endpoint()
    route_globals = endpoint.__globals__
    original_get_repo = route_globals["_get_repo"]

    class _StubRepo:
        def unit_exists_for_author(self, _unit_id: str, _author_sub: str) -> bool:
            return True

        def unit_exists(self, _unit_id: str) -> bool:
            return True

    try:
        route_globals["_get_repo"] = lambda: _StubRepo()
        guard = route_globals["_guard_unit_author"](str(uuid.uuid4()), "teacher-route-guard")
        assert guard is None
    finally:
        route_globals["_get_repo"] = original_get_repo
