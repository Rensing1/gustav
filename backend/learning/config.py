"""
Learning worker configuration (adapter selection only).

Intent:
    Provide a single place to read environment variables that control
    adapter selection (DI) for the learning worker.

Why:
    The worker must be framework-free and predictable. We keep the config
    surface minimal and delegate model/endpoint wiring to the adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class LearningAdapterConfig:
    vision_adapter_path: str
    feedback_adapter_path: str


def _is_prod_like() -> bool:
    env = (os.getenv("GUSTAV_ENV") or "dev").lower()
    return env in {"prod", "production", "stage", "staging"}


def _looks_like_stub_adapter(module_path: str) -> bool:
    return ".stub_" in (module_path or "")


def load_learning_adapter_config() -> LearningAdapterConfig:
    """
    Parse and validate learning-worker adapter configuration from env vars.

    Behavior:
        - Adapters are selected via explicit module paths:
          `LEARNING_VISION_ADAPTER` and `LEARNING_FEEDBACK_ADAPTER`.
        - Defaults are the DSPy-based local adapters.
        - Production-like environments reject stub adapters (fail-fast).
    """
    default_vision = "backend.learning.adapters.local_vision"
    default_feedback = "backend.learning.adapters.local_feedback"

    vision_adapter = (os.getenv("LEARNING_VISION_ADAPTER") or "").strip() or default_vision
    feedback_adapter = (os.getenv("LEARNING_FEEDBACK_ADAPTER") or "").strip() or default_feedback

    if _is_prod_like():
        if _looks_like_stub_adapter(vision_adapter) or _looks_like_stub_adapter(feedback_adapter):
            raise ValueError("Stub learning adapters are not allowed in production/staging.")

    return LearningAdapterConfig(
        vision_adapter_path=vision_adapter,
        feedback_adapter_path=feedback_adapter,
    )
