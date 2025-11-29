"""
Helpers for configuring DSPy/Ollama LMs with GPT-OSS think levels.

Why:
    GPT-OSS requires an explicit `think` level (`low|medium|high`). Without
    it, the model emits long reasoning traces by default. These helpers
    centralise the conditional wiring so both worker bootstrap and DSPy
    programs stay consistent.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_ALLOWED_THINK_LEVELS = {"low", "medium", "high"}


def normalize_think_level(raw: str | None) -> str:
    """Return a safe think level defaulting to 'low'."""
    level = (raw or "low").strip().lower()
    return level if level in _ALLOWED_THINK_LEVELS else "low"


def resolve_think_level(model_name: str, think_level: str | None) -> str | None:
    """Only return a think level for GPT-OSS models."""
    if not model_name.lower().startswith("gpt-oss"):
        return None
    return normalize_think_level(think_level)


def build_lm_kwargs(
    *,
    model_name: str,
    api_base: Optional[str],
    think_level: str | None,
) -> Dict[str, Any]:
    """
    Construct kwargs for dspy.LM, adding `extra_body` with think-level for GPT-OSS.
    """
    kwargs: Dict[str, Any] = {}
    if api_base:
        kwargs["api_base"] = api_base

    maybe_think = resolve_think_level(model_name, think_level)
    if maybe_think:
        kwargs["extra_body"] = {"think": maybe_think}
    return kwargs
