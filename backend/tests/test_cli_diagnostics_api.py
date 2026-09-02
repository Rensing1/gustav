from __future__ import annotations

import importlib
from datetime import datetime, timezone

import httpx
import pytest
from httpx import ASGITransport

from backend.identity_access.cli_tokens import InMemoryCLITokenStore
from backend.tests.runtime_auth_helpers import install_cli_token_store, install_session_store
from backend.tests.utils.db import require_db_or_skip

main = importlib.import_module("backend.web.main")
teaching_live = importlib.import_module("backend.web.routes.teaching_live")
teaching_guards = importlib.import_module("backend.web.routes.teaching_guards")
repo_db = importlib.import_module("backend.teaching.repo_db")


pytestmark = pytest.mark.anyio("asyncio")


def _read_token(monkeypatch: pytest.MonkeyPatch) -> str:
    store = InMemoryCLITokenStore(now=lambda: 1_000)
    created = store.create_token(
        user_sub="teacher-cli-diagnostics",
        label="Diagnostik",
        scopes=["read"],
        ttl_seconds=3_600,
    )
    install_cli_token_store(monkeypatch, main, store)
    monkeypatch.setattr(
        main.AUTH_WIRING.auth_middleware_dependencies,
        "roles_for_cli_sub",
        lambda sub: ["teacher"],
    )
    return created.raw_token


@pytest.mark.anyio
async def test_cli_h5p_detail_never_issues_browser_review_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course_id = "11111111-1111-1111-1111-111111111111"
    unit_id = "22222222-2222-2222-2222-222222222222"
    task_id = "33333333-3333-3333-3333-333333333333"
    submission_id = "44444444-4444-4444-4444-444444444444"

    class StubRepo:
        def list_course_modules_for_owner(self, course_id: str, owner_sub: str):
            return [{"unit_id": unit_id}]

        def get_latest_submission_for_owner(self, **kwargs):
            return {
                "task_kind": "h5p",
                "instruction_md": "Bearbeite das Quiz.",
                "h5p_content_id": "123",
                "submission": (
                    submission_id,
                    task_id,
                    "student-1",
                    datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
                    datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
                    "h5p",
                    2,
                    3,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            }

    monkeypatch.setattr(repo_db, "DBTeachingRepo", StubRepo)
    monkeypatch.setattr(teaching_live, "_get_repo", lambda: StubRepo())
    monkeypatch.setattr(teaching_guards, "_guard_course_owner", lambda *args, **kwargs: None)

    def _must_not_issue(**kwargs):
        raise AssertionError("CLI requests must not receive H5P review credentials")

    monkeypatch.setattr(teaching_live, "issue_h5p_review_token", _must_not_issue)
    raw_token = _read_token(monkeypatch)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            (
                f"/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
                "students/student-1/submissions/latest"
            ),
            headers={"Authorization": f"Bearer {raw_token}"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["h5p"] == {"content_id": "123"}


@pytest.mark.db_write
@pytest.mark.anyio
async def test_cli_latest_submission_uses_real_owner_and_rls_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove that a read token still crosses the real owner-scoped DB boundary."""

    require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    assert isinstance(teaching.REPO, repo_db.DBTeachingRepo)
    assert learning.REPO.__class__.__name__ == "DBLearningRepo"

    sessions = install_session_store(monkeypatch, main)
    owner = sessions.create(
        sub="teacher-cli-diagnostics-db-owner",
        name="Owner",
        roles=["teacher"],
    )
    other = sessions.create(
        sub="teacher-cli-diagnostics-db-other",
        name="Other",
        roles=["teacher"],
    )
    learner = sessions.create(
        sub="student-cli-diagnostics-db",
        name="Ömer",
        roles=["student"],
    )

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        course_response = await client.post(
            "/api/teaching/courses",
            json={
                "title": "CLI Diagnostik DB",
                "subject": "Informatik",
                "grade_level": "10",
                "school_year_start": 2026,
            },
        )
        assert course_response.status_code == 201, course_response.text
        course_id = course_response.json()["id"]

        unit_response = await client.post(
            "/api/teaching/units",
            json={"title": "CLI Diagnostik DB Einheit"},
        )
        assert unit_response.status_code == 201, unit_response.text
        unit_id = unit_response.json()["id"]

        section_response = await client.post(
            f"/api/teaching/units/{unit_id}/sections",
            json={"title": "Diagnostik"},
        )
        assert section_response.status_code == 201, section_response.text
        section_id = section_response.json()["id"]

        task_response = await client.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={
                "instruction_md": "Erkläre den Unterschied zwischen Switch und Router.",
                "criteria": ["Funktion"],
                "max_attempts": 3,
            },
        )
        assert task_response.status_code == 201, task_response.text
        task_id = task_response.json()["id"]

        module_response = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit_id},
        )
        assert module_response.status_code == 201, module_response.text
        module_id = module_response.json()["id"]

        member_response = await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": learner.sub},
        )
        assert member_response.status_code in {201, 204}, member_response.text
        release_response = await client.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
        )
        assert release_response.status_code == 200, release_response.text

        client.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)
        for text_body in ("Erster Versuch", "Zweiter und neuester Versuch"):
            submission_response = await client.post(
                f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
                json={"kind": "text", "text_body": text_body},
            )
            assert submission_response.status_code == 202, submission_response.text

    token_store = InMemoryCLITokenStore(now=lambda: 1_000)
    owner_token = token_store.create_token(
        user_sub=owner.sub,
        label="Owner diagnostics",
        scopes=["read"],
        ttl_seconds=3_600,
    ).raw_token
    other_token = token_store.create_token(
        user_sub=other.sub,
        label="Foreign diagnostics",
        scopes=["read"],
        ttl_seconds=3_600,
    ).raw_token
    install_cli_token_store(monkeypatch, main, token_store)
    monkeypatch.setattr(
        main.AUTH_WIRING.auth_middleware_dependencies,
        "roles_for_cli_sub",
        lambda sub: ["teacher"],
    )
    detail_path = (
        f"/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/"
        f"students/{learner.sub}/submissions/latest"
    )

    async with httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
    ) as client:
        owner_response = await client.get(
            detail_path,
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        foreign_response = await client.get(
            detail_path,
            headers={"Authorization": f"Bearer {other_token}"},
        )

    assert owner_response.status_code == 200, owner_response.text
    assert owner_response.json()["text_body"] == "Zweiter und neuester Versuch"
    assert foreign_response.status_code == 403
