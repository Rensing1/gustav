"""
Teaching API — Course management (contract-first, TDD)

This test drives the minimal implementation for creating and listing courses.
It assumes authentication via the existing session middleware and requires the
"teacher" role for course creation.
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import sys


pytestmark = pytest.mark.anyio("asyncio")


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_teacher_can_create_and_list_own_courses():
    # Arrange: teacher session
    sess = main.SESSION_STORE.create(sub="teacher-1", name="Frau Lehrerin", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", sess.session_id)

        # Act: create course
        create = await client.post(
            "/api/teaching/courses",
            json={"title": "Biologie Q1", "subject": "Biologie", "grade_level": "Q1", "term": "2025-1"},
        )

        # Assert: created
        assert create.status_code == 201
        body = create.json()
        assert body.get("title") == "Biologie Q1"
        assert body.get("teacher_id") == "teacher-1"
        assert body.get("id")

        # Act: list courses
        lst = await client.get("/api/teaching/courses?limit=10&offset=0")
        assert lst.status_code == 200
        arr = lst.json()
        assert isinstance(arr, list)
        assert any(c.get("id") == body.get("id") for c in arr)


@pytest.mark.anyio
async def test_student_cannot_create_course_forbidden():
    # Arrange: student session
    sess = main.SESSION_STORE.create(sub="student-1", name="Max Musterschüler", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", sess.session_id)
        resp = await client.post("/api/teaching/courses", json={"title": "Test"})
        assert resp.status_code == 403
        data = resp.json()
        assert data.get("error") == "forbidden"

