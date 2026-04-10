"""
Teaching API: task-centric H5P authoring helpers.

Why:
    The teacher UI should work against the task it is editing, not against raw
    H5P `content_id` plumbing. These endpoints wrap the existing H5P service
    and keep the visible teacher flow native to GUSTAV.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_unit(client: httpx.AsyncClient, title: str = "Unit") -> dict:
    response = await client.post("/api/teaching/units", json={"title": title})
    assert response.status_code == 201
    return response.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Section") -> dict:
    response = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert response.status_code == 201
    return response.json()


async def _create_h5p_task(client: httpx.AsyncClient, unit_id: str, section_id: str, *, content_id: str | None) -> dict:
    response = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": "H5P placeholder", "h5p": {"content_id": content_id, "display_options": {}}},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.anyio
async def test_task_h5p_editor_model_uses_task_linked_content_id(monkeypatch: pytest.MonkeyPatch) -> None:
    import routes.teaching as teaching  # noqa: E402

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-editor-model", name="T", roles=["teacher"])  # type: ignore

    seen: list[tuple[str, str, dict | None]] = []

    async def fake_h5p_request(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen.append((method, path, kwargs.get("params")))
        return httpx.Response(
            200,
            json={"contentId": "2689406715", "scripts": [], "styles": ["/h5p/theme/h5p-gustav.css"]},
        )

    monkeypatch.setattr(teaching, "_request_h5p_service", fake_h5p_request)

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])
        task = await _create_h5p_task(client, unit["id"], section["id"], content_id="2689406715")

        response = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/h5p/editor-model"
        )

    assert response.status_code == 200
    assert response.json()["contentId"] == "2689406715"
    assert seen == [("GET", "/editor/model", {"content_id": "2689406715"})]


@pytest.mark.anyio
async def test_task_h5p_import_links_uploaded_content_to_task(monkeypatch: pytest.MonkeyPatch) -> None:
    import routes.teaching as teaching  # noqa: E402

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-import", name="T", roles=["teacher"])  # type: ignore

    seen: list[tuple[str, str, str | None]] = []

    async def fake_h5p_request(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        file_payload = kwargs.get("files") or {}
        uploaded = file_payload.get("file")
        filename = uploaded[0] if isinstance(uploaded, tuple) and uploaded else None
        seen.append((method, path, filename))
        return httpx.Response(200, json={"content_id": "314159"})

    monkeypatch.setattr(teaching, "_request_h5p_service", fake_h5p_request)

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])
        task = await _create_h5p_task(client, unit["id"], section["id"], content_id=None)

        response = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/h5p/import",
            files={"file": ("interactive.h5p", b"PK\x03\x04demo", "application/zip")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "h5p"
    assert body["h5p"]["content_id"] == "314159"
    assert seen == [("POST", "/contents/import", "interactive.h5p")]


@pytest.mark.anyio
async def test_task_h5p_save_rolls_back_upstream_content_when_local_persist_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import routes.teaching as teaching  # noqa: E402

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-save-rollback", name="T", roles=["teacher"])  # type: ignore

    seen: list[tuple[str, str]] = []

    async def fake_h5p_request(method: str, path: str, **_kwargs):  # type: ignore[no-untyped-def]
        seen.append((method, path))
        if method == "POST" and path == "/contents":
            return httpx.Response(201, json={"content_id": "271828", "metadata": {"title": "Demo"}})
        if method == "DELETE" and path == "/contents/271828":
            return httpx.Response(204)
        raise AssertionError(f"unexpected upstream call: {(method, path)}")

    monkeypatch.setattr(teaching, "_request_h5p_service", fake_h5p_request)

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])
        task = await _create_h5p_task(client, unit["id"], section["id"], content_id=None)
        original_service = teaching._get_tasks_service()

        class FailingTasksService:
            def list_tasks(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                return original_service.list_tasks(*args, **kwargs)

            def update_task(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
                raise RuntimeError("db_write_failed")

        monkeypatch.setattr(teaching, "_get_tasks_service", lambda: FailingTasksService())

        response = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/h5p/save",
            json={"library": "H5P.Text 1.1", "params": {"text": "<p>Hello</p>"}},
        )

    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert seen == [("POST", "/contents"), ("DELETE", "/contents/271828")]


@pytest.mark.anyio
async def test_task_h5p_import_rolls_back_upstream_content_when_local_persist_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import routes.teaching as teaching  # noqa: E402

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-import-rollback", name="T", roles=["teacher"])  # type: ignore

    seen: list[tuple[str, str]] = []

    async def fake_h5p_request(method: str, path: str, **_kwargs):  # type: ignore[no-untyped-def]
        seen.append((method, path))
        if method == "POST" and path == "/contents/import":
            return httpx.Response(201, json={"content_id": "314159"})
        if method == "DELETE" and path == "/contents/314159":
            return httpx.Response(204)
        raise AssertionError(f"unexpected upstream call: {(method, path)}")

    monkeypatch.setattr(teaching, "_request_h5p_service", fake_h5p_request)

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])
        task = await _create_h5p_task(client, unit["id"], section["id"], content_id=None)
        original_service = teaching._get_tasks_service()

        class FailingTasksService:
            def list_tasks(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                return original_service.list_tasks(*args, **kwargs)

            def update_task(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
                raise RuntimeError("db_write_failed")

        monkeypatch.setattr(teaching, "_get_tasks_service", lambda: FailingTasksService())

        response = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/h5p/import",
            files={"file": ("interactive.h5p", b"PK\\x03\\x04demo", "application/zip")},
        )

    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert seen == [("POST", "/contents/import"), ("DELETE", "/contents/314159")]


@pytest.mark.anyio
async def test_task_h5p_reset_clears_linked_content_id_without_hitting_h5p_service(monkeypatch: pytest.MonkeyPatch) -> None:
    import routes.teaching as teaching  # noqa: E402

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-reset", name="T", roles=["teacher"])  # type: ignore

    async def fail_h5p_request(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("reset must not call upstream h5p service")

    monkeypatch.setattr(teaching, "_request_h5p_service", fail_h5p_request)

    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])
        task = await _create_h5p_task(client, unit["id"], section["id"], content_id="777")

        response = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}/h5p/reset"
        )

    assert response.status_code == 200
    assert response.json()["h5p"]["content_id"] is None
