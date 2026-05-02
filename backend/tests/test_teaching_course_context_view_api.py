"""API tests for the first teacher course context read-model."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore
from identity_access.stores import SessionStore  # type: ignore
from routes import app as app_routes  # type: ignore


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


async def _seed_teacher_course_context(client: httpx.AsyncClient) -> tuple[str, str]:
    course_response = await client.post(
        "/api/teaching/courses",
        json={"title": "Mathe 9b"},
        headers={"Origin": "http://test"},
    )
    course_id = course_response.json()["id"]

    unit_response = await client.post(
        "/api/teaching/units",
        json={"title": "Bruchrechnen"},
        headers={"Origin": "http://test"},
    )
    unit_id = unit_response.json()["id"]

    await client.post(
        f"/api/teaching/courses/{course_id}/modules",
        json={"unit_id": unit_id},
        headers={"Origin": "http://test"},
    )

    return course_id, unit_id


@pytest.mark.anyio
async def test_teacher_course_context_returns_course_members_and_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    monkeypatch.setattr(app_routes.teaching_routes, "resolve_student_names", lambda subs: {"student-context": "Lena"})
    teacher = store.create(sub="teacher-context", roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub="student-context", roles=["student"], name="Lena", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-context", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id, unit_id = await _seed_teacher_course_context(client)
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )

        response = await client.get(f"/api/teaching/views/courses/{course_id}/context", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json()["course"] == {
        "id": course_id,
        "title": "Mathe 9b",
        "href": f"/teaching/courses/{course_id}",
        "members_href": f"/teaching/courses/{course_id}/members",
        "diagnostics_href": f"/diagnostics/courses/{course_id}",
        "members_count": 1,
        "units_count": 1,
    }
    assert response.json()["units"] == [
        {
            "id": unit_id,
            "title": "Bruchrechnen",
            "position": 1,
            "href": f"/teaching/units/{unit_id}",
        }
    ]
    assert response.json()["members"] == [
        {
            "sub": "student-context",
            "name": "Lena",
            "href": "/users/student-context",
            "joined_at": response.json()["members"][0]["joined_at"],
        }
    ]


@pytest.mark.anyio
async def test_teacher_course_context_forbids_non_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    owner = store.create(sub="teacher-owner", roles=["teacher"], name="Ada", ttl_seconds=60)
    outsider = store.create(sub="teacher-outsider", roles=["teacher"], name="Linus", ttl_seconds=60)
    outsider_headers = _mock_bearer_auth(monkeypatch, sub="teacher-outsider", roles=["teacher"], name="Linus")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", owner.session_id)
        course_id, _unit_id = await _seed_teacher_course_context(client)

        response = await client.get(f"/api/teaching/views/courses/{course_id}/context", headers=outsider_headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.anyio
async def test_teacher_course_context_forbids_student(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-view", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get(
            "/api/teaching/views/courses/00000000-0000-0000-0000-000000000000/context",
            headers=headers,
        )

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.anyio
async def test_teacher_course_ai_usage_empty_course_returns_zero_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    monkeypatch.setattr(app_routes.teaching_routes, "resolve_student_names", lambda subs: {"student-usage": "Lena"})
    teacher = store.create(sub="teacher-usage", roles=["teacher"], name="Ada", ttl_seconds=60)
    student = store.create(sub="student-usage", roles=["student"], name="Lena", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-usage", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id, _unit_id = await _seed_teacher_course_context(client)
        await client.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": student.sub},
            headers={"Origin": "http://test"},
        )

        response = await client.get(f"/api/teaching/views/courses/{course_id}/ai-usage", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    body = response.json()
    assert body["course"]["id"] == course_id
    assert body["totals"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "known_events": 0,
        "unknown_events": 0,
        "breakdown": [],
    }
    assert body["learners"][0]["student"]["sub"] == "student-usage"
    assert body["learners"][0]["totals"]["known_events"] == 0


@pytest.mark.anyio
async def test_teacher_course_ai_usage_missing_course_has_private_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
    teacher = store.create(sub="teacher-usage-missing", roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-usage-missing", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", teacher.session_id)
        response = await client.get(
            "/api/teaching/views/courses/00000000-0000-0000-0000-000000000000/ai-usage",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "not_found"}
