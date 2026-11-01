"""Large 4 configuration and actual DSPy/LiteLLM HTTP wire contract.

Only synthetic responses and HTTP mocks are used; no provider is contacted.
"""

import importlib.util
import json
import sys

import httpx
import pytest

from backend.learning.adapters import local_dialog, local_feedback
from backend.learning.adapters.dspy import helpers


@pytest.mark.parametrize(
    "model", ["mistral-large-4", "openai/mistral-large-4", "mistral/mistral-large-4-0"]
)
@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, "low"),
        ("", "low"),
        ("  ", "low"),
        (" LOW ", "low"),
        ("medium", "medium"),
        ("HIGH", "high"),
    ],
)
def test_large4_reasoning_values(model, raw, expected):
    assert helpers.resolve_reasoning_effort(model, raw) == expected


@pytest.mark.parametrize("raw", ["none", "off", "minimal", "xhigh", "max", "invalid"])
def test_large4_rejects_invalid_explicit_reasoning(raw):
    with pytest.raises(ValueError, match="must be low, medium or high"):
        helpers.resolve_reasoning_effort("openai/mistral-large-4", raw)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    for modality in ("TEXT", "VISUAL"):
        monkeypatch.setenv(f"AI_{modality}_MODEL", "mistral-large-4")
        monkeypatch.setenv(f"AI_{modality}_REASONING_EFFORT", "low")
        monkeypatch.setenv(f"AI_{modality}_ANALYSIS_REASONING_EFFORT", "high")
        monkeypatch.setenv(f"AI_{modality}_SYNTHESIS_REASONING_EFFORT", "low")
    monkeypatch.setenv("AI_OCR_MODEL", "mistral-small-latest")


@pytest.mark.parametrize(
    "stage,effort",
    [
        ("text_analysis", "high"),
        ("text_synthesis", "low"),
        ("visual_analysis", "high"),
        ("visual_synthesis", "low"),
        ("dialog", "low"),
    ],
)
@pytest.mark.parametrize("chunked", [False, True])
def test_actual_http_reasoning_and_answer_only(monkeypatch, configured, stage, effort, chunked):
    seen = []

    def send(client, request, **kwargs):
        assert str(request.url) == "https://provider.example/v1/chat/completions"
        seen.append(json.loads(request.content))
        content = "Synthetic answer"
        if chunked:
            content = [
                {
                    "type": "thinking",
                    "thinking": [{"type": "text", "text": "Private synthetic reasoning"}],
                },
                {"type": "text", "text": "Synthetic answer"},
            ]
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "synthetic-completion",
                "object": "chat.completion",
                "created": 1,
                "model": "mistral-large-4",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            },
        )

    monkeypatch.setattr(httpx.Client, "send", send)
    if stage == "dialog":
        lm = local_dialog.LocalDialogGenerator()._get_lm()
    else:
        adapter = local_feedback._LocalFeedbackAdapter()
        lm = getattr(adapter, f"_get_{stage}_lm")()
    result = lm(messages=[{"role": "user", "content": "Synthetic input"}], cache=False)
    if chunked:
        assert result[0]["text"] == "Synthetic answer"
        assert result[0]["reasoning_content"] == "Private synthetic reasoning"
    else:
        assert result == ["Synthetic answer"]
    assert len(seen) == 1
    assert seen[0]["model"] == "mistral-large-4"
    assert seen[0]["reasoning_effort"] == effort
    assert "think" not in seen[0]
    assert seen[0]["messages"] == [{"role": "user", "content": "Synthetic input"}]


def test_dialog_assessment_uses_high_analysis_lm(monkeypatch, configured):
    from backend.learning.adapters.dspy import dialog_assessment_program
    from backend.learning.adapters.ports import FeedbackResult

    captured = []

    def analyze(**kwargs):
        captured.append(kwargs["lm"].kwargs["reasoning_effort"])
        return FeedbackResult(feedback_md="Synthetic feedback", analysis_json={})

    monkeypatch.setattr(dialog_assessment_program, "analyze_dialog", analyze)
    monkeypatch.setattr(
        local_feedback, "capture_dspy_usage", lambda operation, **kwargs: (operation(), [])
    )
    local_feedback._LocalFeedbackAdapter().analyze_dialog(
        student_performance={},
        conversation_context={},
        criteria=[],
        instruction_md="Synthetic task",
    )
    assert captured == ["high"]


def test_ocr_model_and_reasoning_are_unchanged(configured):
    from backend.learning.adapters import local_vision

    lm = local_vision.build()._get_ocr_lm()
    assert lm.model == "openai/mistral-small-latest"
    assert "reasoning_effort" not in lm.kwargs


@pytest.mark.parametrize(
    "model,expected",
    [
        ("mistral-large-4", "mistral/mistral-large-4"),
        ("openai/mistral-large-4-0", "mistral/mistral-large-4-0"),
        ("mistral/mistral-large-4", "mistral/mistral-large-4"),
        ("other/mistral-large-4", "other/mistral-large-4"),
        ("openai/mistral-small-latest", "openai/mistral-small-latest"),
        ("openai/mistral-large-4-unrelated", "openai/mistral-large-4-unrelated"),
    ],
)
def test_transport_routing_is_narrow(model, expected):
    assert helpers.normalize_large4_transport(model) == expected


def test_full_text_feedback_keeps_thinking_out_of_result(monkeypatch, configured):
    # Older adapter tests import these modules with deliberately minimal DSPy
    # stubs. Load fresh real signatures without leaking module reloads to them.
    from backend.learning.adapters.dspy import feedback_program, signatures

    spec = importlib.util.spec_from_file_location("_wire_signatures", signatures.__file__)
    real_signatures = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, real_signatures)
    spec.loader.exec_module(real_signatures)
    for name in ("FeedbackAnalysisSignature", "FeedbackSynthesisSignature"):
        monkeypatch.setattr(feedback_program.dspy_programs, name, getattr(real_signatures, name))
    seen = []

    def send(client, request, **kwargs):
        body = json.loads(request.content)
        seen.append(body)
        answer = (
            {"criteria_results": [{"score": 8, "explanation_md": "Synthetic evidence"}]}
            if body["reasoning_effort"] == "high"
            else {"feedback_md": "Synthetic feedback"}
        )
        return httpx.Response(
            200,
            request=request,
            json={
                "id": f"synthetic-{len(seen)}",
                "object": "chat.completion",
                "created": 1,
                "model": "mistral-large-4",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": [
                                        {"type": "text", "text": "Private synthetic reasoning"}
                                    ],
                                },
                                {"type": "text", "text": json.dumps(answer)},
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            },
        )

    monkeypatch.setattr(httpx.Client, "send", send)
    result = local_feedback.build().analyze(
        text_md="Synthetic answer", criteria=["Synthetic criterion"]
    )
    assert [request["reasoning_effort"] for request in seen] == ["high", "low"]
    assert result.feedback_md == "Synthetic feedback"
    assert result.analysis_json["criteria_results"][0]["score"] == 8
    assert "Private synthetic reasoning" not in repr(result)
    assert len(result.usage_events) == 2
    assert all(event.total_tokens == 20 for event in result.usage_events)


def test_provider_failure_remains_failure(monkeypatch, configured):
    from dspy.utils.exceptions import LMError

    seen = []

    def send(client, request, **kwargs):
        seen.append(request)
        return httpx.Response(
            503, request=request, json={"error": {"message": "Synthetic unavailable"}}
        )

    monkeypatch.setattr(httpx.Client, "send", send)
    generator = local_dialog.LocalDialogGenerator()
    with pytest.raises(LMError):
        generator._get_lm()("Synthetic failure input", cache=False)
    assert len(seen) == 1
