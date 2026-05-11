from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest
from starlette.requests import Request


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
sys.path.insert(0, str(WEB_DIR))

from routes import teaching as teaching_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


@pytest.mark.anyio
async def test_module_content_target_returns_backing_section_for_author(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubRepo:
        def unit_exists_for_author(self, unit_id: str, author_id: str) -> bool:
            return unit_id == "11111111-1111-1111-1111-111111111111" and author_id == "teacher-content-target"

        def unit_exists(self, unit_id: str) -> bool:
            return True

        def get_unit_module_for_author(self, *, unit_id: str, module_id: str, author_id: str):
            assert unit_id == "11111111-1111-1111-1111-111111111111"
            assert module_id == "22222222-2222-2222-2222-222222222222"
            assert author_id == "teacher-content-target"
            return {"id": module_id, "section_id": "33333333-3333-3333-3333-333333333333"}

    stub_repo = StubRepo()
    monkeypatch.setitem(
        teaching_routes.get_unit_module_content_target.__globals__,
        "_get_repo",
        lambda: stub_repo,
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/teaching/units/11111111-1111-1111-1111-111111111111/modules/"
            "22222222-2222-2222-2222-222222222222/content-target",
            "headers": [],
        }
    )
    request.state.user = {"sub": "teacher-content-target", "name": "Teacher", "roles": ["teacher"]}

    response = await teaching_routes.get_unit_module_content_target(
        request,
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    )

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body == {
        "module_id": "22222222-2222-2222-2222-222222222222",
        "section_id": "33333333-3333-3333-3333-333333333333",
    }
