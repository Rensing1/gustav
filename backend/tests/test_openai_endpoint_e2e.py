"""
OpenAI-compatible endpoint E2E smoke tests (optional).

Why:
    GUSTAV's learning worker uses DSPy against an operator-provided
    OpenAI-compatible API endpoint. Unit tests intentionally stub network
    calls; these tests hit a real endpoint to catch wiring regressions early.

How to run:
    - Default (unit suite): skipped.
    - Enable explicitly:
        RUN_OPENAI_E2E=1 pytest -q -m openai_integration
      or:
        make test-openai

Defaults:
    - OpenAI base URL: OPENAI_BASE_URL from `.env`
      (override via OPENAI_E2E_BASE_URL)
    - Model: OPENAI_E2E_MODEL or AI_TEXT_MODEL from `.env`
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.openai_integration


def _should_run() -> bool:
    return os.getenv("RUN_OPENAI_E2E") == "1"


def _openai_base_url() -> str:
    """
    Resolve the base URL used for OpenAI-style endpoints.

    Contract:
        - Prefer OPENAI_E2E_BASE_URL (explicit override for these tests).
        - Otherwise, use OPENAI_BASE_URL, matching the application runtime.
        - OPENAI_E2E_ROOT remains a legacy fallback and receives `/v1`.
    """
    raw = (os.getenv("OPENAI_E2E_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip()
    if raw:
        return raw.rstrip("/")
    root = (os.getenv("OPENAI_E2E_ROOT") or "").strip().rstrip("/")
    if not root:
        raise AssertionError("OPENAI_BASE_URL or OPENAI_E2E_BASE_URL must be set for OpenAI endpoint E2E tests.")
    if root.endswith("/v1"):
        return root
    return f"{root}/v1"


def _model_name() -> str:
    model = (os.getenv("OPENAI_E2E_MODEL") or os.getenv("AI_TEXT_MODEL") or "").strip()
    return model or "ministral-3:3b"


def _auth_headers() -> dict[str, str]:
    key = (os.getenv("OPENAI_API_KEY") or "").strip() or "sk-noop"
    return {"Authorization": f"Bearer {key}"}


@pytest.mark.skipif(
    not _should_run(),
    reason="OpenAI E2E disabled; set RUN_OPENAI_E2E=1 (or use `make test-openai`).",
)
@pytest.mark.anyio
async def test_openai_models_endpoint_lists_configured_model() -> None:
    base_url = _openai_base_url()
    model = _model_name()
    timeout = httpx.Timeout(10.0, connect=3.0)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        resp = await client.get("/models", headers=_auth_headers())
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    data = payload.get("data")
    assert isinstance(data, list), f"Expected OpenAI-style models list, got: {payload!r}"

    ids: list[str] = []
    for item in data:
        if isinstance(item, dict):
            mid = item.get("id")
            if isinstance(mid, str) and mid.strip():
                ids.append(mid)

    assert ids, "Expected at least one model id in /models response."
    assert model in ids, (
        f"Configured AI_TEXT_MODEL={model!r} not found in /models. "
        f"Available: {ids[:10]!r}. "
        f"For Ollama, run: `ollama pull {model}`"
    )


@pytest.mark.skipif(
    not _should_run(),
    reason="OpenAI E2E disabled; set RUN_OPENAI_E2E=1 (or use `make test-openai`).",
)
@pytest.mark.anyio
async def test_openai_chat_completions_returns_message_content() -> None:
    base_url = _openai_base_url()
    model = _model_name()
    timeout = httpx.Timeout(60.0, connect=3.0)

    request_body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with a short confirmation."}],
        "temperature": 0.0,
        "max_tokens": 32,
        "stream": False,
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        resp = await client.post("/chat/completions", headers=_auth_headers(), json=request_body)
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    choices = payload.get("choices")
    assert isinstance(choices, list) and choices, f"Missing choices in response: {payload!r}"
    first = choices[0]
    assert isinstance(first, dict), f"Unexpected choice shape: {first!r}"
    message = first.get("message")
    assert isinstance(message, dict), f"Expected message object, got: {message!r}"
    content = message.get("content")
    assert isinstance(content, str) and content.strip(), f"Expected non-empty content, got: {content!r}"
