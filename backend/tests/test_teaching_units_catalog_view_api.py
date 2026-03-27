"""API tests for the teacher units catalog read-model."""

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
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
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
    assert payload["active_view"] == "recent"
    assert payload["query"] == ""
    assert payload["result_count"] == 2
    assert payload["create_href"] == "/teaching/units?create=1"
    assert payload["views"][0]["id"] == "recent"
    assert payload["views"][0]["active"] is True
    assert [view["id"] for view in payload["views"]] == ["recent", "all", "active", "draft", "unassigned"]
    assert payload["filters"]["status"] == [
        {"id": "all", "label": "Alle", "active": True},
        {"id": "active", "label": "Im Unterricht aktiv", "active": False},
        {"id": "draft", "label": "Entwürfe", "active": False},
        {"id": "unassigned", "label": "Ohne Kurs", "active": False},
    ]
    assert payload["items"][0]["id"] == active_unit_id
    assert payload["items"][0]["title"] == "Lineare Gleichungen"
    assert payload["items"][0]["meta"] == "1 Abschnitt · 1 Kurs"
    assert payload["items"][1]["id"] == draft_unit_id
    assert payload["items"][1]["meta"] == "0 Abschnitte · 0 Kurse"
    assert "selected_item" not in payload


@pytest.mark.anyio
async def test_teacher_units_catalog_filters_by_query_and_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    monkeypatch.setattr(main, "SESSION_STORE", store)
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
            "/api/teaching/views/units/catalog?query=funktion&status=draft",
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "funktion"
    assert payload["active_filters"] == {
        "status": "draft",
        "subject": "",
        "grade_level": "",
        "course_id": "",
    }
    assert payload["result_count"] == 0
    assert payload["items"] == []


@pytest.mark.anyio
async def test_teacher_units_catalog_forbids_students(monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _mock_bearer_auth(monkeypatch, sub="student-view", roles=["student"], name="Lena")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.get("/api/teaching/views/units/catalog", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}
