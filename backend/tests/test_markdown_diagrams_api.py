"""The shared diagram API never reads stored content or exposes parser diagnostics."""

from __future__ import annotations

import importlib
from unittest.mock import Mock

import httpx
import pytest

import backend.web.main as main
from backend.tests.runtime_auth_helpers import install_session_store

pytestmark = pytest.mark.anyio("asyncio")
PATH = "/api/markdown/diagrams"


@pytest.mark.parametrize("role", ["teacher", "student"])
async def test_authorized_roles_receive_ordered_private_results(monkeypatch, role):
    store = install_session_store(monkeypatch, main)
    session = store.create(sub="diagram-user", roles=[role], name="User")
    routes = importlib.import_module("backend.web.routes.markdown_diagrams")
    render = Mock(
        return_value=[{"png": "aGVsbG8=", "width": 10, "height": 5}, {"error": "invalid_diagram"}]
    )
    monkeypatch.setattr(routes, "render_sources", render)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        response = await client.post(
            PATH,
            headers={"Origin": "http://test"},
            json={"sources": ["sequenceDiagram", "bad"], "theme": "dark"},
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["diagrams"] == render.return_value
    assert render.call_args.kwargs["theme"] == "dark"


async def test_auth_role_and_csrf_fail_before_rendering(monkeypatch):
    store = install_session_store(monkeypatch, main)
    routes = importlib.import_module("backend.web.routes.markdown_diagrams")
    render = Mock(side_effect=AssertionError("must not render unauthorized input"))
    monkeypatch.setattr(routes, "render_sources", render)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        assert (await client.post(PATH, json={"sources": ["x"]})).status_code == 401
        session = store.create(sub="diagram-role", roles=["admin"], name="User")
        client.cookies.set("gustav_session", session.session_id)
        assert (
            await client.post(PATH, headers={"Origin": "http://test"}, json={"sources": ["x"]})
        ).status_code == 403
        session = store.create(sub="diagram-student", roles=["student"], name="User")
        client.cookies.set("gustav_session", session.session_id)
        for headers in [{}, {"Origin": "https://evil.example"}]:
            assert (
                await client.post(PATH, headers=headers, json={"sources": ["x"]})
            ).status_code == 403
    render.assert_not_called()


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"sources": []}, 400),
        ({"sources": ["x"] * 101}, 400),
        ({"sources": [7]}, 400),
        ({"sources": ["x" * 50001]}, 400),
        ({"sources": ["x" * 50000] * 5}, 413),
        ({"sources": ["x"], "theme": "unsafe"}, 400),
        ({"sources": ["x"], "config": {}}, 400),
    ],
)
async def test_invalid_batches_are_rejected_without_rendering(monkeypatch, payload, status):
    store = install_session_store(monkeypatch, main)
    session = store.create(sub="diagram-user", roles=["teacher"], name="User")
    routes = importlib.import_module("backend.web.routes.markdown_diagrams")
    render = Mock()
    monkeypatch.setattr(routes, "render_sources", render)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        response = await client.post(PATH, headers={"Origin": "http://test"}, json=payload)
    assert response.status_code == status
    render.assert_not_called()


async def test_technical_failure_is_not_a_content_error(monkeypatch):
    from backend.diagram_renderer import DiagramRenderError

    store = install_session_store(monkeypatch, main)
    session = store.create(sub="diagram-user", roles=["teacher"], name="User")
    routes = importlib.import_module("backend.web.routes.markdown_diagrams")
    monkeypatch.setattr(
        routes, "render_sources", Mock(side_effect=DiagramRenderError("render_timeout"))
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        response = await client.post(
            PATH, headers={"Origin": "http://test"}, json={"sources": ["x"]}
        )
    assert response.status_code == 503
    assert response.json()["error"] == "render_timeout"
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("cause", ["repeated_output", "renderer_413"])
async def test_output_limit_reaches_browser_as_private_413(monkeypatch, cause):
    import base64
    from io import BytesIO

    from PIL import Image

    from backend.diagram_renderer import diagram_key, render_sources

    store = install_session_store(monkeypatch, main)
    session = store.create(sub="diagram-budget-user", roles=["student"], name="User")
    routes = importlib.import_module("backend.web.routes.markdown_diagrams")
    source = "flowchart LR\nA-->B"
    stream = BytesIO()
    Image.new("RGB", (200, 100), "white").save(stream, format="PNG")
    content = stream.getvalue()

    def respond(request):
        if cause == "renderer_413":
            return httpx.Response(413, text="private renderer diagnostic")
        return httpx.Response(200, json={"diagrams": [{
            "id": diagram_key(source), "png": base64.b64encode(content).decode(),
        }]})

    def render(sources, **kwargs):
        # Exercise the real adapter and route; only transport and budget are controlled.
        kwargs["max_output_bytes"] = len(content) * 2
        return render_sources(sources, transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(routes, "render_sources", render)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        client.cookies.set("gustav_session", session.session_id)
        response = await client.post(
            PATH, headers={"Origin": "http://test"}, json={"sources": [source] * 3},
        )
    assert response.status_code == 413
    assert response.json() == {"error": "output_too_large"}
    assert response.headers["cache-control"] == "private, no-store"
