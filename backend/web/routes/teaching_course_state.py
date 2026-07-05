"""Small shared state for Teaching course routes.

Why:
    Course deletion and course-member listing share one short-lived marker so a
    freshly deleted course can be reported consistently while route modules are
    being split apart.

Responsibility:
    Keep only course-level route state that is independent from FastAPI,
    repository implementations and response serialization.
"""

from __future__ import annotations

import time


RECENTLY_DELETED_TTL_SECONDS = 15.0
_RECENTLY_DELETED_BY: dict[str, dict[str, float]] = {}


def teacher_id_of(course: object) -> str | None:
    """Return the teacher_id from a Course represented as a dataclass or dict."""

    if isinstance(course, dict):
        return course.get("teacher_id")
    try:
        return getattr(course, "teacher_id", None)
    except Exception:
        return None


def prune_recently_deleted(owner_id: str, *, now: float | None = None) -> None:
    bucket = _RECENTLY_DELETED_BY.get(owner_id)
    if not bucket:
        return
    current = now if now is not None else time.time()
    expired = [cid for cid, ts in bucket.items() if current - ts > RECENTLY_DELETED_TTL_SECONDS]
    for cid in expired:
        bucket.pop(cid, None)
    if not bucket:
        _RECENTLY_DELETED_BY.pop(owner_id, None)


def mark_recently_deleted(owner_id: str, course_id: str) -> None:
    now = time.time()
    bucket = _RECENTLY_DELETED_BY.setdefault(owner_id, {})
    bucket[course_id] = now
    prune_recently_deleted(owner_id, now=now)


def was_recently_deleted(owner_id: str, course_id: str) -> bool:
    prune_recently_deleted(owner_id)
    bucket = _RECENTLY_DELETED_BY.get(owner_id)
    return bool(bucket and course_id in bucket)
