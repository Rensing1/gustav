"""
Helpers for configuring model-specific DSPy reasoning controls.

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
_ALLOWED_REASONING_EFFORTS = {"none", "high"}
_MISTRAL_LARGE_4_MODELS = {"mistral-large-4", "mistral-large-4-0"}
_MISTRAL_LARGE_4_EFFORTS = {"low", "medium", "high"}

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


def normalize_reasoning_effort(raw: str | None) -> str:
    """Return a safe Magistral reasoning effort defaulting to 'none'."""
    effort = (raw or "none").strip().lower()
    return effort if effort in _ALLOWED_REASONING_EFFORTS else "none"


def resolve_reasoning_effort(model_name: str, reasoning_effort: str | None) -> str | None:
    """Apply each supported model family's own reasoning vocabulary.

    Large 4 has no ``none`` mode. Reject explicit invalid values instead of
    silently requesting a different reasoning budget; omitted values use low.
    Keep the existing Magistral normalization and unrelated models unchanged.
    """
    leaf = _model_leaf(model_name).lower()
    if leaf in _MISTRAL_LARGE_4_MODELS:
        effort = (reasoning_effort or "").strip().lower() or "low"
        if effort not in _MISTRAL_LARGE_4_EFFORTS:
            raise ValueError("Mistral Large 4 reasoning_effort must be low, medium or high")
        return effort
    if not leaf.startswith("magistral"):
        return None
    return normalize_reasoning_effort(reasoning_effort)


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


def build_reasoning_kwargs(model_name: str, reasoning_effort: str | None) -> Dict[str, Any]:
    """Forward supported reasoning even when LiteLLM's model catalog lags.

    Scope the explicit parameter allowance to Large 4. Never globally drop
    unsupported parameters: that would silently lose the requested budget.
    """
    effort = resolve_reasoning_effort(model_name, reasoning_effort)
    if effort is None:
        return {}
    kwargs: Dict[str, Any] = {"reasoning_effort": effort}
    if _model_leaf(model_name).lower() in _MISTRAL_LARGE_4_MODELS:
        kwargs["allowed_openai_params"] = ["reasoning_effort"]
    return kwargs


def normalize_large4_transport(model_name: str) -> str:
    """Use LiteLLM's Mistral parser for Large 4's thinking/text chunk lists.

    The generic OpenAI parser only accepts string content. Keep the supplied
    endpoint/key and all unrelated models or explicit alternative providers.
    """
    leaf = _model_leaf(model_name).lower()
    prefix = model_name.rsplit("/", 1)[0] if "/" in model_name else ""
    if leaf in _MISTRAL_LARGE_4_MODELS and prefix in {"", "openai", "mistral"}:
        return f"mistral/{leaf}"
    return model_name
