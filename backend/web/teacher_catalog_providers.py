"""Explicit per-app teacher catalog wiring, with no route facade dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.teaching.repo_db import DBTeachingRepo
from backend.teaching.services.unit_catalog import UnitCatalogRepository


@dataclass(frozen=True)
class TeacherCatalogProviders:
    repository: Callable[[], UnitCatalogRepository]


def create_teacher_catalog_providers() -> TeacherCatalogProviders:
    """Own a lazy repository per app; failed initialization remains retryable.

    Repository construction can verify database-role membership. Defer that
    work to an authorized synchronous handler, which runs in the threadpool.
    No connection or mutable user context is shared between requests.
    """

    @cache
    def repository() -> UnitCatalogRepository:
        try:
            return DBTeachingRepo()
        except Exception as exc:
            raise TeachingRepositoryUnavailable() from exc

    return TeacherCatalogProviders(repository=repository)


def teacher_catalog_providers(request: Request) -> TeacherCatalogProviders:
    """Resolve only the serving app's dependencies; missing wiring fails closed."""
    return cast(TeacherCatalogProviders, request.app.state.teacher_catalog_providers)
