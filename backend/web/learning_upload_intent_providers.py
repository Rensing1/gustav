"""Explicit database wiring for authorizing student upload intents."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.submissions import LearningSubmissionRepoProtocol


@dataclass(frozen=True)
class LearningUploadIntentProviders:
    repository: Callable[[], LearningSubmissionRepoProtocol]


def create_learning_upload_intent_providers() -> LearningUploadIntentProviders:
    """Build lazily after request validation; failed construction remains retryable.

    The existing DB adapter owns connections, membership and task visibility.
    The synchronous handler resolves it once and performs both reads in the
    bounded threadpool. Shared storage wiring is intentionally separate.
    """

    @cache
    def repository() -> LearningSubmissionRepoProtocol:
        return DBLearningRepo()

    return LearningUploadIntentProviders(repository=repository)


def learning_upload_intent_providers(request: Request) -> LearningUploadIntentProviders:
    """Resolve dependencies installed when the GUSTAV backend starts."""
    return cast(LearningUploadIntentProviders, request.app.state.learning_upload_intent_providers)
