"""
Learning API — Scratch tasks are SB3 upload-only (MVP)

Intent:
    Specify the contract for `Task.kind="scratch"`:
    - Students may only submit SB3 uploads (`kind=file`, `mime_type=application/x.scratch.sb3`).
    - Image/PDF/text submissions are rejected with 400 (detail=invalid_input).
    - The server validates the archive at submission time:
        * invalid ZIP -> 400 invalid_sb3_archive
        * missing project.json -> 400 missing_project_json
"""

from __future__ import annotations

import os
import uuid
from hashlib import sha256
from pathlib import Path
import tempfile
import zipfile

import httpx
import pytest
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from backend.tests.runtime_auth_helpers import install_session_store  # noqa: E402
import routes.learning as learning  # type: ignore  # noqa: E402
from teaching.storage import StorageAdapterProtocol  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


class FakeStorageAdapter(StorageAdapterProtocol):
    """Deterministic presign URLs; download URLs unused in these tests."""

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]) -> dict:
        return {"url": f"https://storage.test/{bucket}/{key}?upload=1", "headers": headers, "method": "PUT"}

    def head_object(self, *, bucket: str, key: str) -> dict:
        return {"content_length": None, "etag": None}

    def delete_object(self, *, bucket: str, key: str) -> None:
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict:
        return {"url": f"https://storage.test/{bucket}/{key}?download=1", "headers": {}, "method": "GET"}


class _UseStorageAdapter:
    def __init__(self, adapter: StorageAdapterProtocol) -> None:
        self._adapter = adapter
        self._original: object | None = None

    def __enter__(self):  # noqa: ANN001
        self._original = getattr(learning, "STORAGE_ADAPTER", None)
        learning.set_storage_adapter(self._adapter)
        return self._adapter

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        if self._original is not None:
            learning.set_storage_adapter(self._original)  # type: ignore[arg-type]
        return False


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


def _make_valid_sb3_bytes() -> bytes:
    """Return a minimal valid SB3-like ZIP containing a project.json."""
    buf = tempfile.SpooledTemporaryFile(max_size=2_000_000)
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "project.json",
            '{"targets":[{"isStage":true,"name":"Stage","blocks":{},"variables":{},"lists":{},"broadcasts":{}}]}',
        )
    buf.seek(0)
    return buf.read()


def _make_zip_missing_project_json() -> bytes:
    buf = tempfile.SpooledTemporaryFile(max_size=2_000_000)
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("not_project.json", "{}")
    buf.seek(0)
    return buf.read()


async def _prepare_task_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    task_payload: dict[str, object],
    course_title: str,
) -> dict:
    """Create course/unit/section with one released task and one enrolled student."""
    _require_db_or_skip()

    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    session_store = install_session_store(monkeypatch, main)
    teacher = session_store.create(sub=f"t-scratch-{uuid.uuid4()}", name="T", roles=["teacher"])
    student = session_store.create(sub=f"s-scratch-{uuid.uuid4()}", name="S", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        course = (await c.post("/api/teaching/courses", json={"title": course_title})).json()
        unit = (await c.post("/api/teaching/units", json={"title": "Unit"})).json()
        section = (await c.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "Abschnitt"})).json()
        task = (await c.post(f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks", json=task_payload)).json()

        module = (await c.post(f"/api/teaching/courses/{course['id']}/modules", json={"unit_id": unit["id"]})).json()
        r = await c.patch(
            f"/api/teaching/courses/{course['id']}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r.status_code == 200

        r = await c.post(
            f"/api/teaching/courses/{course['id']}/members",
            json={"student_sub": student.sub},  # type: ignore[attr-defined]
        )
        assert r.status_code in (201, 204)

    return {"teacher": teacher, "student": student, "course_id": course["id"], "task_id": task["id"]}


async def _prepare_scratch_task_fixture(monkeypatch: pytest.MonkeyPatch) -> dict:
    return await _prepare_task_fixture(
        monkeypatch,
        task_payload={"instruction_md": "### Scratch Aufgabe", "criteria": ["K1"], "scratch": {}},
        course_title="Kurs Scratch",
    )


async def _prepare_native_task_fixture(monkeypatch: pytest.MonkeyPatch) -> dict:
    return await _prepare_task_fixture(
        monkeypatch,
        task_payload={"instruction_md": "### Native Aufgabe", "criteria": ["K1"]},
        course_title="Kurs Native",
    )


@pytest.mark.anyio
async def test_scratch_upload_intent_allows_only_sb3(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_scratch_task_fixture(monkeypatch)
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    with _UseStorageAdapter(FakeStorageAdapter()):
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/upload-intents",
                json={"kind": "file", "filename": "projekt.sb3", "mime_type": "application/x.scratch.sb3", "size_bytes": 1024},
            )
    assert r.status_code == 200
    body = r.json() or {}
    assert body.get("accepted_mime_types") == ["application/x.scratch.sb3"]


@pytest.mark.anyio
async def test_non_scratch_upload_intent_rejects_sb3(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_native_task_fixture(monkeypatch)
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    with _UseStorageAdapter(FakeStorageAdapter()):
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/upload-intents",
                json={"kind": "file", "filename": "projekt.sb3", "mime_type": "application/x.scratch.sb3", "size_bytes": 1024},
            )
    assert r.status_code == 400
    assert r.json().get("detail") == "mime_not_allowed"


@pytest.mark.anyio
async def test_scratch_task_rejects_text_and_image_submissions(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_scratch_task_fixture(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
        r_text = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": "scratch-text-reject"},
            json={"kind": "text", "text_body": "Meine Lösung als Text"},
        )
        r_img = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": "scratch-image-reject"},
            json={
                "kind": "image",
                "storage_key": "submissions/x/y/z/img.png",
                "mime_type": "image/png",
                "size_bytes": 123,
                "sha256": "0" * 64,
            },
        )
    assert r_text.status_code == 400
    assert r_text.json().get("detail") == "invalid_input"
    assert r_img.status_code == 400
    assert r_img.json().get("detail") == "invalid_input"


@pytest.mark.anyio
async def test_non_scratch_submission_rejects_sb3_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_native_task_fixture(monkeypatch)
    sb3_bytes = _make_valid_sb3_bytes()
    digest = sha256(sb3_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/projekt.sb3"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(sb3_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "native-sb3-reject"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.scratch.sb3",
                    "size_bytes": len(sb3_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_file_payload"


@pytest.mark.anyio
async def test_scratch_task_accepts_valid_sb3_and_validates_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_scratch_task_fixture(monkeypatch)
    sb3_bytes = _make_valid_sb3_bytes()
    digest = sha256(sb3_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/projekt.sb3"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(sb3_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "scratch-sb3-ok"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.scratch.sb3",
                    "size_bytes": len(sb3_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 202
    body = r.json() or {}
    assert body.get("kind") == "file"
    assert body.get("analysis_status") == "pending"


@pytest.mark.anyio
async def test_scratch_submission_rejects_invalid_zip(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_scratch_task_fixture(monkeypatch)
    sb3_bytes = b"not a zip"
    digest = sha256(sb3_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/invalid.sb3"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(sb3_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "scratch-sb3-badzip"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.scratch.sb3",
                    "size_bytes": len(sb3_bytes),
                    "sha256": digest,
                },
    )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_upload_content"


@pytest.mark.anyio
async def test_scratch_submission_rejects_missing_project_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_scratch_task_fixture(monkeypatch)
    sb3_bytes = _make_zip_missing_project_json()
    digest = sha256(sb3_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/missing_project.sb3"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(sb3_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "scratch-sb3-missing-project"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.scratch.sb3",
                    "size_bytes": len(sb3_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 400
    assert r.json().get("detail") == "missing_project_json"
