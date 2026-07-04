"""Task-service provider for Teaching route adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.teaching.services.tasks import TasksService


_repo_provider: Callable[[], Any] | None = None


def configure_task_service_repo_provider(provider: Callable[[], Any]) -> None:
    """Install the repository provider used to construct task services.

    Why:
        Split Teaching route modules need task operations without importing the
        large `teaching.py` router. The app composition still owns repository
        selection; this small provider keeps that boundary explicit.
    """

    global _repo_provider
    _repo_provider = provider


def _get_tasks_service() -> TasksService:
    """Return a task service bound to the active Teaching repository."""

    if _repo_provider is None:
        raise RuntimeError("teaching_task_service_repo_provider_not_configured")
    return TasksService(_repo_provider())
