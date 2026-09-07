"""Explicit database wiring for the student's modular graph."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.unit_graph import LearningGraphRepository


@dataclass(frozen=True)
class LearningGraphProviders:
    repository: Callable[[], LearningGraphRepository]


def create_learning_graph_providers() -> LearningGraphProviders:
    """Initialize lazily in the authorized handler; failed construction is retryable.

    Repository operations own connections and RLS identity context. Tests can
    replace this dependency without mutating shared Learning route globals.
    """

    @cache
    def repository() -> LearningGraphRepository:
        return DBLearningRepo()

    return LearningGraphProviders(repository=repository)


def learning_graph_providers(request: Request) -> LearningGraphProviders:
    """Resolve the dependencies supplied during backend construction."""
    return cast(LearningGraphProviders, request.app.state.learning_graph_providers)
