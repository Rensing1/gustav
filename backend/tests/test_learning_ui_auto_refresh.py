import asyncio
import re
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
    """History fragment must include a dedicated poller while analysis runs.

    The history wrapper itself must remain stable (no outerHTML polling) so
    preview artifacts do not get re-rendered every cycle.
    """
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
        "feedback_md": None,
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
    # In-progress (pending/extracted) → wrapper stays stable, poller drives refresh.
    assert "class=\"task-panel__history\"" in html
    assert "hx-get=\"/learning/courses/c1/tasks/t1/history\"" not in html
    assert f'data-open-attempt-id="{latest["id"]}"' in html
    hx_vals = re.search(r'hx-vals=[\'"]\{"open_attempt_id":"([^"]*)"\}[\'"]', html)
    assert hx_vals and hx_vals.group(1) == latest["id"]
    assert 'id="task-history-poll-t1"' in html
    assert 'hx-get="/learning/courses/c1/tasks/t1/history/poll"' in html
    assert "hx-trigger=\"every 10s\"" in html
    assert "data-pending=\"true\"" in html


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["pending", "extracted"])
async def test_history_fragment_shows_spinner_while_in_progress(monkeypatch: pytest.MonkeyPatch, status: str):
    """History fragment should render a spinner hint when analysis is pending/extracted."""
    student = _student_session()

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
        "feedback_md": None,
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
    # Spinner hint visible while analysis runs
    assert "Analyse läuft" in html
    assert "status-chip" in html
    assert "spinner" in html


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["completed", "failed"])
async def test_history_fragment_hides_spinner_when_done_or_failed(monkeypatch: pytest.MonkeyPatch, status: str):
    """No spinner hint should render for completed or failed submissions."""
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
        "analysis_status": status,
        "analysis_json": {"text": "Hallo"} if status == "completed" else None,
        "feedback_md": "Gut gemacht" if status == "completed" else None,
        "error_code": "E_GENERIC" if status == "failed" else None,
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
    assert "Analyse läuft" not in html
    assert "status-chip" not in html
    assert "spinner" not in html


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
        "feedback_md": "Gut gemacht",
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
    # Completed → no poller
    assert "class=\"task-panel__history\"" in html
    assert "data-pending=\"false\"" in html
    assert "hx-get=\"/learning/courses/c1/tasks/t1/history" not in html
    assert "hx-trigger=\"" not in html
    assert 'id="task-history-poll-t1"' not in html


@pytest.mark.anyio
async def test_history_fragment_exposes_submission_ids_and_open_state_attrs(monkeypatch: pytest.MonkeyPatch):
    """Fragment must expose submission ids + open state hooks for HTMX persistence."""
    student = _student_session()

    latest = {
        "id": str(uuid.uuid4()),
        "attempt_nr": 3,
        "kind": "text",
        "text_body": "Neueste Antwort",
        "mime_type": None,
        "size_bytes": None,
        "storage_key": None,
        "sha256": None,
        "analysis_status": "pending",
        "analysis_json": None,
        "feedback_md": None,
        "error_code": None,
        "created_at": "2025-11-04T12:10:00+00:00",
        "completed_at": None,
    }
    older = {
        "id": str(uuid.uuid4()),
        "attempt_nr": 2,
        "kind": "text",
        "text_body": "Ältere Antwort",
        "mime_type": None,
        "size_bytes": None,
        "storage_key": None,
        "sha256": None,
        "analysis_status": "completed",
        "analysis_json": {"schema": "criteria.v2", "results": []},
        "feedback_md": "Gut gemacht",
        "error_code": None,
        "created_at": "2025-11-03T09:00:00+00:00",
        "completed_at": "2025-11-03T09:05:00+00:00",
    }

    open_id = older["id"]

    def _submissions(_params):
        return [latest, older]

    fake = _FakeAsyncClient({
        "/api/learning/courses/c1/tasks/t1/submissions": _submissions,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.get(f"/learning/courses/c1/tasks/t1/history?open_attempt_id={open_id}")
    assert r.status_code == 200
    html = r.text

    # Each <details> carries the submission id for client-side persistence
    assert f'data-submission-id="{latest["id"]}"' in html
    assert f'data-submission-id="{older["id"]}"' in html

    # Wrapper advertises which attempt should remain open and exposes hx-vals
    assert f'data-open-attempt-id="{open_id}"' in html
    hx_vals_match = re.search(r'hx-vals=[\'"]\{"open_attempt_id":"([^"]*)"\}[\'"]', html)
    assert hx_vals_match, "history wrapper must include hx-vals for open_attempt_id"
    assert hx_vals_match.group(1) == open_id

    # Toggle handler present so HTMX polls can update the open attempt id
    assert 'hx-on="toggle:' in html


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["pending", "extracted"])
async def test_unit_page_embeds_autopoll_when_latest_in_progress(monkeypatch: pytest.MonkeyPatch, status: str):
    """Unit page should embed the per-task poller when the latest attempt is pending.

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
            "feedback_md": None,
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
    assert "class=\"task-panel__history\"" in html
    assert f'id="task-history-poll-{task_id}"' in html
    assert f'hx-get="/learning/courses/{course_id}/tasks/{task_id}/history/poll"' in html
    assert "hx-trigger=\"every 10s\"" in html
    # Spinner hint visible while analysis runs
    assert "Analyse läuft" in html
    assert "status-chip" in html
    assert "spinner" in html




@pytest.mark.anyio
async def test_unit_page_hides_spinner_when_latest_completed(monkeypatch: pytest.MonkeyPatch):
    """Unit page should not show the in-progress spinner when latest attempt is done."""
    student = _student_session()
    course_id = str(uuid.uuid4())
    unit_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    open_id = str(uuid.uuid4())

    def _sections(_params):
        return [{
            "section": {"id": "s1", "title": "A", "position": 1, "unit_id": unit_id},
            "materials": [],
            "tasks": [{"id": task_id, "instruction_md": "Aufgabe", "criteria": ["K"], "position": 1}],
        }]

    def _submissions(_params):
        return [{
            "id": open_id,
            "attempt_nr": 1,
            "kind": "text",
            "text_body": "Hallo",
            "mime_type": None,
            "size_bytes": None,
            "storage_key": None,
            "sha256": None,
            "analysis_status": "completed",
            "analysis_json": {"text": "Hallo"},
            "feedback_md": "Gut gemacht",
            "error_code": None,
            "created_at": "2025-11-04T12:00:00+00:00",
            "completed_at": "2025-11-04T12:11:00+00:00",
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
    assert "Analyse läuft" not in html
    assert "status-chip" not in html
    assert "spinner" not in html


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["pending", "extracted"])
async def test_history_poll_endpoint_returns_oob_updates_without_preview(
    monkeypatch: pytest.MonkeyPatch, status: str
):
    """Poll endpoint must return OOB updates and never include preview HTML."""
    student = _student_session()

    latest_id = str(uuid.uuid4())
    latest = {
        "id": latest_id,
        "attempt_nr": 1,
        "kind": "image",
        "text_body": None,
        "mime_type": "image/png",
        "size_bytes": 123,
        "storage_key": "submissions/c/t/u/key.png",
        "sha256": "deadbeef",
        "analysis_status": status,
        "analysis_json": None,
        "feedback_md": None,
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
        r = await client.get("/learning/courses/c1/tasks/t1/history/poll")
    assert r.status_code == 200
    html = r.text

    # Poller replaces itself (and keeps polling while still in progress)
    assert 'id="task-history-poll-t1"' in html
    assert 'hx-get="/learning/courses/c1/tasks/t1/history/poll"' in html
    assert "hx-trigger=\"every 10s\"" in html

    # OOB updates for dynamic zones of the latest submission
    assert f'id="submission-text-{latest_id}"' in html
    assert f'id="submission-result-{latest_id}"' in html
    assert "hx-swap-oob" in html

    # Never include artifact preview markup in polling responses
    assert "<img" not in html
    assert "<iframe" not in html


@pytest.mark.anyio
async def test_history_poll_endpoint_stops_polling_when_completed(monkeypatch: pytest.MonkeyPatch):
    """When latest is completed, poll response must stop further polling and update content."""
    student = _student_session()

    latest_id = str(uuid.uuid4())
    latest = {
        "id": latest_id,
        "attempt_nr": 2,
        "kind": "text",
        "text_body": "Hallo",
        "mime_type": None,
        "size_bytes": None,
        "storage_key": None,
        "sha256": None,
        "analysis_status": "completed",
        "analysis_json": {"text": "Hallo"},
        "feedback_md": "Gut gemacht",
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
        r = await client.get("/learning/courses/c1/tasks/t1/history/poll")
    assert r.status_code == 200
    html = r.text

    assert 'id="task-history-poll-t1"' in html
    assert "hx-trigger" not in html, "poller must remove its interval to stop polling"
    assert f'id="submission-result-{latest_id}"' in html
    assert "Gut gemacht" in html


@pytest.mark.anyio
async def test_history_poll_endpoint_uses_limit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poll endpoint should fetch only the newest submission (limit=1)."""
    student = _student_session()

    latest_id = str(uuid.uuid4())
    latest = {
        "id": latest_id,
        "attempt_nr": 1,
        "kind": "text",
        "text_body": "Hallo",
        "mime_type": None,
        "size_bytes": None,
        "storage_key": None,
        "sha256": None,
        "analysis_status": "pending",
        "analysis_json": None,
        "feedback_md": None,
        "error_code": None,
        "created_at": "2025-11-04T12:00:00+00:00",
        "completed_at": None,
    }

    observed: dict = {}

    def _submissions(params):
        observed["params"] = params
        return [latest]

    fake = _FakeAsyncClient({
        "/api/learning/courses/c1/tasks/t1/submissions": _submissions,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.get("/learning/courses/c1/tasks/t1/history/poll")
    assert r.status_code == 200

    params = observed.get("params") or {}
    assert params.get("limit") == 1
    assert params.get("offset") == 0
