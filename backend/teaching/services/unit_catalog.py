"""Shared teacher catalog and home rules without HTTP or route dependencies."""

from __future__ import annotations

from typing import Protocol


class UnitCatalogRepository(Protocol):
    """Read only courses/units owned by the supplied authenticated subject."""

    def list_courses_for_teacher(
        self, *, teacher_id: str, limit: int, offset: int
    ) -> list[dict]: ...
    def list_catalog_course_refs(self, *, owner_sub: str, course_ids: list[str]) -> list[dict]: ...
    def list_units_for_author(self, *, author_id: str, limit: int, offset: int) -> list[dict]: ...
    def list_catalog_section_summaries(self, *, owner_sub: str, unit_ids: list[str]) -> dict[str, dict]: ...


class UnitCatalogService:
    def __init__(self, repository: UnitCatalogRepository):
        self.repository = repository

    def courses(self, owner_sub: str) -> list[dict[str, str]]:
        """Project only id/title from the teacher's bounded course list."""
        return [
            {"id": str(item.get("id") or ""), "title": str(item.get("title") or "")}
            for item in (
                self.repository.list_courses_for_teacher(teacher_id=owner_sub, limit=200, offset=0)
                or []
            )
            if str(item.get("id") or "")
        ]

    def course_refs(self, owner_sub: str, courses: list[dict]) -> dict[str, list[dict]]:
        """Associate units only with owner-scoped course reads."""
        refs = {}
        if not courses:
            return refs
        courses_by_id = {course["id"]: course for course in courses}
        for assignment in self.repository.list_catalog_course_refs(
            owner_sub=owner_sub, course_ids=list(courses_by_id)
        ):
            unit_id = str(assignment.get("unit_id") or "")
            course = courses_by_id.get(assignment.get("course_id"))
            if unit_id and course:
                refs.setdefault(unit_id, []).append(
                    {"id": course["id"], "title": course["title"], "href": f"/teaching/courses/{course['id']}"}
                )
        return refs

    def home(self, owner_sub: str) -> dict[str, object]:
        """Use catalog activity ordering for the authenticated owner's last three units."""
        courses = self.courses(owner_sub)
        catalog = self.catalog(owner_sub, courses=courses)
        return {
            "courses": sorted(courses, key=lambda item: item["title"].casefold()),
            "recent_units": [
                {key: str(item.get(key) or "") for key in ("id", "title", "updated_at", "href")}
                for item in catalog["items"][:3]
                if str(item.get("id") or "")
            ],
        }

    def catalog(
        self,
        owner_sub: str,
        query: str = "",
        sort: str | None = None,
        *,
        courses: list[dict] | None = None,
    ) -> dict[str, object]:
        """Build the owner-scoped unit catalog projection shared by teacher views.

        The teacher home page deliberately reuses this projection so its recent
        units follow the exact same activity and sorting rules as the full catalog.
        Callers must pass the authenticated teacher subject; repository reads keep
        enforcing author ownership.
        """
        course_refs_by_unit = self.course_refs(
            owner_sub, courses if courses is not None else self.courses(owner_sub)
        )
        units = self.repository.list_units_for_author(author_id=owner_sub, limit=200, offset=0)
        summaries = self.repository.list_catalog_section_summaries(
            owner_sub=owner_sub, unit_ids=[str(unit["id"]) for unit in units]
        ) if units else {}

        items: list[dict[str, object]] = []

        for unit in units:
            unit_id = str(unit.get("id") or "")
            refs = course_refs_by_unit.get(unit_id, [])
            section_summary = summaries.get(unit_id, {})
            sections_count = int(section_summary.get("count") or 0)
            courses_count = len(refs)
            last_activity = max(
                str(unit.get("updated_at") or ""), str(section_summary.get("updated_at") or "")
            )
            haystack = " ".join(
                part.strip().lower()
                for part in (
                    str(unit.get("title") or ""),
                    str(unit.get("summary") or ""),
                )
                if part
            )

            if courses_count > 0:
                status_label = "Aktiv im Unterricht"
                status_tone = "success"
            elif sections_count == 0:
                status_label = "Entwurf"
                status_tone = "muted"
            else:
                status_label = "In Bearbeitung"
                status_tone = "accent"

            items.append(
                {
                    "id": unit_id,
                    "title": str(unit.get("title") or ""),
                    "topic": str(unit.get("summary") or "").strip() or None,
                    "updated_at": last_activity,
                    "href": f"/teaching/units/{unit_id}",
                    "courses_count": courses_count,
                    "courses": [
                        {
                            "id": str(ref.get("id") or ""),
                            "title": str(ref.get("title") or ""),
                            "href": str(ref.get("href") or ""),
                        }
                        for ref in refs
                        if str(ref.get("id") or "")
                    ],
                    "status_label": status_label,
                    "status_tone": status_tone,
                    "searchable": haystack,
                }
            )

        query_value = query.strip()
        if query_value:
            needle = query_value.lower()
            items = [item for item in items if needle in str(item["searchable"])]

        active_sort = sort or "updated_desc"
        if active_sort == "title_asc":
            items.sort(key=lambda item: str(item["title"]).lower())
        else:
            items.sort(key=lambda item: str(item["updated_at"]), reverse=True)

        list_items = [
            {
                "id": str(item["id"]),
                "title": str(item["title"]),
                "topic": item["topic"],
                "status_label": str(item["status_label"]),
                "status_tone": str(item["status_tone"]),
                "courses_count": int(item["courses_count"]),
                "courses": item["courses"],
                "updated_at": str(item["updated_at"]),
                "href": str(item["href"]),
            }
            for item in items
        ]

        return {
            "query": query_value,
            "sort": active_sort,
            "result_count": len(list_items),
            "items": list_items,
            "create_href": "/teaching/units?create=1",
        }
