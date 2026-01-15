"""
DSPy vision program (OCR/text extraction).

Intent:
    Provide a callable that the local Vision adapter may use when `dspy` is
    importable, returning extracted Markdown text and lightweight metadata.

Design:
    - DSPy-only: uses `dspy.Predict(Signature)`; LM wiring happens via `dspy.context(...)`.
    - Fail-fast: no deterministic fallback text is generated in Python.
    - No clipping: the caller enforces the 65_536 char limit.
"""

from __future__ import annotations

from backend.learning.adapters.dspy.signatures import VisionOcrSignature


def _resolve_vision_signature(*, dspy_module) -> type:
    """Return a Vision signature compatible with the currently imported `dspy`.

    Why:
        Some unit tests temporarily inject a minimal fake `dspy` module into
        `sys.modules`. If `backend.learning.adapters.dspy.signatures` is imported
        under that fake, `VisionOcrSignature` may not be a real DSPy Signature.
        Later (integration) tests then import the real DSPy and expect
        `dspy.Predict(...)` to work with a proper Signature type.

        To avoid cross-test pollution, we rebuild the Signature on demand when
        the active DSPy provides the modern Signature API.
    """
    try:
        signature_base = getattr(dspy_module, "Signature")
    except Exception:
        return VisionOcrSignature

    wants_signature_fields = hasattr(signature_base, "input_fields")
    has_signature_fields = hasattr(VisionOcrSignature, "input_fields")
    if not wants_signature_fields or has_signature_fields:
        return VisionOcrSignature

    class _VisionOcrSignature(signature_base):  # type: ignore[misc, valid-type]
        student_image = dspy_module.InputField(  # type: ignore[attr-defined]
            desc="Student submission image (data-URI or URL via dspy.Image)."
        )
        text_md = dspy_module.OutputField(  # type: ignore[attr-defined]
            desc="Extracted text as Markdown (no extra commentary)."
        )

    return _VisionOcrSignature


def extract_text_from_image(*, image_data_uri: str) -> tuple[str, dict]:
    """Extract Markdown text from an image via DSPy.

    Parameters:
        image_data_uri: Data-URI (or URL) pointing to the visual submission.

    Returns:
        `(text_md, meta)` where `meta` contains a stable `program` marker.

    Raises:
        ImportError: when DSPy is not available.
        RuntimeError: when the model does not produce a usable `text_md` output.
    """
    try:  # pragma: no cover - exercised via unit tests with stubbed dspy module
        import dspy  # type: ignore

        _ = getattr(dspy, "__version__", None)
    except Exception:
        raise ImportError("dspy is not available")

    img = dspy.Image(url=str(image_data_uri))  # type: ignore[attr-defined]
    signature = _resolve_vision_signature(dspy_module=dspy)
    predict = dspy.Predict(signature)  # type: ignore[attr-defined]
    out = predict(student_image=img)
    val = getattr(out, "text_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val.strip(), {"backend": "dspy", "program": "vision_ocr"}
    raise RuntimeError("empty_ocr_text_md")
