"""API tests for learner and teacher concern box read/write flows."""

from __future__ import annotations

import importlib
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport


main = importlib.import_module("backend.web.main")
teaching_routes = importlib.import_module("backend.web.routes.teaching")
from backend.tests.runtime_auth_helpers import install_session_store


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


def _unique_sub(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


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
    store = install_session_store(monkeypatch, main)
    teacher_sub = _unique_sub("teacher-concern")
    student_sub = _unique_sub("student-concern")
    teacher = store.create(sub=teacher_sub, roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub=student_sub, roles=["student"], name="Lena", ttl_seconds=60)
    _mock_bearer_auth(monkeypatch, sub=teacher_sub, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern view")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )
        learner_headers = _mock_bearer_auth(monkeypatch, sub=student_sub, roles=["student"], name="Lena")

        response = await client.get("/api/learning/views/concern-box", headers=learner_headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    body = response.json()
    assert body["user"] == {
        "sub": student_sub,
        "name": "Lena",
        "role": "student",
        "roles": ["student"],
    }
    assert {"id": course_id, "title": "Mathe 9b concern view"} in body["courses"]


@pytest.mark.anyio
async def test_learner_can_create_anonymous_concern_box_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_session_store(monkeypatch, main)
    teacher_sub = _unique_sub("teacher-concern-write")
    student_sub = _unique_sub("student-concern-write")
    teacher = store.create(sub=teacher_sub, roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub=student_sub, roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern create")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )

        learner_headers = _mock_bearer_auth(
            monkeypatch, sub=student_sub, roles=["student"], name="Lena"
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
    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub=_unique_sub("teacher-concern-forbidden"), roles=["teacher"], name="Ada", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern forbidden")
        learner_headers = _mock_bearer_auth(
            monkeypatch, sub=_unique_sub("student-concern-forbidden"), roles=["student"], name="Lena"
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
async def test_learner_concern_box_write_requires_bearer_even_with_cookie_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    student = store.create(sub="student-cookie-only", roles=["student"], name="Lena", ttl_seconds=60)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", student.session_id)
        response = await client.post(
            "/api/learning/concern-box/entries",
            headers={"Origin": "http://test"},
            json={
                "course_id": "11111111-1111-1111-1111-111111111111",
                "message_text": "Nur Cookie darf hier nicht reichen.",
                "anonymous": True,
            },
        )

    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "unauthenticated"}


@pytest.mark.anyio
async def test_learner_concern_box_rejects_invalid_course_id_as_bad_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_session_store(monkeypatch, main)
    learner_headers = _mock_bearer_auth(
        monkeypatch, sub="student-invalid-course", roles=["student"], name="Lena"
    )

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post(
            "/api/learning/concern-box/entries",
            headers={**learner_headers, "Origin": "http://test"},
            json={
                "course_id": "not-a-uuid",
                "message_text": "Ungültige Kurs-ID",
                "anonymous": True,
            },
        )

    assert response.status_code == 400
    assert response.json() == {"error": "bad_request", "detail": "invalid_course_id"}


@pytest.mark.anyio
async def test_teacher_concern_box_view_masks_anonymous_entries_and_shows_named_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    student_sub = _unique_sub("student-concern-reader")
    monkeypatch.setattr(
        teaching_routes,
        "resolve_student_names",
        lambda subs: {student_sub: "Lena"},
    )
    teacher_sub = _unique_sub("teacher-concern-reader")
    teacher = store.create(sub=teacher_sub, roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub=student_sub, roles=["student"], name="Lena", ttl_seconds=60)
    teacher_headers = _mock_bearer_auth(monkeypatch, sub=teacher_sub, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern teacher view")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )

        learner_headers = _mock_bearer_auth(
            monkeypatch, sub=student_sub, roles=["student"], name="Lena"
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
        teacher_headers = _mock_bearer_auth(monkeypatch, sub=teacher_sub, roles=["teacher"], name="Ada")

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
    store = install_session_store(monkeypatch, main)
    teacher_sub = _unique_sub("teacher-concern-archive")
    student_sub = _unique_sub("student-concern-archive")
    teacher = store.create(sub=teacher_sub, roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub=student_sub, roles=["student"], name="Lena", ttl_seconds=60)
    teacher_headers = _mock_bearer_auth(monkeypatch, sub=teacher_sub, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _seed_course_for_teacher(client, title="Mathe 9b concern archive")
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )
        learner_headers = _mock_bearer_auth(
            monkeypatch, sub=student_sub, roles=["student"], name="Lena"
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
        teacher_headers = _mock_bearer_auth(monkeypatch, sub=teacher_sub, roles=["teacher"], name="Ada")

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


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path_suffix", "detail"),
    [
        ("archive", "invalid_entry_id"),
        ("restore", "invalid_entry_id"),
    ],
)
async def test_teacher_concern_box_mutations_reject_invalid_entry_id(
    monkeypatch: pytest.MonkeyPatch,
    path_suffix: str,
    detail: str,
) -> None:
    store = install_session_store(monkeypatch, main)
    teacher = store.create(sub=_unique_sub("teacher-concern-bad-entry"), roles=["teacher"], name="Ada", ttl_seconds=60)
    teacher_headers = _mock_bearer_auth(monkeypatch, sub=teacher.sub, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        response = await client.post(
            f"/api/teaching/concern-box/entries/not-a-uuid/{path_suffix}",
            headers={**teacher_headers, "Origin": "http://test"},
        )

    assert response.status_code == 400
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "bad_request", "detail": detail}
