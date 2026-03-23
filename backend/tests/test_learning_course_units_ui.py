"""Legacy learning course page retirement and unit-page handoff behavior."""

from __future__ import annotations

import httpx
from httpx import ASGITransport
import pytest

from utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    response = await client.post("/api/teaching/courses", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    response = await client.post("/api/teaching/units", json={"title": title})
    assert response.status_code == 201
    return response.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    response = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert response.status_code == 201
    return response.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    response = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert response.status_code in (201, 204)


@pytest.mark.anyio
async def test_learning_course_detail_legacy_entry_returns_gone_for_student() -> None:
    _require_db_or_skip()
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-legacy-course-detail", name="Schüler", roles=["student"])
    teacher = main.SESSION_STORE.create(sub="t-legacy-course-detail", name="Lehrkraft", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course(client, "Kurs Altpfad")
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)

        response = await client.get(f"/learning/courses/{course_id}")

    assert response.status_code == 410
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert "legacy route" in response.text.lower()


@pytest.mark.anyio
async def test_learning_unit_page_links_back_to_learning_home_instead_of_legacy_course_detail() -> None:
    _require_db_or_skip()
    import routes.learning as learning  # noqa: E402

    try:
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-learning-back-link", name="Lehrkraft", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="s-learning-back-link", name="Schüler", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course(client, "Kurs Ruecklink")
        unit = await _create_unit(client, "Unit Ruecklink")
        await _attach_unit(client, course_id, unit["id"])
        await _add_member(client, course_id, student.sub)

        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        response = await client.get(f"/learning/courses/{course_id}/units/{unit['id']}")

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert 'href="/learning"' in response.text
    assert f'href="/learning/courses/{course_id}"' not in response.text
