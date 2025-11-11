"""
AI configuration parsing and validation for the learning worker.

Intent:
    Provide a single place to read environment variables that control
    adapter selection (DI), model names, timeouts and the local Ollama URL.

Why:
    Centralising configuration reduces drift across modules and makes
    validation and defaults explicit (KISS). It also helps tests exercise
    config behaviour without booting the worker process.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class AIConfig:
    backend: str  # "stub" | "local"
    vision_adapter_path: str
    feedback_adapter_path: str
    vision_model: str
    feedback_model: str
    timeout_vision_seconds: int
    timeout_feedback_seconds: int
    ollama_base_url: str


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got: {raw!r}")
    if value <= 0 or value > 300:
        raise ValueError(f"{name} out of range (1..300), got: {value}")
    return value


def _validate_ollama_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("OLLAMA_BASE_URL must start with http:// or https://")
    host = (parsed.hostname or "").lower()
    # Allow typical local-only forms (service name in compose, localhost, loopback)
    if not (host == "localhost" or host.startswith("127.") or host.startswith("::1") or host.isalpha()):
        # host.isalpha() allows service names like "ollama" in docker compose networks
        raise ValueError("OLLAMA_BASE_URL must point to localhost/service network host")


def _is_prod_like() -> bool:
    env = (os.getenv("GUSTAV_ENV") or "dev").lower()
    return env in {"prod", "production", "stage", "staging"}


def load_ai_config() -> AIConfig:
    """
    Parse and validate AI-related configuration from environment variables.

    Behavior:
        - `AI_BACKEND` selects DI alias: "stub" or "local" (default: stub).
        - If explicit `LEARNING_*_ADAPTER` are set, they take precedence.
        - Validates timeouts (1..300 seconds) and Ollama base URL shape.
    """
    backend = (os.getenv("AI_BACKEND") or "stub").strip().lower()
    if backend not in {"stub", "local"}:
        raise ValueError("AI_BACKEND must be 'stub' or 'local'")
    if backend == "stub" and _is_prod_like():
        raise ValueError("AI_BACKEND=stub is not allowed in production/staging environments.")

    # Adapter module paths (DI)
    default_vision = (
        "backend.learning.adapters.local_vision" if backend == "local" else "backend.learning.adapters.stub_vision"
    )
    default_feedback = (
        "backend.learning.adapters.local_feedback"
        if backend == "local"
        else "backend.learning.adapters.stub_feedback"
    )
    vision_adapter = os.getenv("LEARNING_VISION_ADAPTER", default_vision)
    feedback_adapter = os.getenv("LEARNING_FEEDBACK_ADAPTER", default_feedback)

    # Models and timeouts
    vision_model = os.getenv("AI_VISION_MODEL", "qwen2.5-vl:7b")
    feedback_model = os.getenv("AI_FEEDBACK_MODEL", "qwen2.5:7b-instruct")
    timeout_vision = _int_env("AI_TIMEOUT_VISION", 30)
    timeout_feedback = _int_env("AI_TIMEOUT_FEEDBACK", 15)

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    _validate_ollama_url(ollama_url)

    return AIConfig(
        backend=backend,
        vision_adapter_path=vision_adapter,
        feedback_adapter_path=feedback_adapter,
        vision_model=vision_model,
        feedback_model=feedback_model,
        timeout_vision_seconds=timeout_vision,
        timeout_feedback_seconds=timeout_feedback,
        ollama_base_url=ollama_url,
    )
