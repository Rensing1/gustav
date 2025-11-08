import asyncio
import types
import uuid

import pytest
import httpx
from httpx import ASGITransport

from backend.web import main


def _student_session():
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    return student


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Minimal stub for httpx.AsyncClient used inside SSR routes.

    It returns canned responses based on the requested path.
    """

    def __init__(self, routes):
        self._routes = routes
        self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, params: dict | None = None):
        # Extract path portion
        path = url
        # Allow tests to pass a mapping of path->callable returning payload
        handler = self._routes.get(path)
        if handler is None:
            # Fallback to 404-like empty payload
            return _FakeResponse(404, {})
        payload = handler(params or {})
        return _FakeResponse(200, payload)


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["pending", "extracted"])
async def test_history_fragment_autopolls_for_in_progress_status(monkeypatch: pytest.MonkeyPatch, status: str):
    """History fragment must auto-refresh while analysis is pending or extracting."""
    student = _student_session()

    # Fake the internal API used by the fragment
    latest = {
        "id": str(uuid.uuid4()),
        "attempt_nr": 1,
        "kind": "image",
        "text_body": None,
        "mime_type": "image/png",
        "size_bytes": 123,
        "storage_key": "submissions/c/t/u/key.png",
        "sha256": "deadbeef",
        "analysis_status": status,
        "analysis_json": None,
        "feedback": None,
        "error_code": None,
        "created_at": "2025-11-04T12:00:00+00:00",
        "completed_at": None,
    }

    def _submissions(_params):
        return [latest]

    fake = _FakeAsyncClient({
        "/api/learning/courses/c1/tasks/t1/submissions": _submissions,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.get("/learning/courses/c1/tasks/t1/history?open_attempt_id=" + latest["id"])  # type: ignore[index]
    assert r.status_code == 200
    html = r.text
    # In-progress (pending/extracted) → auto-refresh attributes present
    assert "class=\"task-panel__history\"" in html
    assert "hx-get=\"/learning/courses/c1/tasks/t1/history?open_attempt_id=" in html
    assert "hx-trigger=\"every 2s\"" in html or "hx-trigger=\"load, every 2s\"" in html
    assert "data-pending=\"true\"" in html


@pytest.mark.anyio
async def test_history_fragment_stops_polling_when_completed(monkeypatch: pytest.MonkeyPatch):
    """When the latest attempt is completed, the fragment must not poll."""
    student = _student_session()

    latest = {
        "id": str(uuid.uuid4()),
        "attempt_nr": 2,
        "kind": "text",
        "text_body": "Hallo",
        "mime_type": None,
        "size_bytes": None,
        "storage_key": None,
        "sha256": None,
        "analysis_status": "completed",
        "analysis_json": {"text": "Hallo"},
        "feedback": "Gut gemacht",
        "error_code": None,
        "created_at": "2025-11-04T12:10:00+00:00",
        "completed_at": "2025-11-04T12:11:00+00:00",
    }

    def _submissions(_params):
        return [latest]

    fake = _FakeAsyncClient({
        "/api/learning/courses/c1/tasks/t1/submissions": _submissions,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.get("/learning/courses/c1/tasks/t1/history?open_attempt_id=" + latest["id"])  # type: ignore[index]
    assert r.status_code == 200
    html = r.text
    # Completed → no hx polling attributes
    assert "class=\"task-panel__history\"" in html
    assert "data-pending=\"false\"" in html
    assert "hx-get=\"/learning/courses/c1/tasks/t1/history" not in html
    assert "hx-trigger=\"" not in html


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["pending", "extracted"])
async def test_unit_page_embeds_autopoll_when_latest_in_progress(monkeypatch: pytest.MonkeyPatch, status: str):
    """Unit page should use a polling placeholder if the latest attempt is pending.

    This ensures that after PRG the history auto-refreshes (vision text/feedback).
    """
    student = _student_session()
    course_id = str(uuid.uuid4())
    unit_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    open_id = str(uuid.uuid4())

    # Provide minimal sections with a single task
    def _sections(_params):
        return [{
            "section": {"id": "s1", "title": "A", "position": 1, "unit_id": unit_id},
            "materials": [],
            "tasks": [{"id": task_id, "instruction_md": "Aufgabe", "criteria": ["K"], "position": 1}],
        }]

    # Latest submission pending/extracted
    def _submissions(_params):
        return [{
            "id": open_id,
            "attempt_nr": 1,
            "kind": "image",
            "text_body": None,
            "mime_type": "image/png",
            "size_bytes": 100,
            "storage_key": "submissions/.../img.png",
            "sha256": "deadbeef",
            "analysis_status": status,
            "analysis_json": None,
            "feedback": None,
            "error_code": None,
            "created_at": "2025-11-04T12:00:00+00:00",
            "completed_at": None,
        }]

    fake = _FakeAsyncClient({
        f"/api/learning/courses/{course_id}/units/{unit_id}/sections": _sections,
        f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions": _submissions,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    url = f"/learning/courses/{course_id}/units/{unit_id}?show_history_for={task_id}&open_attempt_id={open_id}"
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.get(url)
    assert r.status_code == 200
    html = r.text
    # The pre-render should include a placeholder history with polling enabled
    assert "class=\"task-panel__history\"" in html
    expected_hx = f"hx-get=\"/learning/courses/{course_id}/tasks/{task_id}/history?open_attempt_id="
    assert expected_hx in html
    assert "hx-trigger=\"load, every 2s\"" in html or "hx-trigger=\"every 2s\"" in html
