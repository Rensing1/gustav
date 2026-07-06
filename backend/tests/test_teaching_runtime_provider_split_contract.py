from __future__ import annotations

import inspect
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEACHING_ROUTE = REPO_ROOT / "backend" / "web" / "routes" / "teaching.py"


def test_teaching_runtime_sync_helpers_live_outside_route_module():
    """Teaching route runtime sync belongs in a small provider module, not in the route file."""

    from backend.web.routes import teaching_runtime_provider

    assert callable(teaching_runtime_provider.sync_route_repo)
    assert callable(teaching_runtime_provider.sync_route_storage_adapter)

    teaching_source = TEACHING_ROUTE.read_text(encoding="utf-8")
    assert "def _sync_teaching_route_globals(" not in teaching_source
    assert "def _sync_teaching_route_repo(" not in teaching_source


def test_teaching_setters_delegate_runtime_sync_to_provider_module():
    """Public test setters stay on teaching.py but delegate route-global retargeting."""

    from backend.web.routes import teaching

    set_repo_source = inspect.getsource(teaching.set_repo)
    set_storage_source = inspect.getsource(teaching.set_storage_adapter)

    assert "teaching_runtime_provider.sync_route_repo(repo)" in set_repo_source
    assert "teaching_runtime_provider.sync_route_storage_adapter(" in set_storage_source
