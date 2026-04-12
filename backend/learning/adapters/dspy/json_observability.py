"""
Internal helpers to observe DSPy JSONAdapter response-format decisions.

Intent:
    Keep the production path on DSPy's JSONAdapter while exposing whether a
    call used Structured Outputs (`json_schema`) or fell back to `json_object`.

Security:
    Only technical metadata is recorded. No prompt or student content is kept.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_LAST_CALL_METADATA: ContextVar[dict[str, Any] | None] = ContextVar(
    "learning_dspy_last_call_metadata",
    default=None,
)


def clear_last_call_metadata() -> None:
    """Clear stage-local adapter metadata before a DSPy call starts."""
    _LAST_CALL_METADATA.set(None)


def pop_last_call_metadata() -> dict[str, Any] | None:
    """Return and clear the last adapter metadata recorded for the current context."""
    value = _LAST_CALL_METADATA.get()
    _LAST_CALL_METADATA.set(None)
    return value


def _record_call_metadata(
    *,
    stage: str,
    lm: Any,
    lm_kwargs: dict[str, Any],
    response_format_mode: str,
) -> None:
    model = str(getattr(lm, "model", "") or "")
    provider = model.split("/", 1)[0] if "/" in model else ""
    response_format = lm_kwargs.get("response_format")
    if isinstance(response_format, dict):
        response_format_requested = str(response_format.get("type") or "")
    elif response_format is None:
        response_format_requested = ""
    else:
        response_format_requested = getattr(response_format, "__name__", str(type(response_format).__name__))
    _LAST_CALL_METADATA.set(
        {
            "stage": stage,
            "model": model,
            "provider": provider,
            "response_format_mode": response_format_mode,
            "response_format_requested": response_format_requested,
            "reasoning_effort": lm_kwargs.get("reasoning_effort"),
        }
    )


def _get_structured_outputs_response_format(signature, use_native_function_calling: bool = True):  # type: ignore[no-untyped-def]
    """Thin indirection so tests can force the fallback path deterministically."""
    from dspy.adapters.json_adapter import _get_structured_outputs_response_format as _dspy_get

    return _dspy_get(signature, use_native_function_calling)


def build_json_adapter(*, stage: str):  # type: ignore[no-untyped-def]
    """
    Return a JSON adapter that records response-format metadata when possible.

    Tests often monkeypatch `sys.modules["dspy"]` with a light stub. In that
    case we fall back to the stubbed `dspy.JSONAdapter()` to keep unit tests
    deterministic without importing DSPy's internal packages.
    """
    try:
        import litellm
        from dspy.adapters.chat_adapter import ChatAdapter
        from dspy.adapters.json_adapter import (
            JSONAdapter as _DSPYJSONAdapter,
            _has_open_ended_mapping,
        )
        from dspy.adapters.types.tool import ToolCalls
    except Exception:
        import dspy  # type: ignore

        return dspy.JSONAdapter()  # type: ignore[attr-defined]

    class _InstrumentedJSONAdapter(_DSPYJSONAdapter):
        def _json_adapter_call_common(self, lm, lm_kwargs, signature, demos, inputs, call_fn):
            provider = lm.model.split("/", 1)[0] or "openai"
            params = litellm.get_supported_openai_params(model=lm.model, custom_llm_provider=provider)

            if not params or "response_format" not in params:
                _record_call_metadata(
                    stage=stage,
                    lm=lm,
                    lm_kwargs=lm_kwargs,
                    response_format_mode="unsupported_provider",
                )
                return call_fn(lm, lm_kwargs, signature, demos, inputs)

            has_tool_calls = any(field.annotation == ToolCalls for field in signature.output_fields.values())
            if _has_open_ended_mapping(signature) or (not self.use_native_function_calling and has_tool_calls):
                lm_kwargs["response_format"] = {"type": "json_object"}
                _record_call_metadata(
                    stage=stage,
                    lm=lm,
                    lm_kwargs=lm_kwargs,
                    response_format_mode="json_object_forced",
                )
                return call_fn(lm, lm_kwargs, signature, demos, inputs)

            return None

        def __call__(self, lm, lm_kwargs, signature, demos, inputs):
            result = self._json_adapter_call_common(lm, lm_kwargs, signature, demos, inputs, ChatAdapter.__call__)
            if result is not None:
                return result

            try:
                structured_output_model = _get_structured_outputs_response_format(
                    signature, self.use_native_function_calling
                )
                lm_kwargs["response_format"] = structured_output_model
                _record_call_metadata(
                    stage=stage,
                    lm=lm,
                    lm_kwargs=lm_kwargs,
                    response_format_mode="json_schema",
                )
                return ChatAdapter.__call__(self, lm, lm_kwargs, signature, demos, inputs)
            except Exception:
                lm_kwargs["response_format"] = {"type": "json_object"}
                _record_call_metadata(
                    stage=stage,
                    lm=lm,
                    lm_kwargs=lm_kwargs,
                    response_format_mode="json_object_fallback",
                )
                return ChatAdapter.__call__(self, lm, lm_kwargs, signature, demos, inputs)

        async def acall(self, lm, lm_kwargs, signature, demos, inputs):
            result = self._json_adapter_call_common(lm, lm_kwargs, signature, demos, inputs, ChatAdapter.acall)
            if result is not None:
                return await result

            try:
                structured_output_model = _get_structured_outputs_response_format(
                    signature, self.use_native_function_calling
                )
                lm_kwargs["response_format"] = structured_output_model
                _record_call_metadata(
                    stage=stage,
                    lm=lm,
                    lm_kwargs=lm_kwargs,
                    response_format_mode="json_schema",
                )
                return await ChatAdapter.acall(self, lm, lm_kwargs, signature, demos, inputs)
            except Exception:
                lm_kwargs["response_format"] = {"type": "json_object"}
                _record_call_metadata(
                    stage=stage,
                    lm=lm,
                    lm_kwargs=lm_kwargs,
                    response_format_mode="json_object_fallback",
                )
                return await ChatAdapter.acall(self, lm, lm_kwargs, signature, demos, inputs)

    return _InstrumentedJSONAdapter()


__all__ = [
    "build_json_adapter",
    "clear_last_call_metadata",
    "pop_last_call_metadata",
]
