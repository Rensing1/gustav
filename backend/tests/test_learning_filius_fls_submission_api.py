"""
Learning API -- Filius FLS submission finalization.

Intent:
    Filius submissions must be validated early against stored `.fls` bytes
    before persistence schedules the feedback pipeline.
"""

from __future__ import annotations

from hashlib import sha256
import io
import uuid
import zipfile

import httpx
import pytest
from httpx import ASGITransport

import main  # type: ignore
import routes.learning as learning  # type: ignore
from identity_access.stores import SessionStore  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


FILIUS_MIME = "application/x.filius.fls"
VALID_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>2.5</string>
</java>
"""


@pytest.fixture(autouse=True)
def restore_learning_route_state():
    repo = learning.REPO
    verify_storage_object = learning._verify_storage_object  # type: ignore[attr-defined]
    load_storage_bytes = learning._load_storage_bytes_for_validation  # type: ignore[attr-defined]
    yield
    learning.set_repo(repo)  # type: ignore[arg-type]
    learning._verify_storage_object = verify_storage_object  # type: ignore[attr-defined]
    learning._load_storage_bytes_for_validation = load_storage_bytes  # type: ignore[attr-defined]


class FakeLearningRepo:
    def __init__(self, *, task_kind: str) -> None:
        self.task_kind = task_kind
        self.created_payload = None

    def get_task_kind_for_student(self, *, student_sub: str, course_id: str, task_id: str) -> str:
        return self.task_kind

    def create_submission(self, data) -> dict:  # noqa: ANN001
        self.created_payload = data
        return {
            "id": str(uuid.uuid4()),
            "course_id": data.course_id,
            "task_id": data.task_id,
            "student_sub": data.student_sub,
            "kind": data.kind,
            "mime_type": data.mime_type,
            "analysis_status": "pending",
            "intent": data.intent,
        }


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


def _fls_with_config(config: bytes = VALID_XML, *, name: str = "projekt/konfiguration.xml") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, config)
    return buf.getvalue()


async def _post_submission(*, fls_bytes: bytes | None, task_kind: str = "filius") -> httpx.Response:
    repo = FakeLearningRepo(task_kind=task_kind)
    learning.set_repo(repo)  # type: ignore[arg-type]
    learning._verify_storage_object = lambda *args, **kwargs: (True, "ok")  # type: ignore[attr-defined]

    async def _load(*, storage_key: str, max_bytes: int):  # noqa: ANN001
        return fls_bytes

    learning._load_storage_bytes_for_validation = _load  # type: ignore[attr-defined]
    body = fls_bytes or b"x"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, _student_session())
        return await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            headers={"Idempotency-Key": f"filius-{uuid.uuid4().hex[:12]}"},
            json={
                "kind": "file",
                "storage_key": "submissions/course/task/student/file.fls",
                "mime_type": FILIUS_MIME,
                "size_bytes": len(body),
                "sha256": sha256(body).hexdigest(),
            },
        )


@pytest.mark.anyio
async def test_filius_submission_accepts_valid_fls() -> None:
    r = await _post_submission(fls_bytes=_fls_with_config())

    assert r.status_code == 202
    assert r.json().get("analysis_status") == "pending"


@pytest.mark.anyio
async def test_filius_submission_rejects_invalid_archive() -> None:
    r = await _post_submission(fls_bytes=b"not a zip")

    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_filius_archive"


@pytest.mark.anyio
async def test_filius_submission_reports_unavailable_storage_bytes() -> None:
    r = await _post_submission(fls_bytes=None)

    assert r.status_code == 503
    assert r.json().get("detail") == "filius_validation_unavailable"


@pytest.mark.anyio
async def test_non_filius_submission_rejects_fls_payload() -> None:
    r = await _post_submission(fls_bytes=_fls_with_config(), task_kind="native")

    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_file_payload"
