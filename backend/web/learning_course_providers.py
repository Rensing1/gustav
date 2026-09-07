"""Explicit database wiring for the learner's course overview."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.courses import CoursesRepoProtocol


@dataclass(frozen=True)
class LearningCourseProviders:
    repository: Callable[[], CoursesRepoProtocol]


def create_learning_course_providers() -> LearningCourseProviders:
    """Defer repository construction until an authorized read in the threadpool.

    The application owns this accessor; tests can supply a repository without
    mutating shared route globals. Failed construction remains retryable.
    Connections and membership context stay local to repository operations.
    """

    @cache
    def repository() -> CoursesRepoProtocol:
        return DBLearningRepo()

    return LearningCourseProviders(repository=repository)


def learning_course_providers(request: Request) -> LearningCourseProviders:
    """Use the dependencies supplied when constructing this backend application."""
    return cast(LearningCourseProviders, request.app.state.learning_course_providers)
