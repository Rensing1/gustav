"""
Learning API — SB3 validation must tolerate repos without task-kind helper.

Why:
    Some tests and in-memory stubs provide only the minimal submissions
    interface. The SB3 pre-validation path must not crash with 503 when
    `get_task_kind_for_student` is absent.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
import routes.learning as learning  # type: ignore
from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")


class _StubLearningRepo:
    def list_released_sections(self, **kwargs):  # noqa: ANN003 - protocol compatibility
        return []

    def list_submissions(self, **kwargs):  # noqa: ANN003 - protocol compatibility
        return []

    def create_submission(self, data):
        if data.kind == "file" and str(data.mime_type or "").strip().lower() == "application/x.scratch.sb3":
            raise ValueError("invalid_file_payload")
        return {"id": str(uuid.uuid4()), "kind": data.kind, "analysis_status": "pending"}


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


@pytest.mark.anyio
async def test_sb3_submission_does_not_require_task_kind_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])

    course_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    stub_repo = _StubLearningRepo()
    original_repo = learning._get_repo()
    learning.set_repo(stub_repo)
    monkeypatch.setattr(learning, "_verify_storage_object", lambda *args, **kwargs: (True, "match"))  # noqa: ARG005
    try:
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
            r = await c.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
                headers={"Idempotency-Key": "stub-sb3-fallback"},
                json={
                    "kind": "file",
                    "storage_key": "submissions/x/y/z/projekt.sb3",
                    "mime_type": "application/x.scratch.sb3",
                    "size_bytes": 512,
                    "sha256": "0" * 64,
                },
            )
    finally:
        learning.set_repo(original_repo)

    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_file_payload"
