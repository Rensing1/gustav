"""Explicit per-app teacher editor wiring, with no route facade dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.teaching.repo_db import DBTeachingRepo
from backend.teaching.services.node_editor import NodeEditorRepository


@dataclass(frozen=True)
class TeacherEditorProviders:
    repository: Callable[[], NodeEditorRepository]


def create_teacher_editor_providers() -> TeacherEditorProviders:
    """Own a lazy repository per app; failed initialization remains retryable.

    Repository construction can verify database-role membership. Defer that
    work to an authorized synchronous handler, which runs in the threadpool.
    No connection or mutable user context is shared between requests.
    """

    @cache
    def repository() -> NodeEditorRepository:
        try:
            return DBTeachingRepo()
        except Exception as exc:
            raise TeachingRepositoryUnavailable() from exc

    return TeacherEditorProviders(repository=repository)


def teacher_editor_providers(request: Request) -> TeacherEditorProviders:
    """Resolve only the serving app's dependencies; missing wiring fails closed."""
    return cast(TeacherEditorProviders, request.app.state.teacher_editor_providers)
