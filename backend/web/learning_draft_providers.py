"""Explicit database wiring for the student's private task drafts."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.task_drafts import TaskDraftRepository


@dataclass(frozen=True)
class LearningDraftProviders:
    repository: Callable[[], TaskDraftRepository]


def create_learning_draft_providers() -> LearningDraftProviders:
    """Build on the first authorized request; failed initialization is retryable.

    The adapter owns connections and student/course scoping for each access check.
    Construction and queries run in the synchronous handler's bounded threadpool.
    """

    @cache
    def repository() -> TaskDraftRepository:
        return DBLearningRepo()

    return LearningDraftProviders(repository=repository)


def learning_draft_providers(request: Request) -> LearningDraftProviders:
    """Resolve the dependencies installed when the GUSTAV backend starts."""
    return cast(LearningDraftProviders, request.app.state.learning_draft_providers)
