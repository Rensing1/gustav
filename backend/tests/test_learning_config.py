from __future__ import annotations

import pytest

from backend.learning.config import load_learning_adapter_config


def test_load_ai_config_defaults(monkeypatch):
    monkeypatch.delenv("LEARNING_VISION_ADAPTER", raising=False)
    monkeypatch.delenv("LEARNING_FEEDBACK_ADAPTER", raising=False)

    cfg = load_learning_adapter_config()
    assert cfg.vision_adapter_path.endswith("local_vision")
    assert cfg.feedback_adapter_path.endswith("local_feedback")


def test_load_learning_adapter_config_overrides(monkeypatch):
    monkeypatch.setenv("LEARNING_VISION_ADAPTER", "backend.learning.adapters.stub_vision")
    monkeypatch.setenv("LEARNING_FEEDBACK_ADAPTER", "backend.learning.adapters.stub_feedback")

    cfg = load_learning_adapter_config()
    assert cfg.vision_adapter_path.endswith("stub_vision")
    assert cfg.feedback_adapter_path.endswith("stub_feedback")


def test_prod_like_disallows_stub_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUSTAV_ENV", "prod")
    monkeypatch.setenv("LEARNING_VISION_ADAPTER", "backend.learning.adapters.stub_vision")
    with pytest.raises(ValueError):
        load_learning_adapter_config()
