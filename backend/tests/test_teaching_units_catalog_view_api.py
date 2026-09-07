"""API tests for the teacher units catalog read-model."""

from __future__ import annotations

import os
from uuid import uuid4

import httpx
import psycopg
import pytest
from httpx import ASGITransport

from backend.tests.utils.db import is_safe_db_test_dsn, require_db_or_skip
from backend.web.main import create_app

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


@pytest.fixture
def app():
    require_db_or_skip()
    claims = {}
    created = create_app(access_token_verifier=lambda token, cfg: claims)
    created.state.claims = claims
    created.state.unit_ids = []
    created.state.course_ids = []
    yield created
    dsn = os.environ["RLS_TEST_SERVICE_DSN"]
    assert is_safe_db_test_dsn(dsn)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "delete from public.courses where id = any(%s::uuid[])", (created.state.course_ids,)
        )
        conn.execute(
            "delete from public.units where id = any(%s::uuid[])", (created.state.unit_ids,)
        )


def _mock_bearer_auth(app, *, sub, roles, name):
    app.state.claims.clear()
    app.state.claims.update(
        {"sub": sub, "name": name, "gustav_display_name": name, "realm_access": {"roles": roles}}
    )
    return {"Authorization": "Bearer test.jwt"}


async def _create_unit(
    client: httpx.AsyncClient,
    app,
    title: str,
    summary: str | None = None,
) -> str:
    response = await client.post(
        "/api/teaching/units",
        json={"title": title, "summary": summary},
        headers={"Origin": "http://test"},
    )
    assert response.status_code == 201
    app.state.unit_ids.append(response.json()["id"])
    return response.json()["id"]


async def _create_course(client: httpx.AsyncClient, app, title: str) -> str:
    response = await client.post(
        "/api/teaching/courses",
        json={
            "title": title,
            "subject": "Mathematik",
            "grade_level": "8",
            "school_year_start": 2026,
        },
        headers={"Origin": "http://test"},
    )
    assert response.status_code == 201
    app.state.course_ids.append(response.json()["id"])
    return response.json()["id"]


@pytest.mark.anyio
async def test_teacher_units_catalog_returns_recent_units_as_list(
    app,
) -> None:
    owner = f"teacher-{uuid4()}"
    store = app.state.runtime.session_store
    session = store.create(sub=owner, roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(app, sub=owner, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)

        draft_unit_id = await _create_unit(client, app, "Bruchterme")
        active_unit_id = await _create_unit(
            client, app, "Lineare Gleichungen", "Gleichungen sicher lösen."
        )
        course_id = await _create_course(client, app, "8a Mathematik")

        await client.post(
            f"/api/teaching/units/{active_unit_id}/sections",
            json={"title": "Terme umformen"},
            headers={"Origin": "http://test"},
        )
        await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": active_unit_id},
            headers={"Origin": "http://test"},
        )

        response = await client.get("/api/teaching/views/units/catalog", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "private, no-store"

    payload = response.json()
    assert payload["query"] == ""
    assert payload["result_count"] == 2
    assert payload["create_href"] == "/teaching/units?create=1"
    assert payload["items"][0]["id"] == active_unit_id
    assert payload["items"][0]["title"] == "Lineare Gleichungen"
    assert payload["items"][0]["status_label"] == "Aktiv im Unterricht"
    assert payload["items"][0]["status_tone"] == "success"
    assert payload["items"][0]["courses_count"] == 1
    assert payload["items"][0]["courses"] == [
        {"id": course_id, "title": "8a Mathematik", "href": f"/teaching/courses/{course_id}"}
    ]
    assert payload["items"][1]["id"] == draft_unit_id
    assert payload["items"][1]["status_label"] == "Entwurf"
    assert payload["items"][1]["status_tone"] == "muted"
    assert payload["items"][1]["courses_count"] == 0
    assert payload["items"][1]["courses"] == []


@pytest.mark.anyio
async def test_teacher_units_catalog_filters_by_query(
    app,
) -> None:
    owner = f"teacher-{uuid4()}"
    store = app.state.runtime.session_store
    session = store.create(sub=owner, roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(app, sub=owner, roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        await _create_unit(client, app, "Statistik Grundlagen")
        unit_id = await _create_unit(client, app, "Quadratische Funktionen")
        await client.post(
            f"/api/teaching/units/{unit_id}/sections",
            json={"title": "Scheitelpunkt"},
            headers={"Origin": "http://test"},
        )

        response = await client.get(
            "/api/teaching/views/units/catalog?query=funktion",
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "funktion"
    assert payload["result_count"] == 1
    assert payload["items"][0]["title"] == "Quadratische Funktionen"
    assert payload["items"][0]["status_label"] == "In Bearbeitung"


async def test_home_and_catalog_exclude_foreign_units_and_courses(app) -> None:
    store = app.state.runtime.session_store
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        owners = [f"teacher-{uuid4()}" for _ in range(2)]
        units, courses = [], []
        for owner in owners:
            session = store.create(sub=owner, roles=["teacher"], name="Ada", ttl_seconds=60)
            client.cookies.set("gustav_session", session.session_id)
            units.append(await _create_unit(client, app, "Eigene Lerneinheit"))
            courses.append(await _create_course(client, app, "Eigener Kurs"))
            attached = await client.post(
                f"/api/teaching/courses/{courses[-1]}/modules",
                json={"unit_id": units[-1]},
                headers={"Origin": "http://test"},
            )
            assert attached.status_code == 201

        client.cookies.clear()
        for index, owner in enumerate(owners):
            headers = _mock_bearer_auth(app, sub=owner, roles=["teacher"], name="Ada")
            catalog = await client.get("/api/teaching/views/units/catalog", headers=headers)
            home = await client.get("/api/teaching/views/teacher-home", headers=headers)
            assert catalog.status_code == home.status_code == 200
            assert [item["id"] for item in catalog.json()["items"]] == [units[index]]
            assert [item["id"] for item in home.json()["recent_units"]] == [units[index]]
            assert [item["id"] for item in home.json()["courses"]] == [courses[index]]
            assert catalog.json()["items"][0]["courses"][0]["id"] == courses[index]


@pytest.mark.anyio
async def test_teacher_units_catalog_forbids_students(app) -> None:
    headers = _mock_bearer_auth(app, sub="student-view", roles=["student"], name="Lena")

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/teaching/views/units/catalog", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}
