"""
Learning API — Internal Upload Stub (TDD)

Why:
    In dev/offline mode we need a local upload target so the browser can PUT
    the selected file and the server can verify size/hash via
    STORAGE_VERIFY_ROOT. This test drives a minimal PUT endpoint that writes
    bytes and returns sha256 + size for later submission.
"""
from __future__ import annotations

import os
import uuid
from hashlib import sha256
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

import main  # type: ignore  # noqa: E402
import routes.learning as learning  # type: ignore  # noqa: E402
from backend.tests.utils.storage_fixtures import dummy_png_bytes  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


@pytest.fixture(autouse=True)
def restore_learning_repo():
    repo = learning.REPO
    yield
    learning.set_repo(repo)  # type: ignore[arg-type]


class StubSubmissionRepo:
    def __init__(self) -> None:
        self.created_payload = None

    def get_task_kind_for_student(self, *, student_sub: str, course_id: str, task_id: str) -> str:
        return "visual"

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
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://local")


@pytest.mark.anyio
async def test_internal_upload_stub_writes_file_and_returns_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Prepare session and path
    os.environ["STORAGE_VERIFY_ROOT"] = str(tmp_path)
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    main.SESSION_STORE = SessionStore()  # in-memory sessions
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    storage_key = f"submissions/test/{uuid.uuid4().hex}.png"
    url = f"/api/learning/internal/upload-stub?storage_key={storage_key}"
    data = b"hello world" * 10

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(url, content=data, headers={"Content-Type": "image/png", "Origin": "http://local"})

    assert r.status_code == 200
    body = r.json()
    assert int(body.get("size_bytes", 0)) == len(data)
    assert isinstance(body.get("sha256"), str) and len(body["sha256"]) == 64

    # Verify file exists on disk at STORAGE_VERIFY_ROOT/storage_key
    target = (tmp_path / storage_key)
    assert target.exists() and target.is_file()
    assert target.stat().st_size == len(data)


@pytest.mark.anyio
@pytest.mark.parametrize("require_storage_verify", ["false", "true"])
async def test_internal_upload_stub_default_root_is_read_by_submission_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    require_storage_verify: str,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", require_storage_verify)
    repo = StubSubmissionRepo()
    learning.set_repo(repo)  # type: ignore[arg-type]
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    storage_key = f"submissions/test/{uuid.uuid4().hex}.png"
    payload = dummy_png_bytes()

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        upload = await c.put(
            f"/api/learning/internal/upload-stub?storage_key={storage_key}",
            content=payload,
            headers={"Content-Type": "image/png", "Origin": "http://local"},
        )
        assert upload.status_code == 200

        response = await c.post(
            f"/api/learning/courses/{uuid.uuid4()}/tasks/{uuid.uuid4()}/submissions",
            json={
                "kind": "image",
                "storage_key": storage_key,
                "mime_type": "image/png",
                "size_bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            },
            headers={"Origin": "http://local", "Idempotency-Key": f"stub-{uuid.uuid4().hex[:12]}"},
        )

    assert response.status_code == 202
    assert response.json().get("analysis_status") == "pending"
    assert repo.created_payload is not None


@pytest.mark.anyio
async def test_default_stub_root_is_not_read_when_upload_stub_is_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")
    monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
    storage_key = "submissions/test/disabled.png"
    target = tmp_path / ".tmp" / "dev_uploads" / storage_key
    target.parent.mkdir(parents=True)
    target.write_bytes(dummy_png_bytes())

    loaded = await learning._load_storage_bytes_for_validation(  # type: ignore[attr-defined]
        storage_key=storage_key,
        max_bytes=1024 * 1024,
    )

    assert loaded is None


@pytest.mark.anyio
async def test_internal_upload_stub_returns_404_when_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENABLE_DEV_UPLOAD_STUB", raising=False)
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        res = await c.put(
            "/api/learning/internal/upload-stub?storage_key=submissions/test/file.png",
            content=b"x",
            headers={"Origin": "http://local", "Content-Type": "image/png"},
        )
    assert res.status_code == 404
