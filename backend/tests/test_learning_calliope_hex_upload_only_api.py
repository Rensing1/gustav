"""
Learning API — Calliope tasks are MakeCode HEX upload-only (MVP)

Intent:
    Specify the contract for `Task.kind="calliope"`:
    - Students may only submit HEX uploads (`kind=file`, `mime_type=application/x.makecode.hex`).
    - Image/PDF/text submissions are rejected with 400 (detail=invalid_input).
    - The server verifies storage/hash/size at submission time.
    - MakeCode source extraction is best-effort: known extraction errors are
      handled later through fallback evidence, not as upload rejection.
"""

from __future__ import annotations

from hashlib import sha256
import importlib
import json
import lzma
from pathlib import Path
import struct
import tempfile
import uuid

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

from backend.tests.runtime_auth_helpers import install_session_store
from backend.teaching.storage import StorageAdapterProtocol

main = importlib.import_module("backend.web.main")
learning = importlib.import_module("backend.web.routes.learning")


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


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


def _hex_record(*, addr: int, record_type: int, data: bytes) -> str:
    ll = len(data)
    total = ll + ((addr >> 8) & 0xFF) + (addr & 0xFF) + (record_type & 0xFF) + sum(data)
    checksum = (-total) & 0xFF
    return f":{ll:02X}{addr:04X}{record_type:02X}{data.hex().upper()}{checksum:02X}"


def _make_hex_with_embedded_source(*, eurl: str, record_type: int = 0x0E, place_after_eof: bool = True) -> bytes:
    files = {
        "main.ts": 'basic.showString("Hi")\n',
        "pxt.json": json.dumps({"name": "test-project", "dependencies": {}}, separators=(",", ":")),
    }
    extra_header_json = json.dumps({"name": "test-project"}, separators=(",", ":"))
    files_json = json.dumps(files, separators=(",", ":"))
    text = (extra_header_json + files_json).encode("utf-8")
    compressed = lzma.compress(text, format=lzma.FORMAT_ALONE)

    header = {
        "eURL": eurl,
        "compression": "LZMA",
        "headerSize": len(extra_header_json),
        "textSize": len(text.decode("utf-8")),
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    magic = b"\x41\x14\x0E\x2F\xB8\x2F\xA2\xBB"
    blob = magic + struct.pack("<H", len(header_bytes)) + struct.pack("<I", len(compressed)) + b"\x00\x00"
    blob += header_bytes + compressed

    lines: list[str] = []
    if place_after_eof:
        # Real MakeCode Calliope downloads may append the embedded source after
        # the EOF record because flashing tools stop at EOF.
        lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
        lines.append("")
    for i in range(0, len(blob), 16):
        lines.append(_hex_record(addr=i, record_type=record_type, data=blob[i : i + 16]))
    if not place_after_eof:
        lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
    return ("\n".join(lines) + "\n").encode("ascii")


def _make_hex_without_magic() -> bytes:
    blob = b"\x00" * 64
    lines: list[str] = []
    for i in range(0, len(blob), 16):
        lines.append(_hex_record(addr=i, record_type=0x00, data=blob[i : i + 16]))
    lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
    return ("\n".join(lines) + "\n").encode("ascii")


async def _prepare_task_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    task_payload: dict[str, object],
    course_title: str,
) -> dict:
    """Create course/unit/section with one released task and one enrolled student."""
    _require_db_or_skip()

    teaching = importlib.import_module("backend.web.routes.teaching")

    try:
        from backend.teaching.repo_db import DBTeachingRepo
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    session_store = install_session_store(monkeypatch, main)
    teacher = session_store.create(sub=f"t-calliope-{uuid.uuid4()}", name="T", roles=["teacher"])
    student = session_store.create(sub=f"s-calliope-{uuid.uuid4()}", name="S", roles=["student"])

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        course = (await c.post("/api/teaching/courses", json={"title": course_title, "subject": "Informatik", "grade_level": "7", "school_year_start": 2026})).json()
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


async def _prepare_calliope_task_fixture(monkeypatch: pytest.MonkeyPatch) -> dict:
    return await _prepare_task_fixture(
        monkeypatch,
        task_payload={"instruction_md": "### Calliope Aufgabe", "criteria": ["K1"], "calliope": {}},
        course_title="Kurs Calliope",
    )


async def _prepare_native_task_fixture(monkeypatch: pytest.MonkeyPatch) -> dict:
    return await _prepare_task_fixture(
        monkeypatch,
        task_payload={"instruction_md": "### Native Aufgabe", "criteria": ["K1"]},
        course_title="Kurs Native",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("mime_type", ["application/x.makecode.hex", "Application/X.MakeCode.Hex"])
async def test_calliope_upload_intent_allows_only_hex(monkeypatch: pytest.MonkeyPatch, mime_type: str) -> None:
    fx = await _prepare_calliope_task_fixture(monkeypatch)
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    with _UseStorageAdapter(FakeStorageAdapter()):
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/upload-intents",
                json={"kind": "file", "filename": "projekt.hex", "mime_type": mime_type, "size_bytes": 1024},
            )
    assert r.status_code == 200
    body = r.json() or {}
    assert body.get("accepted_mime_types") == ["application/x.makecode.hex"]


@pytest.mark.anyio
async def test_non_calliope_upload_intent_rejects_hex(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_native_task_fixture(monkeypatch)
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    with _UseStorageAdapter(FakeStorageAdapter()):
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/upload-intents",
                json={"kind": "file", "filename": "projekt.hex", "mime_type": "application/x.makecode.hex", "size_bytes": 1024},
            )
    assert r.status_code == 400
    assert r.json().get("detail") == "mime_not_allowed"


@pytest.mark.anyio
async def test_calliope_task_rejects_text_and_image_submissions(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_calliope_task_fixture(monkeypatch)
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
        r_text = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": "calliope-text-reject"},
            json={"kind": "text", "text_body": "Meine Loesung als Text"},
        )
        r_img = await c.post(
            f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
            headers={"Idempotency-Key": "calliope-image-reject"},
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
async def test_non_calliope_submission_rejects_hex_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_native_task_fixture(monkeypatch)
    hex_bytes = _make_hex_with_embedded_source(eurl="https://makecode.calliope.cc/#editor")
    digest = sha256(hex_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/projekt.hex"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(hex_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "native-hex-reject"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.makecode.hex",
                    "size_bytes": len(hex_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_file_payload"


@pytest.mark.anyio
@pytest.mark.parametrize("mime_type", ["application/x.makecode.hex", "Application/X.MakeCode.Hex"])
async def test_calliope_task_accepts_valid_hex_and_validates_source(monkeypatch: pytest.MonkeyPatch, mime_type: str) -> None:
    fx = await _prepare_calliope_task_fixture(monkeypatch)
    hex_bytes = _make_hex_with_embedded_source(eurl="https://makecode.calliope.cc/#editor")
    digest = sha256(hex_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/projekt.hex"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(hex_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "calliope-hex-ok"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": mime_type,
                    "size_bytes": len(hex_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 202
    body = r.json() or {}
    assert body.get("kind") == "file"
    assert body.get("analysis_status") == "pending"


@pytest.mark.anyio
async def test_calliope_submission_accepts_hex_even_if_eurl_host_is_unexpected(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_calliope_task_fixture(monkeypatch)
    hex_bytes = _make_hex_with_embedded_source(eurl="https://makecode.microbit.org/#editor")
    digest = sha256(hex_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/wrong_editor.hex"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(hex_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "calliope-hex-wrong-editor"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.makecode.hex",
                    "size_bytes": len(hex_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 202
    body = r.json() or {}
    assert body.get("kind") == "file"
    assert body.get("analysis_status") == "pending"


@pytest.mark.anyio
async def test_calliope_submission_accepts_missing_makecode_source(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = await _prepare_calliope_task_fixture(monkeypatch)
    hex_bytes = _make_hex_without_magic()
    digest = sha256(hex_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/missing_source.hex"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(hex_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "calliope-hex-missing-source"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.makecode.hex",
                    "size_bytes": len(hex_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 202
    assert r.json().get("analysis_status") == "pending"


@pytest.mark.anyio
async def test_calliope_submission_accepts_invalid_hex_file_soft_extraction_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = await _prepare_calliope_task_fixture(monkeypatch)
    hex_bytes = b":00000001FE\n"
    digest = sha256(hex_bytes).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        storage_key = "submissions/x/y/z/invalid_hex.hex"
        path = root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(hex_bytes)

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, fx["student"].session_id)
            r = await c.post(
                f"/api/learning/courses/{fx['course_id']}/tasks/{fx['task_id']}/submissions",
                headers={"Idempotency-Key": "calliope-hex-invalid-soft"},
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/x.makecode.hex",
                    "size_bytes": len(hex_bytes),
                    "sha256": digest,
                },
            )
    assert r.status_code == 202
    assert r.json().get("analysis_status") == "pending"
