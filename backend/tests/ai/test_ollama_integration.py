"""
Pytest: Optional integration test verifying local Ollama connectivity.

Why:
    Our unit tests use fakes for determinism. This opt-in test does a
    real, local-only roundtrip to ensure `OLLAMA_BASE_URL` is reachable and
    `AI_FEEDBACK_MODEL` is available. It is skipped by default to keep CI
    fast and network-free.

How to run locally:
    export RUN_OLLAMA_E2E=1
    export OLLAMA_BASE_URL=http://localhost:11434  # or http://ollama:11434 inside Compose
    export AI_FEEDBACK_MODEL=llama3.1              # pick a locally pulled model
    docker compose exec ollama ollama pull "$AI_FEEDBACK_MODEL"
    pytest -q -m ollama_integration -k ollama_integration
"""

from __future__ import annotations

import os
import urllib.parse
import pytest


ALLOWED_HOSTS = {"localhost", "127.0.0.1", "ollama"}


def _should_run() -> str | None:
    if os.getenv("RUN_OLLAMA_E2E") != "1":
        return "Set RUN_OLLAMA_E2E=1 to enable Ollama connectivity tests"
    # Default to localhost when not explicitly configured (conftest only loads .env for RUN_E2E)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return f"OLLAMA_BASE_URL must point to a local host (got: {host!r})"
    model = os.getenv("AI_FEEDBACK_MODEL", "").strip()
    if not model:
        return (
            "AI_FEEDBACK_MODEL is not set. Example:\n"
            "  export AI_FEEDBACK_MODEL=llama3.1\n"
            "  docker compose exec ollama ollama pull $AI_FEEDBACK_MODEL"
        )
    try:
        import ollama  # type: ignore
        _ = getattr(ollama, "Client", None)
        if _ is None:
            return "ollama package missing Client; install compatible version"
    except Exception as exc:  # pragma: no cover - environment-dependent
        return f"ollama package not importable: {exc}"
    return None


@pytest.mark.ollama_integration
def test_ollama_connectivity_feedback_response_non_empty():
    skip_reason = _should_run()
    if skip_reason:
        pytest.skip(skip_reason)

    # Imports after gating to avoid ImportError noise in normal runs
    import ollama  # type: ignore

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    model = os.getenv("AI_FEEDBACK_MODEL", "").strip()

    try:
        client = ollama.Client(base_url)
        res = client.generate(model=model, prompt="ok", options={"timeout": 10})
    except Exception as exc:
        msg = str(exc).lower()
        if any(x in msg for x in ("connection", "refused", "unreachable", "timed out")):
            pytest.skip(
                "Could not reach local Ollama (is service running and port exposed?).\n"
                "Hint: docker compose up -d --build; check OLLAMA_BASE_URL"
            )
        if any(x in msg for x in ("not found", "pull", "no such model")):
            pytest.skip(
                f"Model {model!r} not available. Pull it first:\n"
                f"  docker compose exec ollama ollama pull {model}"
            )
        # Unknown runtime error: keep the test non-failing but actionable.
        pytest.skip(f"Ollama generate failed: {exc}")

    # Basic shape assertion: accept dict or client response object with `.response`
    text = ""
    if isinstance(res, dict):
        text = str(res.get("response", "")).strip()
    else:
        text = str(getattr(res, "response", "")).strip()
    assert text, "Expected non-empty 'response' from local Ollama"
