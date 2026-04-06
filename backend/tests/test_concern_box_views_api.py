"""API tests for learner and teacher concern box read/write flows."""

from __future__ import annotations

from pathlib import Path
import sys

import httpx
import pytest
from httpx import ASGITransport


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from routes import teaching as teaching_routes  # type: ignore


pytestmark = pytest.mark.anyio("asyncio")


def _mock_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sub: str,
    roles: list[str],
    name: str,
) -> dict[str, str]:
    monkeypatch.setattr(
        main,
        "verify_bearer_token",
        lambda token, cfg: {
            "sub": sub,
            "name": name,
            "gustav_display_name": name,
            "realm_access": {"roles": roles},
            "exp": 4102444800,
        },
    )
    return {"Authorization": "Bearer test.jwt"}


async def _seed_course_for_teacher(client: httpx.AsyncClient, title: str = "Mathe 9b") -> str:
    response = await client.post(
        "/api/teaching/courses",
        json={"title": title},
        headers={"Origin": "http://test"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


@pytest.mark.anyio
async def test_learner_concern_box_view_returns_current_courses(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    teacher = store.create(sub="teacher-concern", roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub="student-concern", roles=["student"], name="Lena", ttl_seconds=60)
    teacher_headers = _mock_bearer_auth(monkeypatch, sub="teacher-concern", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern view")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )
        learner_headers = _mock_bearer_auth(monkeypatch, sub="student-concern", roles=["student"], name="Lena")

        response = await client.get("/api/learning/views/concern-box", headers=learner_headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    body = response.json()
    assert body["user"] == {
        "sub": "student-concern",
        "name": "Lena",
        "role": "student",
        "roles": ["student"],
    }
    assert {"id": course_id, "title": "Mathe 9b concern view"} in body["courses"]


@pytest.mark.anyio
async def test_learner_can_create_anonymous_concern_box_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    teacher = store.create(sub="teacher-concern-write", roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub="student-concern-write", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern create")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )

        learner_headers = _mock_bearer_auth(
            monkeypatch, sub="student-concern-write", roles=["student"], name="Lena"
        )
        response = await client.post(
            "/api/learning/concern-box/entries",
            headers={**learner_headers, "Origin": "http://test"},
            json={
                "course_id": course_id,
                "message_text": "Mehr Beispiele wären hilfreich.",
                "anonymous": True,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["created_at"]


@pytest.mark.anyio
async def test_learner_concern_box_rejects_course_without_membership(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    teacher = store.create(sub="teacher-concern-forbidden", roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern forbidden")
        learner_headers = _mock_bearer_auth(
            monkeypatch, sub="student-concern-forbidden", roles=["student"], name="Lena"
        )

        response = await client.post(
            "/api/learning/concern-box/entries",
            headers={**learner_headers, "Origin": "http://test"},
            json={
                "course_id": course_id,
                "message_text": "Das sollte nicht gehen.",
                "anonymous": True,
            },
        )

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.anyio
async def test_teacher_concern_box_view_masks_anonymous_entries_and_shows_named_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    monkeypatch.setattr(
        teaching_routes,
        "resolve_student_names",
        lambda subs: {"student-concern-reader": "Lena"},
    )
    teacher = store.create(sub="teacher-concern-reader", roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub="student-concern-reader", roles=["student"], name="Lena", ttl_seconds=60)
    teacher_headers = _mock_bearer_auth(monkeypatch, sub="teacher-concern-reader", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern teacher view")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )

        learner_headers = _mock_bearer_auth(
            monkeypatch, sub="student-concern-reader", roles=["student"], name="Lena"
        )
        await client.post(
            "/api/learning/concern-box/entries",
            headers={**learner_headers, "Origin": "http://test"},
            json={
                "course_id": course_id,
                "message_text": "Anonymer Hinweis",
                "anonymous": True,
            },
        )
        await client.post(
            "/api/learning/concern-box/entries",
            headers={**learner_headers, "Origin": "http://test"},
            json={
                "course_id": course_id,
                "message_text": "Hinweis mit Namen",
                "anonymous": False,
            },
        )
        teacher_headers = _mock_bearer_auth(monkeypatch, sub="teacher-concern-reader", roles=["teacher"], name="Ada")

        response = await client.get("/api/teaching/views/concern-box", headers=teacher_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["active_scope"] == "open"
    assert [scope["id"] for scope in body["scopes"]] == ["open", "archived"]
    assert [entry["message_text"] for entry in body["entries"]] == ["Hinweis mit Namen", "Anonymer Hinweis"]
    assert body["entries"][0]["student_name"] == "Lena"
    assert body["entries"][1]["student_name"] is None


@pytest.mark.anyio
async def test_teacher_can_archive_and_restore_concern_box_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    teacher = store.create(sub="teacher-concern-archive", roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub="student-concern-archive", roles=["student"], name="Lena", ttl_seconds=60)
    teacher_headers = _mock_bearer_auth(monkeypatch, sub="teacher-concern-archive", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern archive")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )
        learner_headers = _mock_bearer_auth(
            monkeypatch, sub="student-concern-archive", roles=["student"], name="Lena"
        )
        created = await client.post(
            "/api/learning/concern-box/entries",
            headers={**learner_headers, "Origin": "http://test"},
            json={
                "course_id": course_id,
                "message_text": "Bitte mehr Wiederholungen.",
                "anonymous": True,
            },
        )
        entry_id = str(created.json()["id"])
        teacher_headers = _mock_bearer_auth(monkeypatch, sub="teacher-concern-archive", roles=["teacher"], name="Ada")

        archive_response = await client.post(
            f"/api/teaching/concern-box/entries/{entry_id}/archive",
            headers={**teacher_headers, "Origin": "http://test"},
        )
        open_response = await client.get("/api/teaching/views/concern-box?scope=open", headers=teacher_headers)
        archived_response = await client.get(
            "/api/teaching/views/concern-box?scope=archived", headers=teacher_headers
        )
        restore_response = await client.post(
            f"/api/teaching/concern-box/entries/{entry_id}/restore",
            headers={**teacher_headers, "Origin": "http://test"},
        )
        reopened_response = await client.get("/api/teaching/views/concern-box?scope=open", headers=teacher_headers)

    assert archive_response.status_code == 204
    assert open_response.json()["entries"] == []
    assert [entry["id"] for entry in archived_response.json()["entries"]] == [entry_id]
    assert restore_response.status_code == 204
    assert [entry["id"] for entry in reopened_response.json()["entries"]] == [entry_id]
