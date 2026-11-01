"""Diagram preparation is private, bounded and precedes isolated PDF layout."""

from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from backend.teaching.print_diagrams import collect_diagrams, diagram_key, render_diagrams
from backend.teaching.printouts import DEFAULT_PRINT_POLICY, PrintExportError
from backend.teaching.printouts_pdf import _markdown_for_print

SOURCE = "sequenceDiagram\nA->>B: Hallo\n"
DOCUMENT = {"nodes": [{"items": [{"body_md": f"```mermaid\n{SOURCE}```\n\n```text\n{SOURCE}```"}]}]}


def png() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (200, 100), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_collects_only_explicit_fences_and_deduplicates_sources():
    diagrams = collect_diagrams(DOCUMENT)
    assert diagrams == [{"id": diagram_key(SOURCE), "source": SOURCE}]
    assert collect_diagrams({"nodes": []}) == []


def test_print_substitutes_only_mermaid_and_keeps_syntax_fallback():
    key = diagram_key(SOURCE)
    assets = {key: "print-diagram:0"}
    rendered = _markdown_for_print(
        DOCUMENT["nodes"][0]["items"][0]["body_md"], diagram_assets=assets
    )
    assert rendered.count('<img src="print-diagram:0"') == 1
    assert "<pre>" in rendered and "A-&gt;&gt;B: Hallo" in rendered
    fallback = _markdown_for_print(f"```mermaid\n{SOURCE}```", diagram_assets={key: None})
    assert "Das Diagramm konnte nicht dargestellt werden" in fallback
    assert "A-&gt;&gt;B: Hallo" in fallback


def test_pdf_bridge_keeps_content_errors_and_maps_technical_failures(monkeypatch):
    import backend.teaching.print_diagrams as adapter
    from backend.diagram_renderer import DiagramRenderError

    monkeypatch.setattr(
        adapter, "render_sources", lambda *a, **kw: [{"png": base64.b64encode(png()).decode()}]
    )
    assert render_diagrams(DOCUMENT, deadline=123, policy=DEFAULT_PRINT_POLICY) == {
        diagram_key(SOURCE): png()
    }
    monkeypatch.setattr(adapter, "render_sources", lambda *a, **kw: [{"error": "invalid_diagram"}])
    assert render_diagrams(DOCUMENT, deadline=123, policy=DEFAULT_PRINT_POLICY) == {
        diagram_key(SOURCE): None
    }

    def unavailable(*args, **kwargs):
        raise DiagramRenderError("render_timeout")

    monkeypatch.setattr(adapter, "render_sources", unavailable)
    with pytest.raises(PrintExportError) as error:
        render_diagrams(DOCUMENT, deadline=123, policy=DEFAULT_PRINT_POLICY)
    assert error.value.code == "pdf_render_timeout"


def test_shared_adapter_deduplicates_and_restores_order():
    import json
    import time

    import httpx

    from backend.diagram_renderer import render_sources

    def respond(request):
        payload = json.loads(request.content)
        assert payload["theme"] == "dark"
        assert len(payload["diagrams"]) == 2
        return httpx.Response(
            200,
            json={
                "diagrams": [
                    {"id": diagram_key("bad"), "error": "invalid_diagram"},
                    {"id": diagram_key(SOURCE), "png": base64.b64encode(png()).decode()},
                ]
            },
        )

    result = render_sources(
        [SOURCE, "bad", SOURCE],
        theme="dark",
        deadline=time.monotonic() + 10,
        transport=httpx.MockTransport(respond),
    )
    assert result[0] == result[2]
    assert result[0]["width"] == 67
    assert result[1] == {"error": "invalid_diagram"}


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [{"id": "wrong", "png": "bad"}],
        [{"id": diagram_key(SOURCE), "png": "bad"}],
        [{"id": diagram_key(SOURCE), "error": "internal_private_error"}],
    ],
)
def test_shared_adapter_rejects_invalid_results(entries):
    import time

    import httpx

    from backend.diagram_renderer import DiagramRenderError, render_sources

    with pytest.raises(DiagramRenderError, match="renderer_unavailable"):
        render_sources(
            [SOURCE],
            deadline=time.monotonic() + 10,
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"diagrams": entries})
            ),
        )


def test_shared_adapter_handles_timeout_and_empty_input():
    import time

    import httpx

    from backend.diagram_renderer import DiagramRenderError, render_sources

    assert render_sources([], deadline=0) == []

    def timeout(request):
        raise httpx.ReadTimeout("private diagnostic")

    with pytest.raises(DiagramRenderError, match="render_timeout"):
        render_sources(
            [SOURCE], deadline=time.monotonic() + 10, transport=httpx.MockTransport(timeout)
        )


@pytest.mark.parametrize("below_limit", [False, True])
def test_output_budget_counts_every_occurrence_at_the_exact_boundary(below_limit):
    import json
    import time

    import httpx

    from backend.diagram_renderer import DiagramRenderError, render_sources

    content = png()
    sources = [SOURCE, "bad", SOURCE, SOURCE]
    limit = len(content) * 3 - int(below_limit)

    def respond(request):
        # Repeated output must count fully without doing repeated rendering work.
        assert len(json.loads(request.content)["diagrams"]) == 2
        return httpx.Response(200, json={"diagrams": [
            {"id": diagram_key("bad"), "error": "invalid_diagram"},
            {"id": diagram_key(SOURCE), "png": base64.b64encode(content).decode()},
        ]})

    def render():
        return render_sources(
            sources, deadline=time.monotonic() + 10,
            max_output_bytes=limit, transport=httpx.MockTransport(respond),
        )

    if below_limit:
        with pytest.raises(DiagramRenderError, match="^output_too_large$") as error:
            render()
        assert error.value.status == 413
    else:
        result = render()
        assert result[0] == result[2] == result[3]
        assert result[1] == {"error": "invalid_diagram"}


@pytest.mark.parametrize("status,code", [(413, "output_too_large"), (500, "renderer_unavailable"), (503, "renderer_unavailable")])
def test_shared_adapter_preserves_size_errors_without_exposing_diagnostics(status, code):
    import time

    import httpx

    from backend.diagram_renderer import DiagramRenderError, render_sources

    with pytest.raises(DiagramRenderError, match=f"^{code}$") as error:
        render_sources(
            [SOURCE], deadline=time.monotonic() + 10,
            transport=httpx.MockTransport(lambda request: httpx.Response(
                status, text="private renderer diagnostic",
            )),
        )
    assert error.value.status == (413 if status == 413 else 503)
