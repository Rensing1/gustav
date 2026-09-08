"""Explicit database and storage wiring for student upload intents."""

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.submissions import LearningSubmissionRepoProtocol
from backend.storage.supabase_factory import build_storage_adapter
from backend.teaching.storage import StorageAdapterProtocol


def _storage_factory() -> Callable[[], StorageAdapterProtocol]:
    """Cache successful construction only, independently of legacy route state."""
    return cache(lambda: build_storage_adapter())


@dataclass(frozen=True)
class LearningUploadIntentProviders:
    repository: Callable[[], LearningSubmissionRepoProtocol]
    storage: Callable[[], StorageAdapterProtocol] = field(default_factory=_storage_factory)


def create_learning_upload_intent_providers() -> LearningUploadIntentProviders:
    """Build lazily after request validation; failed construction remains retryable.

    The existing DB adapter owns connections, membership and task visibility.
    The synchronous handler resolves it once and performs both reads in the
    bounded threadpool. Storage is initialized only after authorization and MIME
    validation; failures are not cached and never change another consumer.
    """

    @cache
    def repository() -> LearningSubmissionRepoProtocol:
        return DBLearningRepo()

    return LearningUploadIntentProviders(repository=repository)


def learning_upload_intent_providers(request: Request) -> LearningUploadIntentProviders:
    """Resolve dependencies installed when the GUSTAV backend starts."""
    return cast(LearningUploadIntentProviders, request.app.state.learning_upload_intent_providers)
