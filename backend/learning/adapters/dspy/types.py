"""Data transfer objects that represent structured feedback analysis results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass
class CriterionResult:
    """Represents one criterion's score/evidence returned by DSPy."""

    criterion: str
    max_score: int
    score: int
    explanation_md: str

    @classmethod
    def from_value(cls, value: Any) -> "CriterionResult":
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(
                criterion=str(value.get("criterion", "")),
                max_score=int(value.get("max_score", 10)),
                score=int(value.get("score", 0)),
                explanation_md=str(value.get("explanation_md", value.get("explanation", ""))) or "",
            )
        if hasattr(value, "__dict__"):
            return cls.from_value(vars(value))
        raise ValueError("Unsupported criterion result value")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LeanCriterionResult:
    """Lean structured criterion result emitted by the model."""

    criterion_idx: int
    score: int
    explanation_md: str

    @classmethod
    def from_value(cls, value: Any) -> "LeanCriterionResult":
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            if "criterion_idx" not in value:
                raise ValueError("invalid_criterion_idx")
            try:
                criterion_idx = int(value.get("criterion_idx"))
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid_criterion_idx") from exc
            try:
                score = int(value.get("score", 0))
            except (TypeError, ValueError):
                score = 0
            explanation_md = str(value.get("explanation_md", value.get("explanation", ""))) or ""
            return cls(criterion_idx=criterion_idx, score=score, explanation_md=explanation_md)
        if hasattr(value, "__dict__"):
            return cls.from_value(vars(value))
        raise ValueError("invalid_criterion_idx")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CriteriaAnalysis:
    """Flat mapping of a `criteria.v2` analysis payload."""

    schema: str
    score: int
    criteria_results: list[CriterionResult]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriteriaAnalysis":
        return cls(
            schema=str(data.get("schema", "criteria.v2")),
            score=int(data.get("score", 0)),
            criteria_results=[CriterionResult.from_value(item) for item in data.get("criteria_results", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "score": self.score,
            "criteria_results": [item.to_dict() for item in self.criteria_results],
        }
