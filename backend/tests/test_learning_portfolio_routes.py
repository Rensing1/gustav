"""HTTP contract tests for the private learner portfolio and export jobs."""

from __future__ import annotations

import importlib
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store


main = importlib.import_module("backend.web.main")
learning = importlib.import_module("backend.web.routes.learning")

pytestmark = pytest.mark.anyio("asyncio")


class _PortfolioRepo:
    def __init__(self, course_id: str) -> None:
        self.course_id = course_id
        self.created_for: tuple[str, str] | None = None

    def list_personal_courses(self, *, student_sub: str, scope: str, limit: int, offset: int):
        if student_sub != "student-own":
            return []
        return [{"id": self.course_id, "title": "Archivkurs", "status": "archived", "membership_status": "former"}]

    def personal_course_portfolio(self, *, course_id: str, student_sub: str):
        assert course_id == self.course_id
        assert student_sub == "student-own"
        return [{
            "id": str(uuid4()),
            "kind": "text",
            "intent": "submit",
            "created_at": "2026-07-01T10:00:00+00:00",
            "completed_at": "2026-07-01T10:01:00+00:00",
            "text_body": "Meine Lösung",
            "feedback_md": "Gut begründet.",
            "analysis_json": {"version": "criteria.v2"},
            "storage_key": None,
            "mime_type": None,
            "dialog_session_id": None,
            "task_snapshot": {"title": "Aufgabe 1", "instruction_md": "Begründe."},
        }]

    def create_learning_export_job(self, *, course_id: str, student_sub: str):
        self.created_for = (course_id, student_sub)
        return {
            "id": str(uuid4()), "course_id": course_id, "status": "pending",
            "requested_at": "2026-08-06T10:00:00+00:00",
            "expires_at": "2026-08-07T10:00:00+00:00", "storage_key": None, "error_code": None,
        }

    def get_latest_learning_export_job(self, *, course_id: str, student_sub: str):
        return None

    def get_learning_export_job(self, *, export_id: str, student_sub: str):
        if student_sub != "student-own":
            return None
        return {
            "id": export_id,
            "course_id": self.course_id,
            "status": "ready",
            "requested_at": "2026-08-06T10:00:00+00:00",
            "expires_at": "2026-08-07T10:00:00+00:00",
            "storage_key": f"exports/{export_id}.zip",
            "error_code": None,
        }


async def test_student_reads_only_own_portfolio_and_queues_export(monkeypatch: pytest.MonkeyPatch) -> None:
    course_id = str(uuid4())
    repo = _PortfolioRepo(course_id)
    learning.set_repo(repo)
    store = install_session_store(monkeypatch, main)
    session = store.create(sub="student-own", name="Lernende Person", roles=["student"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"}) as client:
        client.cookies.set("gustav_session", session.session_id)
        portfolio = await client.get(f"/api/learning/courses/{course_id}/portfolio")
        assert portfolio.status_code == 200
        assert portfolio.json()["course"]["title"] == "Archivkurs"
        assert portfolio.json()["submissions"][0]["text_body"] == "Meine Lösung"

        created = await client.post(f"/api/learning/courses/{course_id}/exports")
        assert created.status_code == 202
        assert created.json()["status"] == "pending"
        assert repo.created_for == (course_id, "student-own")


async def test_student_cannot_read_course_outside_personal_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    course_id = str(uuid4())
    repo = _PortfolioRepo(course_id)
    learning.set_repo(repo)
    store = install_session_store(monkeypatch, main)
    session = store.create(sub="student-other", name="Andere Person", roles=["student"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        response = await client.get(f"/api/learning/courses/{course_id}/portfolio")
        assert response.status_code == 404


async def test_ready_export_download_uses_the_dedicated_private_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    course_id = str(uuid4())
    export_id = str(uuid4())
    current_learning = importlib.import_module("backend.web.routes.learning")
    current_learning.set_repo(_PortfolioRepo(course_id))
    store = install_session_store(monkeypatch, main)
    session = store.create(sub="student-own", name="Lernende Person", roles=["student"])
    requested: dict[str, str] = {}

    async def _download(*, bucket: str, key: str, disposition: str, max_bytes: int):
        requested.update(bucket=bucket, key=key, disposition=disposition)
        return b"zip"

    monkeypatch.setattr(current_learning, "_download_storage_object_via_presign", _download)
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        response = await client.get(f"/api/learning/exports/{export_id}/download")

    assert response.status_code == 200
    assert requested == {
        "bucket": "learning-exports",
        "key": f"exports/{export_id}.zip",
        "disposition": "attachment",
    }
