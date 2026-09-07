"""Explicit database wiring for the teacher's graph workspace."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.teaching.repo_db import DBTeachingRepo
from backend.teaching.services.unit_workspace import UnitWorkspaceRepository


@dataclass(frozen=True)
class TeacherWorkspaceProviders:
    repository: Callable[[], UnitWorkspaceRepository]


def create_teacher_workspace_providers() -> TeacherWorkspaceProviders:
    """Construct lazily in the authorized handler's threadpool; failures are retryable.

    Repository operations own their connections and RLS identity context. Tests
    inject dependencies directly without replacing shared route globals.
    """

    @cache
    def repository() -> UnitWorkspaceRepository:
        try:
            return DBTeachingRepo()
        except Exception as exc:
            raise TeachingRepositoryUnavailable() from exc

    return TeacherWorkspaceProviders(repository=repository)


def teacher_workspace_providers(request: Request) -> TeacherWorkspaceProviders:
    """Resolve the dependencies installed during backend construction."""
    return cast(TeacherWorkspaceProviders, request.app.state.teacher_workspace_providers)
