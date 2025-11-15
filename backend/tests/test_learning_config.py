from __future__ import annotations

import os

import pytest

from backend.learning.config import load_ai_config


def test_load_ai_config_defaults(monkeypatch):
    monkeypatch.delenv("AI_BACKEND", raising=False)
    monkeypatch.delenv("LEARNING_VISION_ADAPTER", raising=False)
    monkeypatch.delenv("LEARNING_FEEDBACK_ADAPTER", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    cfg = load_ai_config()
    assert cfg.backend == "stub"
    assert cfg.vision_adapter_path.endswith("stub_vision")
    assert cfg.feedback_adapter_path.endswith("stub_feedback")
    assert cfg.timeout_vision_seconds == 30
    assert cfg.timeout_feedback_seconds == 15
    assert cfg.ollama_base_url.startswith("http://")


def test_load_ai_config_local_overrides(monkeypatch):
    monkeypatch.setenv("AI_BACKEND", "local")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_TIMEOUT_VISION", "45")
    monkeypatch.setenv("AI_TIMEOUT_FEEDBACK", "20")

    cfg = load_ai_config()
    assert cfg.backend == "local"
    assert cfg.vision_adapter_path.endswith("local_vision")
    assert cfg.feedback_adapter_path.endswith("local_feedback")
    assert cfg.timeout_vision_seconds == 45
    assert cfg.timeout_feedback_seconds == 20


@pytest.mark.parametrize("name", ["AI_TIMEOUT_VISION", "AI_TIMEOUT_FEEDBACK"])
def test_load_ai_config_invalid_timeout(monkeypatch, name):
    monkeypatch.setenv("AI_BACKEND", "stub")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv(name, "not-an-int")
    with pytest.raises(ValueError):
        load_ai_config()


def test_load_ai_config_invalid_backend(monkeypatch):
    monkeypatch.setenv("AI_BACKEND", "cloud")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    with pytest.raises(ValueError):
        load_ai_config()


def test_load_ai_config_ollama_url_validation(monkeypatch):
    monkeypatch.setenv("AI_BACKEND", "stub")
    # Disallow obviously external hosts
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example.com:11434")
    with pytest.raises(ValueError):
        load_ai_config()

