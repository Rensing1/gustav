"""
Routes repo swapping contract.

Why:
    Several tests switch between DB-backed and in-memory repos via `set_repo(...)`.
    The public module attribute (`routes.<x>.REPO`) must reflect that change,
    because other tests use it for `isinstance(...)` guards.

    A mismatch causes order-dependent skips in full-suite runs.
"""

from __future__ import annotations


def test_teaching_set_repo_updates_public_repo_alias():
    import routes.teaching as teaching  # type: ignore

    original = teaching._get_repo()  # type: ignore[attr-defined]
    replacement = teaching._Repo()  # type: ignore[attr-defined]
    try:
        teaching.set_repo(replacement)  # type: ignore[attr-defined]
        assert teaching._get_repo() is replacement  # type: ignore[attr-defined]
        assert teaching.REPO is replacement  # type: ignore[attr-defined]
    finally:
        teaching.set_repo(original)  # type: ignore[attr-defined]


def test_learning_set_repo_updates_public_repo_alias():
    import routes.learning as learning  # type: ignore

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


def test_teaching_set_storage_adapter_updates_existing_route_globals_after_reload():
    """Reloaded Teaching modules must still retarget already-registered route globals."""

    import importlib
    import sys
    from fastapi.routing import APIRoute
    import main  # type: ignore
    import routes.teaching as original_teaching  # type: ignore

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
