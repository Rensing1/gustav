"""
Helpers for configuring DSPy LMs with GPT-OSS think levels.

Why:
    GPT-OSS requires an explicit `think` level (`low|medium|high`). Without it,
    the model may emit long reasoning traces by default.

    We keep the logic in one place so the learning adapters can apply the same
    conservative rule: only GPT-OSS gets a think-level; other models are left
    unchanged for compatibility with stricter OpenAI-compatible endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_ALLOWED_THINK_LEVELS = {"low", "medium", "high"}

def _model_leaf(model_name: str) -> str:
    """
    Return the provider-stripped model name.

    Why:
        Our adapters normalize models to strings like "openai/<name>". GPT-OSS
        detection must therefore work on the leaf ("gpt-oss:...") rather than
        the full provider-prefixed string.
    """
    raw = (model_name or "").strip()
    if "/" not in raw:
        return raw
    return raw.rsplit("/", 1)[-1]


def normalize_think_level(raw: str | None) -> str:
    """Return a safe think level defaulting to 'low'."""
    level = (raw or "low").strip().lower()
    return level if level in _ALLOWED_THINK_LEVELS else "low"


def resolve_think_level(model_name: str, think_level: str | None) -> str | None:
    """Only return a think level for GPT-OSS models."""
    leaf = _model_leaf(model_name).lower()
    if not leaf.startswith("gpt-oss"):
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
