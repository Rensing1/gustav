"""
Pytest: Optional vision test verifying `images` flow with local Ollama.

Why:
    Complement the connectivity test by exercising a tiny image call using the
    `images=[<b64>]` parameter, gated behind `RUN_OLLAMA_VISION_E2E=1`.

How to run locally:
    export RUN_OLLAMA_E2E=1
    export RUN_OLLAMA_VISION_E2E=1
    export OLLAMA_BASE_URL=http://localhost:11434   # or http://ollama:11434 inside Compose
    export AI_VISION_MODEL=qwen2.5vl:3b             # or your preferred pulled vision model
    docker compose exec ollama ollama pull "$AI_VISION_MODEL"
    pytest -q -m ollama_integration -k vision
"""

from __future__ import annotations

import os
import urllib.parse
import pytest


ALLOWED_HOSTS = {"localhost", "127.0.0.1", "ollama"}

from pathlib import Path
import base64

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_IMAGE_PATH = REPO_ROOT / "backend" / "tests" / "ex_submission.jpg"


def _should_run_vision() -> str | None:
    if os.getenv("RUN_OLLAMA_E2E") != "1":
        return "Set RUN_OLLAMA_E2E=1 to enable Ollama integration tests"
    if os.getenv("RUN_OLLAMA_VISION_E2E") != "1":
        return "Set RUN_OLLAMA_VISION_E2E=1 to enable vision image test"
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return f"OLLAMA_BASE_URL must point to a local host (got: {host!r})"
    model = os.getenv("AI_VISION_MODEL", "qwen2.5vl:3b").strip()
    if not model:
        return (
            "AI_VISION_MODEL is not set. Example:\n"
            "  export AI_VISION_MODEL=qwen2.5vl:3b\n"
            "  docker compose exec ollama ollama pull $AI_VISION_MODEL"
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
def test_ollama_vision_generate_with_images_param():
    skip_reason = _should_run_vision()
    if skip_reason:
        pytest.skip(skip_reason)

    import ollama  # type: ignore

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    model = os.getenv("AI_VISION_MODEL", "qwen2.5vl:3b").strip()

    try:
        client = ollama.Client(base_url)
        # Load the real test image and base64-encode it for the vision call
        data = TEST_IMAGE_PATH.read_bytes()
        img_b64 = base64.b64encode(data).decode("ascii")
        res = client.generate(
            model=model,
            prompt="Please describe this image briefly.",
            images=[img_b64],
            options={"timeout": 15},
        )
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
        pytest.skip(f"Ollama generate (vision) failed: {exc}")

    # Accept dict or object with `.response` for client compatibility
    text = ""
    if isinstance(res, dict):
        text = str(res.get("response", "")).strip()
    else:
        text = str(getattr(res, "response", "")).strip()
    assert text, "Expected non-empty 'response' for vision generate"
