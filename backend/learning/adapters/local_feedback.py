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
from typing import Any, Sequence

from backend.learning.adapters.dspy import helpers as dspy_helpers
from backend.learning.adapters.ports import (
    FeedbackInvalidAnalysisError,
    FeedbackPermanentError,
    FeedbackResult,
    FeedbackTransientError,
)

LOG = logging.getLogger(__name__)

_VISUAL_PROVIDER_IMAGE_MAX_EDGE = 1280
_VISUAL_PROVIDER_IMAGE_MAX_PIXELS = 16_000_000
_VISUAL_PROVIDER_STITCHED_PDF_MAX_PIXELS = 64_000_000
_VISUAL_PROVIDER_IMAGE_JPEG_QUALITY = 85
_VISUAL_PROVIDER_PNG_NORMALIZE_MIN_BASE64_CHARS = 300_000


def _safe_response_header(exc: Exception, name: str) -> str:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return ""
    try:
        return str(headers.get(name, "") or "")
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


def _raise_feedback_error_for_exception(exc: Exception, *, default_transient_code: str) -> None:
    """Classify adapter exceptions into stable transient/permanent error codes."""
    normalized = str(exc or "").strip().lower()
    usage_events = list(getattr(exc, "usage_events", []) or [])
    if _is_provider_rate_limit_exception(exc):
        LOG.warning(
            "learning.feedback.provider_rate_limited provider=%s model=%s status_code=%s retry_after=%s request_id=%s",
            str(getattr(exc, "llm_provider", "") or ""),
            str(getattr(exc, "model", "") or ""),
            str(getattr(exc, "status_code", "429") or "429"),
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
    max_pixels: int = _VISUAL_PROVIDER_IMAGE_MAX_PIXELS,
) -> str:
    """Return the data URI sent to the visual provider, normalizing large PNGs."""
    normalized_mime, normalized_b64 = _normalize_png_for_provider(
        mime=mime,
        image_b64=image_b64,
        max_pixels=max_pixels,
    )
    return f"data:{normalized_mime};base64,{normalized_b64}"


def _png_as_rgb_on_white(image: Any) -> Any:
    """Return an RGB image, preserving transparent drawings on a white canvas."""
    has_alpha = getattr(image, "mode", "") in {"RGBA", "LA"} or "transparency" in getattr(image, "info", {})
    if not has_alpha:
        return image.convert("RGB")

    from PIL import Image

    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    white.alpha_composite(rgba)
    return white.convert("RGB")


def _normalize_png_for_provider(
    *,
    mime: str,
    image_b64: str,
    max_pixels: int = _VISUAL_PROVIDER_IMAGE_MAX_PIXELS,
) -> tuple[str, str]:
    """
    Convert large PNG screenshots to JPEG before provider submission.

    Why:
        The original file remains unchanged in storage. Only the provider-bound
        representation is normalized to avoid oversized PNG data URIs that can
        trigger provider-side admission/rate-limit behavior.
    """
    if mime != "image/png":
        return mime, image_b64

    try:
        from PIL import Image
    except Exception as exc:
        LOG.warning(
            "learning.feedback.visual_image_normalization_skipped reason=%s",
            exc.__class__.__name__,
        )
        return mime, image_b64

    try:
        raw = base64.b64decode(image_b64, validate=True)

        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
            pixel_count = width * height
            if pixel_count > max_pixels:
                LOG.warning(
                    "learning.feedback.visual_image_rejected reason=input_too_large mime=image/png "
                    "width=%s height=%s pixels=%s max_pixels=%s bytes=%s",
                    width,
                    height,
                    pixel_count,
                    max_pixels,
                    len(raw),
                )
                raise FeedbackPermanentError("input_too_large")

            should_normalize = (
                max(width, height) > _VISUAL_PROVIDER_IMAGE_MAX_EDGE
                or len(image_b64) >= _VISUAL_PROVIDER_PNG_NORMALIZE_MIN_BASE64_CHARS
            )
            if not should_normalize:
                return mime, image_b64

            normalized = _png_as_rgb_on_white(image)
            normalized.thumbnail(
                (_VISUAL_PROVIDER_IMAGE_MAX_EDGE, _VISUAL_PROVIDER_IMAGE_MAX_EDGE),
                Image.Resampling.LANCZOS,
            )
            out = BytesIO()
            normalized.save(
                out,
                format="JPEG",
                quality=_VISUAL_PROVIDER_IMAGE_JPEG_QUALITY,
                optimize=True,
            )
            normalized_bytes = out.getvalue()
            LOG.info(
                "learning.feedback.visual_image_normalized original_mime=image/png original_bytes=%s "
                "original_width=%s original_height=%s normalized_mime=image/jpeg normalized_bytes=%s "
                "normalized_width=%s normalized_height=%s",
                len(raw),
                width,
                height,
                len(normalized_bytes),
                normalized.width,
                normalized.height,
            )
            return "image/jpeg", base64.b64encode(normalized_bytes).decode("ascii")
    except FeedbackPermanentError:
        raise
    except Image.DecompressionBombError as exc:
        raise FeedbackPermanentError("input_too_large") from exc
    except Image.DecompressionBombWarning as exc:
        raise FeedbackPermanentError("input_too_large") from exc
    except Exception as exc:
        LOG.warning(
            "learning.feedback.visual_image_normalization_skipped reason=%s",
            exc.__class__.__name__,
        )
        return mime, image_b64


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
        )
        return self._visual_analysis_lm

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
                image_data_uri = _provider_image_data_uri(
                    mime="image/png",
                    image_b64=stitched_b64,
                    max_pixels=_VISUAL_PROVIDER_STITCHED_PDF_MAX_PIXELS,
                )
            else:
                raise FeedbackPermanentError("unsupported_mime")
        except VisionPermanentError as exc:
            raise FeedbackPermanentError(str(exc)) from exc
        except VisionTransientError as exc:
            raise FeedbackTransientError(str(exc)) from exc

        if not image_data_uri:
            raise FeedbackTransientError("image_unavailable")
        try:
            from backend.learning.adapters.dspy import visual_feedback_program
            return visual_feedback_program.analyze_visual_feedback(
                image_data_uri=image_data_uri,
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
            _raise_feedback_error_for_exception(exc, default_transient_code="visual_feedback_failed")


def build() -> _LocalFeedbackAdapter:
    """Factory used by the worker DI to construct the adapter instance."""
    return _LocalFeedbackAdapter()
