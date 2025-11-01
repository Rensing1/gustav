"""
Learning API — Storage integrity verification for submissions.

Ensures the server validates size/sha256 against a local storage root when
configured. The verification is optional by default and can be enforced with
REQUIRE_STORAGE_VERIFY=true for strict environments/tests.
"""
from __future__ import annotations

import os
import tempfile
from hashlib import sha256
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

import uuid

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _prepare_fixture():
    # Reuse teaching APIs to seed data
    main.SESSION_STORE = SessionStore()  # in-memory
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    async with (await _client()) as c:
        # Teacher creates course/unit/section/task and releases section
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "Kurs"})
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["Kriterium"], "max_attempts": 3},
        )
        task_id = r_task.json()["id"]
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
        module_id = r_module.json()["id"]
        r_vis = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r_vis.status_code == 200
        # Add student to course
        r_member = await c.post(f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name})  # type: ignore
        assert r_member.status_code == 201
    return student.session_id, course_id, task_id


@pytest.mark.anyio
async def test_submission_verification_rejects_sha_mismatch(monkeypatch):
    student_sid, course_id, task_id = await _prepare_fixture()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Request an upload intent to get a storage_key
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
            r_intent = await c.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
                json={"kind": "file", "filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 12},
                headers={"Origin": "http://test"},
            )
        assert r_intent.status_code == 200
        intent = r_intent.json()
        storage_key = intent["storage_key"]

        # Create a file at STORAGE_VERIFY_ROOT/storage_key
        dest = (root / storage_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = b"hello world!"  # 12 bytes
        dest.write_bytes(data)
        size = len(data)
        # Mismatched sha256 (flip one byte)
        wrong_hash = sha256(b"hello world?").hexdigest()

        # Enforce verification via env
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
            r = await c.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
                json={
                    "kind": "file",
                    "storage_key": storage_key,
                    "mime_type": "application/pdf",
                    "size_bytes": size,
                    "sha256": wrong_hash,
                },
            )
        assert r.status_code == 400
        assert r.json().get("detail") == "invalid_file_payload"


@pytest.mark.anyio
async def test_submission_verification_accepts_correct_hash_and_size(monkeypatch):
    student_sid, course_id, task_id = await _prepare_fixture()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
            r_intent = await c.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
                json={"kind": "image", "filename": "img.png", "mime_type": "image/png", "size_bytes": 11},
                headers={"Origin": "http://test"},
            )
        assert r_intent.status_code == 200
        storage_key = r_intent.json()["storage_key"]
        dest = (Path(root) / storage_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = b"hello world"  # 11 bytes
        dest.write_bytes(data)
        size = len(data)
        good_hash = sha256(data).hexdigest()

        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(root))
        monkeypatch.setenv("REQUIRE_STORAGE_VERIFY", "true")

        async with (await _client()) as c:
            c.cookies.set(main.SESSION_COOKIE_NAME, student_sid)
            r = await c.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
                json={
                    "kind": "image",
                    "storage_key": storage_key,
                    "mime_type": "image/png",
                    "size_bytes": size,
                    "sha256": good_hash,
                },
            )
        assert r.status_code == 201
        assert r.headers.get("Cache-Control") == "private, no-store"
