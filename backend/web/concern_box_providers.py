"""Explicit per-app concern-box wiring, with no route facade dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

from fastapi import Request

from backend.identity_access.student_names import resolve_student_names
from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.teaching.repo_db import DBTeachingRepo
from backend.teaching.services.concern_box import ConcernBoxRepository


@dataclass(frozen=True)
class ConcernBoxProviders:
    repository: Callable[[], ConcernBoxRepository]
    resolve_names: Callable[[list[str]], dict[str, str]]


def create_concern_box_providers() -> ConcernBoxProviders:
    """Own a lazy repository per app; failed initialization remains retryable.

    Repository construction can verify database-role membership. Defer that
    work to an authorized synchronous handler, which runs in the threadpool.
    No connection or mutable user context is shared between requests.
    """

    @cache
    def repository() -> ConcernBoxRepository:
        try:
            return DBTeachingRepo()
        except Exception as exc:
            raise TeachingRepositoryUnavailable() from exc

    return ConcernBoxProviders(repository=repository, resolve_names=resolve_student_names)


def concern_box_providers(request: Request) -> ConcernBoxProviders:
    """Resolve only the serving app's dependencies; missing wiring fails closed."""
    return cast(ConcernBoxProviders, request.app.state.concern_box_providers)
