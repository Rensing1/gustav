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

        active_courses = await client.get("/api/teaching/courses")
        archived_courses = await client.get(
            "/api/teaching/courses", params={"status": "archived"}
        )
        assert active_courses.status_code == 200
        assert archived_courses.status_code == 200
        assert course_id not in {course["id"] for course in active_courses.json()}
        assert course_id in {course["id"] for course in archived_courses.json()}

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
        assert queued.json()["course_title"] == "Kursarchiv"

        repeated = await client.post(
            f"/api/teaching/courses/{course_id}/deletion-jobs",
            json={"confirmation_title": "Kursarchiv", "confirm_student_data_loss": True},
        )
        assert repeated.status_code == 202
        assert repeated.json()["id"] == queued.json()["id"]

        jobs = await client.get("/api/teaching/course-deletion-jobs")
        assert jobs.status_code == 200
        assert [job["id"] for job in jobs.json()] == [queued.json()["id"]]

        current = await client.get(
            f"/api/teaching/course-deletion-jobs/{queued.json()['id']}"
        )
        assert current.status_code == 200
        assert current.json() == queued.json()

        repo.course_deletion_jobs[queued.json()["id"]].update(
            status="completed",
            completed_at="2026-08-08T12:00:00+00:00",
        )
        repo.courses.pop(course_id)
        completed_repeat = await client.post(
            f"/api/teaching/courses/{course_id}/deletion-jobs",
            json={"confirmation_title": "Kursarchiv", "confirm_student_data_loss": True},
        )
        assert completed_repeat.status_code == 202
        assert completed_repeat.json()["id"] == queued.json()["id"]
        assert completed_repeat.json()["status"] == "completed"

        malformed = await client.get(
            "/api/teaching/course-deletion-jobs/not-a-valid-job-id"
        )
        assert malformed.status_code == 404

        foreign_store = install_session_store(monkeypatch, main)
        foreign_session = foreign_store.create(
            sub="teacher-foreign", name="Andere Lehrkraft", roles=["teacher"]
        )
        client.cookies.set("gustav_session", foreign_session.session_id)
        foreign = await client.get(
            f"/api/teaching/course-deletion-jobs/{queued.json()['id']}"
        )
        assert foreign.status_code == 404
