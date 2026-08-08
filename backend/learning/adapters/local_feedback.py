"""
Learning feedback adapter (DSPy-only, OpenAI-compatible endpoint).

Intent:
    Provide a minimal adapter for the learning worker that generates:
      - structured rubric analysis (`criteria.v2`) and
      - formative feedback (Markdown)
    via DSPy, configured against an OpenAI-compatible API endpoint.

Design:
    - Fail-fast: no Ollama fallback, no deterministic Python fallback text.
    - Thread-safe: the worker may run jobs concurrently; use `dspy.context(...)`
      (thread-local settings) instead of global `dspy.configure(...)`.

Security:
    - Do not log student text or teacher-only context.
"""

from __future__ import annotations

import base64
from io import BytesIO
import logging
import os
from typing import Sequence

from backend.learning.adapters.dspy import helpers as dspy_helpers
from backend.learning.adapters.dspy.usage import capture_dspy_usage
from backend.learning.adapters.ports import (
    FeedbackInvalidAnalysisError,
    FeedbackPermanentError,
    FeedbackResult,
    FeedbackTransientError,
)

LOG = logging.getLogger(__name__)

_VISUAL_PROVIDER_COMPLEX_PNG_MIN_EDGE = 1280
_VISUAL_PROVIDER_COMPLEX_PNG_MIN_BASE64_CHARS = 300_000
_VISUAL_PROVIDER_RENDITION_MAX_EDGE = 1280
_VISUAL_PROVIDER_RENDITION_MAX_PIXELS = 16_777_216
_VISUAL_PROVIDER_RENDITION_JPEG_QUALITY = 85


def _safe_response_header(exc: Exception, name: str) -> str:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return ""
    try:
        return str(headers.get(name, "") or "")
    except Exception:
        return ""


def _safe_exception_attr(exc: Exception, name: str) -> str:
    """Read a provider exception attribute without risking secondary failures."""
    try:
        return str(getattr(exc, name, "") or "")
    except Exception:
        return ""


def _is_provider_rate_limit_exception(exc: Exception) -> bool:
    """Return true for OpenAI/LiteLLM-style provider rate-limit failures."""
    if exc.__class__.__name__ == "RateLimitError":
        return True
    try:
        return int(getattr(exc, "status_code", 0) or 0) == 429
    except Exception:
        return False


def _raise_feedback_error_for_exception(
    exc: Exception,
    *,
    default_transient_code: str,
    provider_image_diagnostics: dict[str, object] | None = None,
) -> None:
    """Classify adapter exceptions into stable transient/permanent error codes."""
    normalized = str(exc or "").strip().lower()
    usage_events = list(getattr(exc, "usage_events", []) or [])
    if _is_provider_rate_limit_exception(exc):
        if _is_complex_provider_png_diagnostic(provider_image_diagnostics):
            LOG.warning(
                "learning.feedback.visual_image_too_complex_for_provider mime=image/png "
                "width=%s height=%s bytes=%s base64_chars=%s provider=%s model=%s "
                "status_code=%s provider_error_type=%s provider_error_code=%s retry_after=%s request_id=%s",
                provider_image_diagnostics.get("width", "") if provider_image_diagnostics else "",
                provider_image_diagnostics.get("height", "") if provider_image_diagnostics else "",
                provider_image_diagnostics.get("bytes", "") if provider_image_diagnostics else "",
                provider_image_diagnostics.get("base64_chars", "") if provider_image_diagnostics else "",
                _safe_exception_attr(exc, "llm_provider"),
                _safe_exception_attr(exc, "model"),
                _safe_exception_attr(exc, "status_code") or "429",
                _safe_exception_attr(exc, "type"),
                _safe_exception_attr(exc, "code"),
                _safe_response_header(exc, "retry-after"),
                _safe_response_header(exc, "x-request-id"),
            )
            raise FeedbackPermanentError("image_too_complex_for_provider", usage_events=usage_events) from exc
        LOG.warning(
            "learning.feedback.provider_rate_limited provider=%s model=%s status_code=%s "
            "provider_error_type=%s provider_error_code=%s retry_after=%s request_id=%s",
            _safe_exception_attr(exc, "llm_provider"),
            _safe_exception_attr(exc, "model"),
            _safe_exception_attr(exc, "status_code") or "429",
            _safe_exception_attr(exc, "type"),
            _safe_exception_attr(exc, "code"),
            _safe_response_header(exc, "retry-after"),
            _safe_response_header(exc, "x-request-id"),
        )
        raise FeedbackTransientError("provider_rate_limited", usage_events=usage_events) from exc
    if ("invalid_criterion_idx" in normalized) or ("invalid_analysis_json" in normalized):
        raise FeedbackInvalidAnalysisError("feedback_invalid_analysis", usage_events=usage_events) from exc
    if normalized in {"invalid_feedback_format", "empty_feedback_md"}:
        raise FeedbackPermanentError(normalized, usage_events=usage_events) from exc
    raise FeedbackTransientError(default_transient_code, usage_events=usage_events) from exc


def _provider_image_data_uri(
    *,
    mime: str,
    image_b64: str,
) -> str:
    """Return the original data URI sent to the visual provider."""
    return f"data:{mime};base64,{image_b64}"


def _decode_provider_image_b64(image_b64: str) -> bytes:
    try:
        return base64.b64decode(image_b64, validate=True)
    except Exception as exc:
        raise FeedbackPermanentError("invalid_upload_content") from exc


def _provider_safe_jpeg_rendition_b64(*, image_b64: str) -> str:
    """Return a provider-bound JPEG rendition without mutating the stored upload."""
    raw = _decode_provider_image_b64(image_b64)
    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
            pixels = int(width) * int(height)
            if pixels > _VISUAL_PROVIDER_RENDITION_MAX_PIXELS:
                LOG.warning(
                    "learning.feedback.visual_image_rendition_pixel_limit_exceeded "
                    "width=%s height=%s pixels=%s max_pixels=%s bytes=%s base64_chars=%s",
                    width,
                    height,
                    pixels,
                    _VISUAL_PROVIDER_RENDITION_MAX_PIXELS,
                    len(raw),
                    len(image_b64),
                )
                raise FeedbackPermanentError("image_too_complex_for_provider")
            image = ImageOps.exif_transpose(image)
            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in getattr(image, "info", {})
            )
            if has_alpha:
                rgba = image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                background.alpha_composite(rgba)
                image = background.convert("RGB")
            else:
                image = image.convert("RGB")
            image.thumbnail(
                (_VISUAL_PROVIDER_RENDITION_MAX_EDGE, _VISUAL_PROVIDER_RENDITION_MAX_EDGE),
                Image.Resampling.LANCZOS,
            )
            out = BytesIO()
            image.save(
                out,
                format="JPEG",
                quality=_VISUAL_PROVIDER_RENDITION_JPEG_QUALITY,
                optimize=True,
                progressive=False,
            )
    except FeedbackPermanentError:
        raise
    except Exception as exc:
        raise FeedbackPermanentError("provider_image_rendition_failed") from exc
    return base64.b64encode(out.getvalue()).decode("ascii")


def _provider_image_diagnostics(*, mime: str, image_b64: str) -> dict[str, object]:
    """Return PII-free image metadata used only for provider-failure diagnostics."""
    diagnostics: dict[str, object] = {"mime": mime, "base64_chars": len(image_b64)}
    try:
        raw = base64.b64decode(image_b64, validate=True)
        diagnostics["bytes"] = len(raw)
    except Exception:
        return diagnostics

    if mime not in {"image/png", "image/jpeg"}:
        return diagnostics
    try:
        from PIL import Image

        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
            diagnostics["width"] = width
            diagnostics["height"] = height
            diagnostics["pixels"] = width * height
    except Exception as exc:
        LOG.warning(
            "learning.feedback.visual_image_diagnostics_unavailable reason=%s",
            exc.__class__.__name__,
        )
    return diagnostics


def _call_visual_feedback_program(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    instruction_md: str | None,
    teacher_context_md: str | None,
    analysis_lm,
    synthesis_lm,
) -> FeedbackResult:
    from backend.learning.adapters.dspy import visual_feedback_program

    return visual_feedback_program.analyze_visual_feedback(
        image_data_uri=image_data_uri,
        criteria=criteria,
        teacher_instructions_md=instruction_md,
        teacher_context_md=teacher_context_md,
        analysis_lm=analysis_lm,
        synthesis_lm=synthesis_lm,
    )


def _is_complex_provider_png_diagnostic(diagnostics: dict[str, object] | None) -> bool:
    """Return true for screenshot-like PNG payloads that should not be retried."""
    if not diagnostics or diagnostics.get("mime") != "image/png":
        return False
    try:
        width = int(diagnostics.get("width") or 0)
        height = int(diagnostics.get("height") or 0)
    except Exception:
        width = 0
        height = 0
    try:
        base64_chars = int(diagnostics.get("base64_chars") or 0)
    except Exception:
        base64_chars = 0
    return (
        max(width, height) >= _VISUAL_PROVIDER_COMPLEX_PNG_MIN_EDGE
        or base64_chars >= _VISUAL_PROVIDER_COMPLEX_PNG_MIN_BASE64_CHARS
    )


def _require_secure_openai_base_url(base_url: str) -> None:
    """
    Historical security guard (now disabled).

    We intentionally do not block non-HTTPS OpenAI endpoints anymore. Operators
    may route traffic through VPNs (e.g. Tailscale) and accept responsibility
    for transport security at the network layer.
    """
    return


def _parse_float_env(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _parse_optional_str_env(name: str, *, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = str(raw).strip()
    return normalized or default


def _normalize_model_name(raw: str) -> str:
    """Return a DSPy/LiteLLM model string for OpenAI-compatible chat completion."""
    model = (raw or "").strip()
    if not model:
        return ""
    # Allow advanced users to provide an explicit provider prefix.
    if "/" in model:
        return model
    return f"openai/{model}"


class _LocalFeedbackAdapter:
    """DSPy-only Feedback adapter used by the learning worker."""

    def __init__(self) -> None:
        self._base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
        self._api_key = (os.getenv("OPENAI_API_KEY") or "").strip() or "sk-noop"

        self._text_model = _normalize_model_name(os.getenv("AI_TEXT_MODEL") or "")
        self._visual_model = _normalize_model_name(os.getenv("AI_VISUAL_MODEL") or "")
        self._text_analysis_think_level = _parse_optional_str_env(
            "AI_TEXT_ANALYSIS_THINK_LEVEL",
            default=_parse_optional_str_env("AI_TEXT_THINK_LEVEL"),
        )
        self._text_synthesis_think_level = _parse_optional_str_env(
            "AI_TEXT_SYNTHESIS_THINK_LEVEL",
            default=_parse_optional_str_env("AI_TEXT_THINK_LEVEL"),
        )
        self._visual_analysis_think_level = _parse_optional_str_env(
            "AI_VISUAL_ANALYSIS_THINK_LEVEL",
            default=_parse_optional_str_env("AI_VISUAL_THINK_LEVEL"),
        )
        self._visual_synthesis_think_level = _parse_optional_str_env(
            "AI_VISUAL_SYNTHESIS_THINK_LEVEL",
            default=_parse_optional_str_env("AI_VISUAL_THINK_LEVEL"),
        )
        self._text_analysis_reasoning_effort = _parse_optional_str_env(
            "AI_TEXT_ANALYSIS_REASONING_EFFORT",
            default=_parse_optional_str_env("AI_TEXT_REASONING_EFFORT"),
        )
        self._text_synthesis_reasoning_effort = _parse_optional_str_env(
            "AI_TEXT_SYNTHESIS_REASONING_EFFORT",
            default=_parse_optional_str_env("AI_TEXT_REASONING_EFFORT"),
        )
        self._visual_analysis_reasoning_effort = _parse_optional_str_env(
            "AI_VISUAL_ANALYSIS_REASONING_EFFORT",
            default=_parse_optional_str_env("AI_VISUAL_REASONING_EFFORT"),
        )
        self._visual_synthesis_reasoning_effort = _parse_optional_str_env(
            "AI_VISUAL_SYNTHESIS_REASONING_EFFORT",
            default=_parse_optional_str_env("AI_VISUAL_REASONING_EFFORT"),
        )

        self._text_analysis_temperature = _parse_float_env(
            "AI_TEXT_ANALYSIS_TEMPERATURE",
            default=_parse_float_env("AI_TEXT_TEMPERATURE", default=0.0),
        )
        self._text_synthesis_temperature = _parse_float_env(
            "AI_TEXT_SYNTHESIS_TEMPERATURE",
            default=_parse_float_env("AI_TEXT_TEMPERATURE", default=0.0),
        )
        self._visual_analysis_temperature = _parse_float_env(
            "AI_VISUAL_ANALYSIS_TEMPERATURE",
            default=_parse_float_env("AI_VISUAL_TEMPERATURE", default=0.0),
        )
        self._visual_synthesis_temperature = _parse_float_env(
            "AI_VISUAL_SYNTHESIS_TEMPERATURE",
            default=_parse_float_env("AI_VISUAL_TEMPERATURE", default=0.0),
        )

        self._text_analysis_lm = None
        self._text_synthesis_lm = None
        self._visual_analysis_lm = None
        self._visual_synthesis_lm = None

    def _require_common_config(self) -> None:
        if not self._base_url:
            raise FeedbackTransientError("missing_OPENAI_BASE_URL")
        _require_secure_openai_base_url(self._base_url)
        if not self._text_model:
            raise FeedbackTransientError("missing_AI_TEXT_MODEL")

    def _build_lm(  # type: ignore[no-untyped-def]
        self,
        *,
        model: str,
        temperature: float,
        think_level: str | None,
        reasoning_effort: str | None,
        num_retries: int | None = None,
    ):
        self._require_common_config()
        try:
            import dspy  # type: ignore
        except Exception as exc:
            raise FeedbackTransientError("dspy_unavailable") from exc
        lm_kwargs = {
            "temperature": temperature,
            "base_url": self._base_url,
            "api_key": self._api_key,
        }
        # GPT-OSS supports a per-request `think` level; keep other models unchanged.
        maybe_think = dspy_helpers.resolve_think_level(model, think_level)
        if maybe_think:
            lm_kwargs["extra_body"] = {"think": maybe_think}
        maybe_reasoning_effort = dspy_helpers.resolve_reasoning_effort(model, reasoning_effort)
        if maybe_reasoning_effort:
            lm_kwargs["reasoning_effort"] = maybe_reasoning_effort
        if num_retries is not None:
            lm_kwargs["num_retries"] = num_retries
        return dspy.LM(model, **lm_kwargs)  # type: ignore[attr-defined]

    def _get_text_analysis_lm(self):  # type: ignore[no-untyped-def]
        if self._text_analysis_lm is None:
            self._text_analysis_lm = self._build_lm(
                model=self._text_model,
                temperature=self._text_analysis_temperature,
                think_level=self._text_analysis_think_level,
                reasoning_effort=self._text_analysis_reasoning_effort,
            )
        return self._text_analysis_lm

    def _get_text_synthesis_lm(self):  # type: ignore[no-untyped-def]
        if self._text_synthesis_lm is None:
            self._text_synthesis_lm = self._build_lm(
                model=self._text_model,
                temperature=self._text_synthesis_temperature,
                think_level=self._text_synthesis_think_level,
                reasoning_effort=self._text_synthesis_reasoning_effort,
            )
        return self._text_synthesis_lm

    def _get_visual_analysis_lm(self):  # type: ignore[no-untyped-def]
        if self._visual_analysis_lm is not None:
            return self._visual_analysis_lm
        self._require_common_config()
        if not self._visual_model:
            raise FeedbackPermanentError("missing_AI_VISUAL_MODEL")
        self._visual_analysis_lm = self._build_lm(
            model=self._visual_model,
            temperature=self._visual_analysis_temperature,
            think_level=self._visual_analysis_think_level,
            reasoning_effort=self._visual_analysis_reasoning_effort,
            num_retries=0,
        )
        return self._visual_analysis_lm

    def analyze_dialog(
        self,
        *,
        student_performance: dict,
        conversation_context: dict,
        criteria: Sequence[str],
        instruction_md: str,
    ):
        """Assess learner contributions separately from AI conversation context."""

        try:
            from backend.learning.adapters.dspy.dialog_assessment_program import analyze_dialog

            result, usage_events = capture_dspy_usage(
                lambda: analyze_dialog(
                    student_performance=student_performance,
                    conversation_context=conversation_context,
                    criteria=criteria,
                    instruction_md=instruction_md,
                    lm=self._get_text_analysis_lm(),
                ),
                model=self._text_model,
                stage="analysis",
                modality="text",
                call_kind="primary",
            )
            result.usage_events.extend(usage_events)
            return result
        except (FeedbackPermanentError, FeedbackTransientError):
            raise
        except Exception as exc:
            _raise_feedback_error_for_exception(exc, default_transient_code="feedback_failed")

    def _get_visual_synthesis_lm(self):  # type: ignore[no-untyped-def]
        if self._visual_synthesis_lm is not None:
            return self._visual_synthesis_lm
        self._require_common_config()
        if not self._visual_model:
            raise FeedbackPermanentError("missing_AI_VISUAL_MODEL")
        self._visual_synthesis_lm = self._build_lm(
            model=self._visual_model,
            temperature=self._visual_synthesis_temperature,
            think_level=self._visual_synthesis_think_level,
            reasoning_effort=self._visual_synthesis_reasoning_effort,
            num_retries=0,
        )
        return self._visual_synthesis_lm

    def analyze(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        instruction_md: str | None = None,
        teacher_context_md: str | None = None,
    ) -> FeedbackResult:  # type: ignore[override]
        """Generate structured analysis + feedback for a text submission."""
        analysis_lm = self._get_text_analysis_lm()
        synthesis_lm = self._get_text_synthesis_lm()
        try:
            from backend.learning.adapters.dspy import feedback_program
            return feedback_program.analyze_feedback(
                text_md=text_md,
                criteria=criteria,
                teacher_instructions_md=instruction_md,
                teacher_context_md=teacher_context_md,
                analysis_lm=analysis_lm,
                synthesis_lm=synthesis_lm,
            )
        except FeedbackPermanentError:
            raise
        except FeedbackTransientError:
            raise
        except TimeoutError as exc:
            raise FeedbackTransientError("timeout") from exc
        except ImportError as exc:
            raise FeedbackTransientError("dspy_unavailable") from exc
        except Exception as exc:
            _raise_feedback_error_for_exception(exc, default_transient_code="feedback_failed")

    def analyze_visual(  # type: ignore[no-untyped-def]
        self,
        *,
        submission: dict,
        job_payload: dict,
        criteria: Sequence[str],
        instruction_md: str | None = None,
        teacher_context_md: str | None = None,
    ) -> FeedbackResult:
        """Generate structured analysis + feedback for a visual submission (image/PDF)."""
        # Fail fast on missing visual-model configuration before touching storage.
        analysis_lm = self._get_visual_analysis_lm()
        synthesis_lm = self._get_visual_synthesis_lm()

        from backend.learning.adapters.local_vision import (  # type: ignore
            VisionPermanentError,
            VisionTransientError,
            _LocalVisionAdapter,
            _resolve_submission_image_bytes,
            _submissions_bucket,
            get_learning_max_upload_bytes,
        )

        mime = (job_payload or {}).get("mime_type") or (submission or {}).get("mime_type") or ""
        mime = str(mime or "").strip().lower()

        bucket = _submissions_bucket()
        max_download_bytes = get_learning_max_upload_bytes()

        image_data_uri: str | None = None
        image_b64: str | None = None
        provider_image_diagnostics: dict[str, object] | None = None
        try:
            if mime in {"image/jpeg", "image/png"}:
                meta: dict = {}
                image_b64 = _resolve_submission_image_bytes(
                    submission=submission,
                    job_payload=job_payload,
                    bucket=bucket,
                    max_download_bytes=max_download_bytes,
                    meta=meta,
                )
                if not image_b64:
                    raise FeedbackTransientError("image_unavailable")
                provider_image_diagnostics = _provider_image_diagnostics(mime=mime, image_b64=image_b64)
                image_data_uri = _provider_image_data_uri(mime=mime, image_b64=image_b64)
            elif mime == "application/pdf":
                stitched = _LocalVisionAdapter()._ensure_pdf_stitched_png(  # noqa: SLF001
                    submission=submission,
                    job_payload=job_payload,
                )
                if not stitched:
                    raise FeedbackTransientError("pdf_images_unavailable")
                import base64 as _b64

                stitched_b64 = _b64.b64encode(stitched).decode("ascii")
                image_data_uri = f"data:image/png;base64,{stitched_b64}"
            else:
                raise FeedbackPermanentError("unsupported_mime")
        except VisionPermanentError as exc:
            raise FeedbackPermanentError(str(exc)) from exc
        except VisionTransientError as exc:
            raise FeedbackTransientError(str(exc)) from exc

        if not image_data_uri:
            raise FeedbackTransientError("image_unavailable")
        try:
            return _call_visual_feedback_program(
                image_data_uri=image_data_uri,
                criteria=criteria,
                instruction_md=instruction_md,
                teacher_context_md=teacher_context_md,
                analysis_lm=analysis_lm,
                synthesis_lm=synthesis_lm,
            )
        except FeedbackPermanentError:
            raise
        except FeedbackTransientError:
            raise
        except TimeoutError as exc:
            raise FeedbackTransientError("timeout") from exc
        except ImportError as exc:
            raise FeedbackTransientError("dspy_unavailable") from exc
        except Exception as exc:
            if image_b64 and mime in {"image/jpeg", "image/png"} and _is_provider_rate_limit_exception(exc):
                original_usage_events = list(getattr(exc, "usage_events", []) or [])
                try:
                    fallback_b64 = _provider_safe_jpeg_rendition_b64(image_b64=image_b64)
                except FeedbackPermanentError as rendition_exc:
                    raise FeedbackPermanentError(
                        str(rendition_exc),
                        usage_events=[
                            *original_usage_events,
                            *list(getattr(rendition_exc, "usage_events", []) or []),
                        ],
                    ) from rendition_exc
                fallback_uri = _provider_image_data_uri(mime="image/jpeg", image_b64=fallback_b64)
                try:
                    fallback_result = _call_visual_feedback_program(
                        image_data_uri=fallback_uri,
                        criteria=criteria,
                        instruction_md=instruction_md,
                        teacher_context_md=teacher_context_md,
                        analysis_lm=analysis_lm,
                        synthesis_lm=synthesis_lm,
                    )
                    fallback_result.usage_events = [
                        *original_usage_events,
                        *list(getattr(fallback_result, "usage_events", []) or []),
                    ]
                    return fallback_result
                except Exception as fallback_exc:
                    fallback_usage_events = list(getattr(fallback_exc, "usage_events", []) or [])
                    combined_usage_events = [*original_usage_events, *fallback_usage_events]
                    if _is_provider_rate_limit_exception(fallback_exc):
                        fallback_diagnostics = _provider_image_diagnostics(mime="image/jpeg", image_b64=fallback_b64)
                        LOG.warning(
                            "learning.feedback.visual_image_too_complex_for_provider mime=image/jpeg "
                            "width=%s height=%s bytes=%s base64_chars=%s provider=%s model=%s "
                            "status_code=%s provider_error_type=%s provider_error_code=%s retry_after=%s request_id=%s",
                            fallback_diagnostics.get("width", ""),
                            fallback_diagnostics.get("height", ""),
                            fallback_diagnostics.get("bytes", ""),
                            fallback_diagnostics.get("base64_chars", ""),
                            _safe_exception_attr(fallback_exc, "llm_provider"),
                            _safe_exception_attr(fallback_exc, "model"),
                            _safe_exception_attr(fallback_exc, "status_code") or "429",
                            _safe_exception_attr(fallback_exc, "type"),
                            _safe_exception_attr(fallback_exc, "code"),
                            _safe_response_header(fallback_exc, "retry-after"),
                            _safe_response_header(fallback_exc, "x-request-id"),
                        )
                        raise FeedbackPermanentError(
                            "image_too_complex_for_provider",
                            usage_events=combined_usage_events,
                        ) from fallback_exc
                    if combined_usage_events:
                        setattr(fallback_exc, "usage_events", combined_usage_events)
                    _raise_feedback_error_for_exception(
                        fallback_exc,
                        default_transient_code="visual_feedback_failed",
                        provider_image_diagnostics=_provider_image_diagnostics(mime="image/jpeg", image_b64=fallback_b64),
                    )
            _raise_feedback_error_for_exception(
                exc,
                default_transient_code="visual_feedback_failed",
                provider_image_diagnostics=provider_image_diagnostics,
            )


def build() -> _LocalFeedbackAdapter:
    """Factory used by the worker DI to construct the adapter instance."""
    return _LocalFeedbackAdapter()
