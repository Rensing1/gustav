"""Explicit database wiring for the student's H5P access check."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.h5p_access import LearningRepoProtocol


@dataclass(frozen=True)
class LearningH5PProviders:
    repository: Callable[[], LearningRepoProtocol]


def create_learning_h5p_providers() -> LearningH5PProviders:
    """Build on the first authorized request; failed initialization is retryable.

    The adapter owns connections and student/course scoping for each access check.
    Construction and queries run in the synchronous handler's bounded threadpool.
    """

    @cache
    def repository() -> LearningRepoProtocol:
        return DBLearningRepo()

    return LearningH5PProviders(repository=repository)


def learning_h5p_providers(request: Request) -> LearningH5PProviders:
    """Resolve the dependencies installed when the GUSTAV backend starts."""
    return cast(LearningH5PProviders, request.app.state.learning_h5p_providers)
