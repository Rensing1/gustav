"""Explicit dialog wiring; mutable generator usage state stays request-local."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.dialogs import DialogGeneratorProtocol, DialogUseCases


def build_dialog_generator() -> DialogGeneratorProtocol:
    """Construct the existing generator lazily without changing its AI configuration."""
    from backend.learning.adapters.local_dialog import build

    return build()


@dataclass(frozen=True)
class LearningDialogProviders:
    usecases: Callable[[], DialogUseCases]


def create_learning_dialog_providers() -> LearningDialogProviders:
    """Reuse the connection-free repository, never the generator's usage buffer.

    The synchronous HTTP handlers resolve this factory only after authorization
    and execute the existing use cases in FastAPI's bounded threadpool. Repository
    construction failures remain retryable; transaction ownership stays in the
    existing database adapter, outside model calls.
    """
    repository = cache(DBLearningRepo)

    def usecases() -> DialogUseCases:
        return DialogUseCases(repository(), build_dialog_generator())

    return LearningDialogProviders(usecases=usecases)


def learning_dialog_providers(request: Request) -> LearningDialogProviders:
    """Resolve only the dependencies installed when this backend starts."""
    return cast(LearningDialogProviders, request.app.state.learning_dialog_providers)
