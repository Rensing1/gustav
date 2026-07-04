"""Learning API -- upload content-signature gate.

The route must reject stored bytes that contradict the declared upload MIME
before creating a submission or queueing feedback work.
"""

from __future__ import annotations

from hashlib import sha256
import importlib
from io import BytesIO
import uuid

import httpx
from httpx import ASGITransport
from PIL import Image
import pytest

from backend.tests.runtime_auth_helpers import install_session_store

main = importlib.import_module("backend.web.main")
learning = importlib.import_module("backend.web.routes.learning")


pytestmark = pytest.mark.anyio("asyncio")


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
    def __init__(self, *, task_kind: str = "visual") -> None:
        self.task_kind = task_kind
        self.task_kind_reads = 0
        self.created_payload = None

    def get_task_kind_for_student(self, *, student_sub: str, course_id: str, task_id: str) -> str:
        self.task_kind_reads += 1
        return self.task_kind

    def create_submission(self, data):  # noqa: ANN001
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


def _student_session(monkeypatch: pytest.MonkeyPatch) -> str:
    store = install_session_store(monkeypatch, main)
    student = store.create(sub=f"s-content-{uuid.uuid4()}", name="S", roles=["student"])
    return str(student.session_id)


def _image_bytes(*, image_format: str) -> bytes:
    out = BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 255)).save(out, format=image_format)
    return out.getvalue()


async def _post_upload_submission(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mime_type: str,
    stored_bytes: bytes | None,
    kind: str = "file",
    task_kind: str = "visual",
) -> tuple[httpx.Response, FakeLearningRepo]:
    repo = FakeLearningRepo(task_kind=task_kind)
    learning.set_repo(repo)  # type: ignore[arg-type]
    learning._verify_storage_object = lambda *args, **kwargs: (True, "ok")  # type: ignore[attr-defined]

    async def _load(*, storage_key: str, max_bytes: int):  # noqa: ANN001
        return stored_bytes

    learning._load_storage_bytes_for_validation = _load  # type: ignore[attr-defined]

    body = stored_bytes or b"x"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, _student_session(monkeypatch))
        response = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            headers={"Idempotency-Key": f"content-{uuid.uuid4().hex[:12]}"},
            json={
                "kind": kind,
                "storage_key": "submissions/course/task/student/upload.bin",
                "mime_type": mime_type,
                "size_bytes": len(body),
                "sha256": sha256(body).hexdigest(),
            },
        )
    return response, repo


@pytest.mark.parametrize(
    ("kind", "mime_type", "task_kind"),
    [
        ("image", "image/png", "visual"),
        ("file", "application/pdf", "visual"),
        ("file", "application/x.makecode.hex", "calliope"),
    ],
)
async def test_wrong_content_is_rejected_before_submission_creation(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    mime_type: str,
    task_kind: str,
) -> None:
    response, repo = await _post_upload_submission(
        monkeypatch,
        kind=kind,
        mime_type=mime_type,
        stored_bytes=b"PK\x03\x04not-the-declared-type",
        task_kind=task_kind,
    )

    assert response.status_code == 400
    assert response.json().get("detail") == "invalid_upload_content"
    assert repo.created_payload is None


@pytest.mark.parametrize(
    ("kind", "mime_type", "payload"),
    [
        ("image", "image/png", _image_bytes(image_format="PNG")),
        ("image", "image/jpeg", _image_bytes(image_format="JPEG")),
        ("file", "application/pdf", b"%PDF-1.7\n%test\n"),
    ],
)
async def test_valid_image_and_pdf_content_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    mime_type: str,
    payload: bytes,
) -> None:
    response, repo = await _post_upload_submission(
        monkeypatch,
        kind=kind,
        mime_type=mime_type,
        stored_bytes=payload,
        task_kind="visual",
    )

    assert response.status_code == 202
    assert response.json().get("analysis_status") == "pending"
    assert repo.created_payload is not None


async def test_missing_validation_bytes_fails_closed_before_submission_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    response, repo = await _post_upload_submission(
        monkeypatch,
        kind="image",
        mime_type="image/png",
        stored_bytes=None,
        task_kind="visual",
    )

    assert response.status_code == 503
    assert response.json().get("detail") == "submission_validation_unavailable"
    assert repo.created_payload is None


async def test_specialized_file_validation_reuses_loaded_task_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.storage.filius_validation as filius_validation

    monkeypatch.setattr(filius_validation, "extract_configuration_xml_bytes", lambda _data: b"<config/>")

    response, repo = await _post_upload_submission(
        monkeypatch,
        kind="file",
        mime_type="application/x.filius.fls",
        stored_bytes=b"PK\x03\x04filius",
        task_kind="filius",
    )

    assert response.status_code == 202
    assert repo.created_payload is not None
    assert repo.task_kind_reads == 1
