"""TDD: Vision-Adapter — minimale Integration für gerenderte Seiten.

We validate that a Vision adapter is invoked once per page, the extracted
markdown text is concatenated with page headings, and the repo is marked
as completed with the provided text and analysis metadata.
"""
from __future__ import annotations

from typing import List


class _FakeVisionClient:
    def __init__(self) -> None:
        self.calls: List[bytes] = []

    def analyze_image(self, *, image_bytes: bytes) -> str:
        self.calls.append(image_bytes)
        # Return a tiny stub text per page
        return f"Text({len(image_bytes)})"


class _FakeRepo:
    def __init__(self) -> None:
        self.completed: tuple[str, str, dict, str] | None = None

    def mark_completed(self, *, submission_id: str, text_md: str, analysis_json: dict, feedback_md: str) -> None:
        self.completed = (submission_id, text_md, analysis_json, feedback_md)


def _mk_page(b: bytes):
    class _P:
        def __init__(self, data: bytes) -> None:
            self.png_bytes = data
            self.width = 10
            self.height = 20

    return _P(b)


def test_vision_extracts_text_and_marks_completed():
    from backend.vision.vision_adapter import extract_text_from_pages, VisionClient, CompletionRepo

    client: VisionClient = _FakeVisionClient()  # type: ignore[assignment]
    pages = [_mk_page(b"A"), _mk_page(b"BC")]

    result = extract_text_from_pages(pages=pages, client=client)
    # Client called once per page with the exact bytes
    assert len(client.calls) == 2  # type: ignore[attr-defined]
    assert client.calls[0] == b"A" and client.calls[1] == b"BC"  # type: ignore[index]

    # Text contains page headings and concatenated payloads
    assert "## Page 1" in result.text_md
    assert "Text(1)" in result.text_md
    assert "## Page 2" in result.text_md
    assert "Text(2)" in result.text_md
    # Analysis metadata records page count and model hint
    assert result.analysis_json.get("pages") == 2
    assert result.analysis_json.get("source") == "vision.ollama"

    # Mark completion via the repo port
    repo: CompletionRepo = _FakeRepo()  # type: ignore[assignment]
    repo.mark_completed(
        submission_id="00000000-0000-0000-0000-000000000001",
        text_md=result.text_md,
        analysis_json=result.analysis_json,
        feedback_md="",
    )
    assert repo.completed is not None
    sid, text_md, analysis_json, feedback_md = repo.completed  # type: ignore[assignment]
    assert sid.endswith("1")
    assert "Page 1" in text_md and "Page 2" in text_md
    assert analysis_json.get("pages") == 2
    assert feedback_md == ""
