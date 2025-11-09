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

    def run(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        teacher_instructions_md: str | None = None,
        solution_hints_md: str | None = None,
    ) -> str:
        """Execute the configured runner with the provided inputs."""
        import inspect as _inspect
        kwargs = {"text_md": text_md, "criteria": criteria}
        try:
            sig = _inspect.signature(self._runner)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
            if "solution_hints_md" in sig.parameters:
                kwargs["solution_hints_md"] = solution_hints_md
        except Exception:
            pass
        return self._runner(**kwargs)


class FeedbackSynthesisProgram:
    """Wrapper around the feedback-synthesis runner (second DSPy stage)."""

    def __init__(self, *, runner: Callable[..., str]):
        """
        Parameters:
            runner: Callable accepting `text_md`, `criteria`, `analysis_json`
                    and returning Markdown feedback as string.
        """
        self._runner = runner

    def run(
        self,
        *,
        text_md: str,
        criteria: Sequence[str],
        analysis_json: dict[str, Any],
        teacher_instructions_md: str | None = None,
    ) -> str:
        """Execute the configured runner for the synthesis stage."""
        import inspect as _inspect
        kwargs = {"text_md": text_md, "criteria": criteria, "analysis_json": analysis_json}
        try:
            sig = _inspect.signature(self._runner)
            if "teacher_instructions_md" in sig.parameters:
                kwargs["teacher_instructions_md"] = teacher_instructions_md
        except Exception:
            pass
        return self._runner(**kwargs)
