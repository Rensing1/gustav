"""API tests for the teacher units catalog read-model."""

from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport


import main  # type: ignore
from backend.tests.runtime_auth_helpers import install_session_store

teaching_routes = importlib.import_module("backend.web.routes.teaching")


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


async def _create_unit(
    client: httpx.AsyncClient,
    title: str,
    summary: str | None = None,
) -> str:
    response = await client.post(
        "/api/teaching/units",
        json={"title": title, "summary": summary},
        headers={"Origin": "http://test"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_course(client: httpx.AsyncClient, title: str) -> str:
    response = await client.post(
        "/api/teaching/courses",
        json={"title": title},
        headers={"Origin": "http://test"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.anyio
async def test_teacher_units_catalog_returns_recent_units_as_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teaching_routes.set_repo(teaching_routes._Repo())
    session = store.create(sub="teacher-units", roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-units", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)

        active_unit_id = await _create_unit(client, "Lineare Gleichungen", "Gleichungen sicher loesen.")
        draft_unit_id = await _create_unit(client, "Bruchterme")
        course_id = await _create_course(client, "8a Mathematik")

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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = install_session_store(monkeypatch, main)
    teaching_routes.set_repo(teaching_routes._Repo())
    session = store.create(sub="teacher-filter", roles=["teacher"], name="Ada", ttl_seconds=60)
    headers = _mock_bearer_auth(monkeypatch, sub="teacher-filter", roles=["teacher"], name="Ada")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set("gustav_session", session.session_id)
        await _create_unit(client, "Statistik Grundlagen")
        unit_id = await _create_unit(client, "Quadratische Funktionen")
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


@pytest.mark.anyio
async def test_teacher_units_catalog_forbids_students(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-view", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/teaching/views/units/catalog", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}
