"""Concern-box use cases and privacy-safe view models, independent of HTTP."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class ConcernBoxRepository(Protocol):
    """Owner-/membership-scoped persistence; implementations enforce RLS."""

    def list_courses_for_student(
        self, *, student_id: str, limit: int, offset: int
    ) -> list[dict]: ...
    def student_has_course(self, course_id: str, student_sub: str) -> bool: ...
    def create_concern_box_entry(
        self, *, course_id: str, student_sub: str, message_text: str, anonymous: bool
    ) -> dict | None: ...
    def list_concern_box_entries_for_teacher(self, owner_sub: str, scope: str) -> list[dict]: ...
    def archive_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool: ...
    def restore_concern_box_entry_owned(self, entry_id: str, owner_sub: str) -> bool: ...


class ConcernBoxService:
    """Work on the authenticated caller's courses, never expose anonymous subjects."""

    def __init__(
        self, repository: ConcernBoxRepository, resolve_names: Callable[[list[str]], dict[str, str]]
    ):
        self.repository = repository
        self.resolve_names = resolve_names

    def courses(self, student_sub: str, limit: int, offset: int) -> list[dict[str, str]]:
        """Project the enrolled student's selectable courses without internal fields."""
        return [
            {"id": str(item.get("id") or ""), "title": str(item.get("title") or "")}
            for item in (
                self.repository.list_courses_for_student(
                    student_id=student_sub, limit=limit, offset=offset
                )
                or []
            )
            if str(item.get("id") or "")
        ]

    def create(
        self, course_id: str, student_sub: str, message_text: str, anonymous: bool
    ) -> dict | None:
        """Create a member's hint; the repository rechecks membership atomically.

        The HTTP adapter must supply the authenticated learner's subject. None
        denies a missing/revoked membership; invalid text raises ValueError.
        """
        if not self.repository.student_has_course(course_id, student_sub):
            return None
        return self.repository.create_concern_box_entry(
            course_id=course_id,
            student_sub=student_sub,
            message_text=message_text,
            anonymous=anonymous,
        )

    def inbox(self, owner_sub: str, scope: str) -> dict[str, object]:
        """Read only the teacher's inbox; resolve names once for non-anonymous hints.

        The owner subject comes from authentication. Anonymous subjects must
        reach neither the directory nor the public response projection.
        """
        active_scope = "archived" if scope == "archived" else "open"
        entries = self.repository.list_concern_box_entries_for_teacher(owner_sub, active_scope)
        visible_subs = sorted(
            {
                str(item.get("student_sub") or "")
                for item in entries
                if isinstance(item, dict)
                and not bool(item.get("anonymous"))
                and str(item.get("student_sub") or "")
            }
        )
        names = self.resolve_names(visible_subs) if visible_subs else {}
        return {
            "scopes": [
                {"id": "open", "label": "Offen", "active": active_scope == "open"},
                {"id": "archived", "label": "Archiv", "active": active_scope == "archived"},
            ],
            "active_scope": active_scope,
            "entries": [
                {
                    "id": str(item.get("id") or ""),
                    "course_id": str(item.get("course_id") or ""),
                    "course_title": str(item.get("course_title") or ""),
                    "message_text": str(item.get("message_text") or ""),
                    "anonymous": bool(item.get("anonymous")),
                    "student_name": None
                    if bool(item.get("anonymous"))
                    else names.get(str(item.get("student_sub") or ""), "Unbekannt"),
                    "created_at": str(item.get("created_at") or ""),
                    "archived_at": item.get("archived_at"),
                }
                for item in entries
                if isinstance(item, dict)
            ],
        }
