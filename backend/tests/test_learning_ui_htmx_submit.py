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

    Supports method-specific keys: 'GET /path' and 'POST /path'.
    """

    def __init__(self, routes):
        self._routes_get = {}
        self._routes_post = {}
        for k, v in routes.items():
            if isinstance(k, str) and k.startswith('GET '):
                self._routes_get[k[4:]] = v
            elif isinstance(k, str) and k.startswith('POST '):
                self._routes_post[k[5:]] = v
            else:
                self._routes_get[k] = v
        self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, params: dict | None = None):
        handler = self._routes_get.get(url)
        if handler is None:
            return _FakeResponse(404, {})
        payload = handler(params or {}) if callable(handler) else handler
        return _FakeResponse(200, payload)

    async def post(self, url: str, json: dict | None = None, headers: dict | None = None):
        handler = self._routes_post.get(url)
        if handler is None:
            return _FakeResponse(404, {})
        payload = handler(json or {}) if callable(handler) else handler
        return _FakeResponse(201, payload)


@pytest.mark.anyio
async def test_unit_task_form_has_htmx_attributes(monkeypatch: pytest.MonkeyPatch):
    """The student task form should submit via HTMX and target the history fragment."""
    student = _student_session()
    course_id = str(uuid.uuid4())
    unit_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    # Provide a single section with a single task so the unit page renders a form
    def _sections(_params):
        return [{
            "section": {"id": "s1", "title": "A", "position": 1, "unit_id": unit_id},
            "materials": [],
            "tasks": [{"id": task_id, "instruction_md": "Aufgabe", "criteria": ["K"], "position": 1}],
        }]

    fake = _FakeAsyncClient({
        f"GET /api/learning/courses/{course_id}/units/{unit_id}/sections": _sections,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    url = f"/learning/courses/{course_id}/units/{unit_id}?show_history_for={task_id}"
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.get(url)
    assert r.status_code == 200
    html = r.text
    # Form uses HTMX submit and targets the task history section
    assert f'hx-post="/learning/courses/{course_id}/tasks/{task_id}/submit"' in html
    assert f'hx-target="#task-history-{task_id}"' in html
    assert 'hx-swap="outerHTML"' in html


@pytest.mark.anyio
async def test_htmx_submit_returns_history_fragment_and_message(monkeypatch: pytest.MonkeyPatch):
    """Posting via HTMX should return the updated history fragment and trigger a success message."""
    student = _student_session()
    course_id = str(uuid.uuid4())
    unit_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    created_id = str(uuid.uuid4())

    # Fake API: creating a submission returns the id; history shows it pending
    def _create_submission(_json):
        return {"id": created_id}

    def _submissions(_params):
        return [{
            "id": created_id,
            "attempt_nr": 1,
            "kind": "text",
            "text_body": "Hallo",
            "analysis_status": "pending",
            "created_at": "2025-11-04T12:00:00+00:00",
        }]

    fake = _FakeAsyncClient({
        f"GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions": _submissions,
        f"GET /api/learning/courses/{course_id}/units/{unit_id}/sections": [{
            "section": {"id": "s1", "title": "A", "position": 1, "unit_id": unit_id},
            "materials": [],
            "tasks": [{"id": task_id, "instruction_md": "Aufgabe", "criteria": ["K"], "position": 1}],
        }],
        f"POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions": _create_submission,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    # HTMX form submit
    form = {
        "mode": "text",
        "unit_id": unit_id,
        "text_body": "Hallo",
    }
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.post(f"/learning/courses/{course_id}/tasks/{task_id}/submit", data=form, headers={"HX-Request": "true"})
    # Expect HTML fragment of history, not a redirect
    assert r.status_code == 200
    assert r.headers.get("HX-Trigger")
    html = r.text
    assert f'id="task-history-{task_id}"' in html
    # Pending → includes hx polling
    assert "hx-trigger=\"every 2s\"" in html or "hx-trigger=\"load, every 2s\"" in html


@pytest.mark.anyio
async def test_non_htmx_submit_keeps_prg(monkeypatch: pytest.MonkeyPatch):
    """Non-HTMX POST retains PRG redirect to the unit page for progressive enhancement."""
    student = _student_session()
    course_id = str(uuid.uuid4())
    unit_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    created_id = str(uuid.uuid4())

    def _create_submission(_json):
        return {"id": created_id}

    fake = _FakeAsyncClient({
        f"POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions": _create_submission,
    })
    import sys as _sys
    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    form = {"mode": "text", "unit_id": unit_id, "text_body": "Hallo"}
    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.post(f"/learning/courses/{course_id}/tasks/{task_id}/submit", data=form, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers.get("location", "").startswith(f"/learning/courses/{course_id}/units/{unit_id}")

