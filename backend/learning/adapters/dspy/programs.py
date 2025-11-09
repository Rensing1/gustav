"""
DSPy program scaffolding for feedback analysis.

Intent:
    Provide a tiny abstraction that mirrors how DSPy modules would expose
    their structured output while remaining dependency-light for tests.
    By funnelling raw model execution through this helper we keep the
    `feedback_program` module focused on parsing and normalization logic.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence


class FeedbackAnalysisProgram:
    """Lightweight runner facade for the feedback analysis prompt."""

    def __init__(self, *, runner: Callable[..., str]):
        """
        Parameters:
            runner: Callable accepting `text_md` and `criteria` and returning
                    the raw (JSON) model response as string.
        """
        self._runner = runner

    def run(self, *, text_md: str, criteria: Sequence[str]) -> str:
        """Execute the configured runner with the provided inputs."""
        return self._runner(text_md=text_md, criteria=criteria)


class FeedbackSynthesisProgram:
    """Wrapper around the feedback-synthesis runner (second DSPy stage)."""

    def __init__(self, *, runner: Callable[..., str]):
        """
        Parameters:
            runner: Callable accepting `text_md`, `criteria`, `analysis_json`
                    and returning Markdown feedback as string.
        """
        self._runner = runner

    def run(self, *, text_md: str, criteria: Sequence[str], analysis_json: dict[str, Any]) -> str:
        """Execute the configured runner for the synthesis stage."""
        return self._runner(text_md=text_md, criteria=criteria, analysis_json=analysis_json)
