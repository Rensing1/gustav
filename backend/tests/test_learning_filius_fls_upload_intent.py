"""
Learning API -- Filius FLS upload intents.

Intent:
    Filius tasks are upload-only and must receive presigned upload intents only
    for canonical `.fls` submissions.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
import routes.learning as learning  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from teaching.storage import StorageAdapterProtocol  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


FILIUS_MIME = "application/x.filius.fls"


@pytest.fixture(autouse=True)
def restore_learning_route_state():
    repo = learning.REPO
    storage_adapter = learning.STORAGE_ADAPTER
    storage_override = learning._STORAGE_ADAPTER_OVERRIDE_ACTIVE  # type: ignore[attr-defined]
    yield
    learning.set_repo(repo)  # type: ignore[arg-type]
    learning.set_storage_adapter(storage_adapter, override=storage_override)


class FakeLearningRepo:
    def __init__(self, *, task_kind: str) -> None:
        self.task_kind = task_kind

    def list_submissions(self, *, student_sub: str, course_id: str, task_id: str, limit: int, offset: int) -> list[dict]:
        return []

    def get_task_kind_for_student(self, *, student_sub: str, course_id: str, task_id: str) -> str:
        return self.task_kind


class FakeStorageAdapter(StorageAdapterProtocol):
    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]) -> dict:
        return {"url": f"https://storage.test/{bucket}/{key}?upload=1", "headers": headers, "method": "PUT"}

    def head_object(self, *, bucket: str, key: str) -> dict:
        return {"content_length": None, "etag": None}

    def delete_object(self, *, bucket: str, key: str) -> None:
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict:
        return {"url": f"https://storage.test/{bucket}/{key}?download=1", "headers": {}, "method": "GET"}


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


def _student_session() -> str:
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-filius-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    return str(student.session_id)


@pytest.mark.anyio
async def test_filius_upload_intent_allows_only_fls(monkeypatch: pytest.MonkeyPatch) -> None:
    learning.set_repo(FakeLearningRepo(task_kind="filius"))  # type: ignore[arg-type]
    learning.set_storage_adapter(FakeStorageAdapter())
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, _student_session())
        r = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/upload-intents",
            json={"kind": "file", "filename": "projekt.fls", "mime_type": FILIUS_MIME, "size_bytes": 1024},
        )

    assert r.status_code == 200
    body = r.json()
    assert body.get("accepted_mime_types") == [FILIUS_MIME]
    assert str(body.get("storage_key") or "").endswith(".fls")
    assert body.get("headers", {}).get("content-type") == FILIUS_MIME


@pytest.mark.anyio
async def test_non_filius_upload_intent_rejects_fls(monkeypatch: pytest.MonkeyPatch) -> None:
    learning.set_repo(FakeLearningRepo(task_kind="native"))  # type: ignore[arg-type]
    learning.set_storage_adapter(FakeStorageAdapter())
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, _student_session())
        r = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/upload-intents",
            json={"kind": "file", "filename": "projekt.fls", "mime_type": FILIUS_MIME, "size_bytes": 1024},
        )

    assert r.status_code == 400
    assert r.json().get("detail") == "mime_not_allowed"
