"""Explicit database wiring for released section lists and material links."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.sections import LearningRepoProtocol


@dataclass(frozen=True)
class LearningSectionProviders:
    repository: Callable[[], LearningRepoProtocol]


def create_learning_section_providers() -> LearningSectionProviders:
    """Build lazily in the authorized handler; failed initialization is retryable.

    Operations own their DB connections and student/course scope. Section reads
    and their material visibility enrichment share the explicitly supplied adapter.
    """

    @cache
    def repository() -> LearningRepoProtocol:
        return DBLearningRepo()

    return LearningSectionProviders(repository=repository)


def learning_section_providers(request: Request) -> LearningSectionProviders:
    """Resolve dependencies installed during this backend's construction."""
    return cast(LearningSectionProviders, request.app.state.learning_section_providers)
