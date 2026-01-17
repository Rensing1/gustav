"""
Unit tests for GPT-OSS think-level helpers.

Intent:
    - Only GPT-OSS models should receive a think level.
    - Detection must work with provider-prefixed model names (e.g. "openai/...").
    - Missing/invalid values must default to "low" for GPT-OSS.

Safety:
    Non-GPT-OSS models must never receive a think level, even if an env value
    is provided by accident.
"""

from __future__ import annotations

from backend.learning.adapters.dspy import helpers as dspy_helpers


def test_resolve_think_level_defaults_to_low_for_gpt_oss_leaf() -> None:
    assert dspy_helpers.resolve_think_level("openai/gpt-oss:120b", None) == "low"
    assert dspy_helpers.resolve_think_level("openai/gpt-oss:120b", "") == "low"


def test_resolve_think_level_normalizes_and_sanitizes_for_gpt_oss() -> None:
    assert dspy_helpers.resolve_think_level("openai/gpt-oss:120b", "HIGH") == "high"
    assert dspy_helpers.resolve_think_level("openai/gpt-oss:120b", "banana") == "low"


def test_resolve_think_level_skips_non_gpt_oss_even_when_value_provided() -> None:
    assert dspy_helpers.resolve_think_level("openai/llama3.1", "high") is None
