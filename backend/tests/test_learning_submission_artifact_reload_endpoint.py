import types

import pytest
import httpx
from httpx import ASGITransport

from backend.web import main


pytestmark = pytest.mark.anyio("asyncio")


def _install_session_store():
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    return main.SESSION_STORE


@pytest.mark.anyio
async def test_submission_artifact_reload_requires_student_role(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _install_session_store()
    teacher = store.create(sub="t1", name="T", roles=["teacher"])

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)  # type: ignore[attr-defined]
        resp = await client.get("/learning/courses/c1/tasks/t1/submissions/s1/artifact")

    assert resp.status_code == 403
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_submission_artifact_reload_returns_stable_container(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _install_session_store()
    student = store.create(sub="s1", name="S", roles=["student"])

    submission_id = "deadbeef-dead-beef-dead-beef000042"
    submission = {
        "id": submission_id,
        "kind": "image",
        "mime_type": "image/png",
        "file_url": "http://storage.test/submissions/c1/t1/s1.png",
    }

    class _FakeResponse:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeInternalClient:
        def __init__(self, routes):
            self._routes = routes
            self.cookies = types.SimpleNamespace(set=lambda *a, **k: None)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, path: str, params=None):  # type: ignore[no-untyped-def]
            handler = self._routes.get(path)
            if handler is None:
                return _FakeResponse(404, {"error": "not_found"})
            return _FakeResponse(200, handler(params or {}))

    def _submissions(_params):
        return [submission]

    fake = _FakeInternalClient({
        "/api/learning/courses/c1/tasks/t1/submissions": _submissions,
    })

    import sys as _sys

    _fake_httpx_mod = types.SimpleNamespace(AsyncClient=lambda **k: fake, ASGITransport=ASGITransport)
    monkeypatch.setitem(_sys.modules, "httpx", _fake_httpx_mod)

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        resp = await client.get(f"/learning/courses/c1/tasks/t1/submissions/{submission_id}/artifact")

    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control") == "private, no-store"
    html = resp.text

    assert f'id="submission-artifact-{submission_id}"' in html
    assert 'data-artifact-reload="true"' in html
    assert 'file-preview--image' in html
