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
    predict = dspy.Predict(VisionOcrSignature)  # type: ignore[attr-defined]
    out = predict(student_image=img)
    val = getattr(out, "text_md", None)
    if isinstance(val, str) and val.strip() and val.strip().lower() != "none":
        return val.strip(), {"backend": "dspy", "program": "vision_ocr"}
    raise RuntimeError("empty_ocr_text_md")
