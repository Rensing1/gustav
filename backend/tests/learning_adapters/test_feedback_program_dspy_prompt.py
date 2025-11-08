import importlib
from typing import List

import pytest


@pytest.mark.anyio
def test_dspy_feedback_program_builds_prompt_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure dspy is importable (fake module)
    class _FakeDSPy:
        __version__ = "0.1-test"

    monkeypatch.setitem(__import__("sys").modules, "dspy", _FakeDSPy())

    mod = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    captured_prompts: List[str] = []

    def fake_lm_call(*, prompt: str, timeout: int) -> str:
        captured_prompts.append(prompt)
        # Return a slightly messy JSON the parser must normalize to v2
        return (
            '{"score": "4.0", "criteria": ['
            '{"name": "Inhalt", "max": 10, "score": 11, "explanation": "gut"},'
            '{"name": "Darstellung", "max": 5, "score": -1, "explanation": "ok"}'
            ']}'
        )

    monkeypatch.setattr(mod, "_lm_call", fake_lm_call)

    text_md = "# Lösung\nText"  # not asserted to avoid leaking
    criteria = ["Inhalt", "Darstellung"]

    feedback_md, analysis = mod.analyze_feedback(text_md=text_md, criteria=criteria)

    # Prompt assertions: includes criteria names and privacy/output hints
    assert captured_prompts, "Expected _lm_call to be invoked"
    p = captured_prompts[0]
    assert "Inhalt" in p and "Darstellung" in p
    assert "Do not include student text" in p
    assert "criteria.v2" in p and "JSON" in p

    # Normalization assertions
    assert analysis["schema"] == "criteria.v2"
    assert 0 <= int(analysis["score"]) <= 5
    items = analysis["criteria_results"]
    assert isinstance(items, list) and len(items) == 2
    # Scores must be clamped into valid ranges per criterion
    inhalt = next(i for i in items if i["criterion"] == "Inhalt")
    darst = next(i for i in items if i["criterion"] == "Darstellung")
    assert 0 <= inhalt["score"] <= inhalt["max_score"]
    assert 0 <= darst["score"] <= darst["max_score"]


@pytest.mark.anyio
def test_dspy_feedback_program_whitespace_response_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeDSPy:
        __version__ = "0.1-test"

    monkeypatch.setitem(__import__("sys").modules, "dspy", _FakeDSPy())

    mod = importlib.import_module("backend.learning.adapters.dspy.feedback_program")

    def fake_lm_call(*, prompt: str, timeout: int) -> str:
        return "   \n\n  "  # whitespace only → unparsable

    monkeypatch.setattr(mod, "_lm_call", fake_lm_call)

    feedback_md, analysis = mod.analyze_feedback(text_md="# t", criteria=["X"])
    assert analysis["schema"] == "criteria.v2"
    assert analysis["criteria_results"] and analysis["criteria_results"][0]["criterion"] == "X"
    assert 0 <= int(analysis["score"]) <= 5


@pytest.mark.anyio
def test_dspy_feedback_program_binds_real_ollama_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the DSPy program instantiates the Ollama client with env config."""

    class _FakeDSPy:
        __version__ = "0.1-test"

    monkeypatch.setitem(__import__("sys").modules, "dspy", _FakeDSPy())

    captured_calls: List[dict] = []

    class _FakeOllamaClient:
        def __init__(self, base_url=None):
            self.base_url = base_url

        def generate(self, *, model: str, prompt: str, options: dict | None = None) -> str:
            captured_calls.append(
                {
                    "base_url": self.base_url,
                    "model": model,
                    "prompt": prompt,
                    "options": options or {},
                }
            )
            return '{"schema":"criteria.v2","score":3,"criteria_results":[]}'

    fake_ollama = type("OllamaModule", (), {"Client": _FakeOllamaClient})
    monkeypatch.setitem(__import__("sys").modules, "ollama", fake_ollama)

    base_url = "http://ollama:11434"
    model_name = "llama3:feedback"
    monkeypatch.setenv("OLLAMA_BASE_URL", base_url)
    monkeypatch.setenv("AI_FEEDBACK_MODEL", model_name)

    mod = importlib.import_module("backend.learning.adapters.dspy.feedback_program")
    mod = importlib.reload(mod)

    feedback_md, analysis = mod.analyze_feedback(text_md="# Lösung", criteria=["Inhalt"])

    assert feedback_md
    assert analysis["schema"] == "criteria.v2"

    assert captured_calls, "Expected DSPy program to call ollama.Client.generate"
    call = captured_calls[0]
    assert call["base_url"] == base_url
    assert call["model"] == model_name
    assert "Inhalt" in call["prompt"]
