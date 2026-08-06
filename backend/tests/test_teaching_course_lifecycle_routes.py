"""Route tests for archive, restore and strongly confirmed deletion."""

from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store


main = importlib.import_module("backend.web.main")
teaching = importlib.import_module("backend.web.routes.teaching")
pytestmark = pytest.mark.anyio("asyncio")


async def test_archive_requires_metadata_and_delete_requires_double_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = teaching._Repo()  # type: ignore[attr-defined]
    teaching.set_repo(repo)
    store = install_session_store(monkeypatch, main)
    session = store.create(sub="teacher-lifecycle", name="Lehrkraft", roles=["teacher"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as client:
        client.cookies.set("gustav_session", session.session_id)
        # Existing installations may still contain legacy courses without the
        # metadata that is mandatory for newly created courses.
        created = repo.create_course(
            title="Kursarchiv",
            subject=None,
            grade_level=None,
            term=None,
            school_year_start=None,
            teacher_id="teacher-lifecycle",
        )
        course_id = created.id

        incomplete = await client.post(f"/api/teaching/courses/{course_id}/archive")
        assert incomplete.status_code == 400
        assert incomplete.json()["detail"] == "course_metadata_incomplete"

        updated = await client.patch(
            f"/api/teaching/courses/{course_id}",
            json={"subject": "Informatik", "grade_level": "10", "school_year_start": 2026},
        )
        assert updated.status_code == 200
        archived = await client.post(f"/api/teaching/courses/{course_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        restored = await client.post(f"/api/teaching/courses/{course_id}/restore")
        assert restored.status_code == 200
        assert restored.json()["status"] == "active"

        mismatch = await client.post(
            f"/api/teaching/courses/{course_id}/deletion-jobs",
            json={"confirmation_title": "Falsch", "confirm_student_data_loss": True},
        )
        assert mismatch.status_code == 400
        assert mismatch.json()["detail"] == "deletion_confirmation_mismatch"
        queued = await client.post(
            f"/api/teaching/courses/{course_id}/deletion-jobs",
            json={"confirmation_title": "Kursarchiv", "confirm_student_data_loss": True},
        )
        assert queued.status_code == 202
        assert queued.json()["status"] == "pending"
