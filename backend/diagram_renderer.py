"""Shared, bounded PNG adapter for browser Markdown and printable documents.

Callers authorize access before submitting sources. Nothing is persisted and
untrusted parser diagnostics never cross this boundary.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections import Counter
from io import BytesIO

import httpx
from PIL import Image

_ENDPOINT = "http://diagram-renderer:3001/render"


class DiagramRenderError(Exception):
    """A stable technical failure; content errors remain individual results."""

    def __init__(self, code: str, status: int = 503):
        super().__init__(code)
        self.code = code
        self.status = status


def diagram_key(source: str) -> str:
    """Deduplicate identical definitions within a transient batch."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def render_sources(
    sources: list[str],
    *,
    theme: str = "light",
    deadline: float,
    max_output_bytes: int = 50 * 1024 * 1024,
    transport: httpx.BaseTransport | None = None,
) -> list[dict]:
    """Render a batch in input order, including duplicates, with checked PNGs.

    `deadline` covers transport and output checks; `max_output_bytes` bounds
    decoded images across all returned occurrences, including duplicates. The
    caller must authorize the sources. Oversized output raises a stable 413;
    technical failures raise 503 without exposing renderer diagnostics. The
    optional HTTP transport permits isolated adapter tests.
    """
    if not sources:
        return []
    keys = [diagram_key(source) for source in sources]
    occurrences = Counter(keys)
    definitions = dict(zip(keys, sources, strict=True))
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DiagramRenderError("render_timeout")
    try:
        with httpx.Client(transport=transport, timeout=remaining, trust_env=False) as client:
            with client.stream(
                "POST",
                _ENDPOINT,
                json={
                    "diagrams": [
                        {"id": key, "source": source} for key, source in definitions.items()
                    ],
                    "theme": theme,
                    "budget_ms": max(1, int(remaining * 1000)),
                    "max_output_bytes": max_output_bytes,
                },
            ) as response:
                if response.status_code == 413:
                    raise DiagramRenderError("output_too_large", 413)
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    if time.monotonic() >= deadline:
                        raise httpx.ReadTimeout("diagram_budget_exhausted")
                    size += len(chunk)
                    if size > max_output_bytes * 2:
                        raise DiagramRenderError("output_too_large", 413)
                    chunks.append(chunk)
                entries = json.loads(b"".join(chunks))["diagrams"]
        if len(entries) != len(definitions) or {item["id"] for item in entries} != set(definitions):
            raise ValueError("invalid_diagram_results")
        results, total = {}, 0
        for entry in entries:
            if entry.get("error") in {"invalid_diagram", "diagram_too_large"}:
                results[entry["id"]] = {"error": entry["error"]}
                continue
            content = base64.b64decode(entry["png"], validate=True)
            # Render and validate once, but budget every copy serialized for the caller.
            total += len(content) * occurrences[entry["id"]]
            if total > max_output_bytes:
                raise DiagramRenderError("output_too_large", 413)
            with Image.open(BytesIO(content)) as image:
                if image.format != "PNG" or image.width * image.height > 40_000_000:
                    raise ValueError("invalid_diagram_image")
                # The single renderer produces 3x images for sharp screen/print output.
                width, height = (image.width + 2) // 3, (image.height + 2) // 3
                image.verify()
            results[entry["id"]] = {"png": entry["png"], "width": width, "height": height}
        return [results[key] for key in keys]
    except DiagramRenderError:
        raise
    except httpx.TimeoutException as exc:
        raise DiagramRenderError("render_timeout") from exc
    except Exception as exc:
        raise DiagramRenderError("renderer_unavailable") from exc
