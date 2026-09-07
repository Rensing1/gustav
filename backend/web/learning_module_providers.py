"""Explicit database wiring for student module contents and material visibility."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.learning.repo_db import DBLearningRepo
from backend.learning.usecases.module_content import LearningModuleRepository


@dataclass(frozen=True)
class LearningModuleProviders:
    repository: Callable[[], LearningModuleRepository]


def create_learning_module_providers() -> LearningModuleProviders:
    """Construct lazily in the authorized handler; failed construction is retryable.

    Operations own their connections and student/course scope. Content and
    material visibility use this same adapter, without shared route overrides.
    """

    @cache
    def repository() -> LearningModuleRepository:
        return DBLearningRepo()

    return LearningModuleProviders(repository=repository)


def learning_module_providers(request: Request) -> LearningModuleProviders:
    """Resolve dependencies installed during backend construction."""
    return cast(LearningModuleProviders, request.app.state.learning_module_providers)
