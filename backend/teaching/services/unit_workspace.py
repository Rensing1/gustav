"""Author-scoped graph workspace data, independent of HTTP and web globals."""

from typing import Protocol
from uuid import UUID

from backend.teaching.errors import TeachingRepositoryUnavailable


class UnitWorkspaceRepository(Protocol):
    """Every graph/content read remains scoped to the authenticated author."""

    def unit_exists_for_author(self, unit_id: str, author_id: str) -> bool: ...
    def unit_exists(self, unit_id: str) -> bool: ...
    def get_unit_for_author(self, unit_id: str, author_id: str) -> dict | None: ...
    def list_courses_for_teacher(
        self, *, teacher_id: str, limit: int, offset: int
    ) -> list[dict]: ...
    def list_course_units_for_owner(self, course_id: str, owner_sub: str) -> list[dict]: ...
    def list_sections_for_author(self, unit_id: str, author_id: str) -> list[dict]: ...
    def list_materials_for_section_owned(
        self, unit_id: str, section_id: str, author_id: str
    ) -> list[dict]: ...
    def list_tasks_for_section_owned(
        self, unit_id: str, section_id: str, author_id: str
    ) -> list[dict]: ...
    def list_unit_phases_for_author(self, unit_id: str, author_id: str) -> list[dict]: ...
    def list_unit_modules_for_author(self, *, unit_id: str, author_id: str) -> list[dict]: ...
    def list_unit_module_edges_for_author(self, *, unit_id: str, author_id: str) -> list[dict]: ...


class WorkspaceAccessDenied(PermissionError):
    """Ownership cannot be established."""


class WorkspaceNotFound(LookupError):
    """The requested unit does not exist."""


class WorkspaceRepositoryIncomplete(RuntimeError):
    """The adapter cannot supply modular graph data."""


class WorkspaceInvalidSelection(ValueError):
    """A relevant selection parameter is not UUID-like."""


class UnitWorkspaceService:
    def __init__(self, repository: UnitWorkspaceRepository):
        self.repository = repository

    def read(
        self,
        owner_sub: str,
        unit_id: str,
        *,
        section_id: str | None = None,
        phase_id: str | None = None,
        module_id: str | None = None,
        edge_from_module_id: str | None = None,
        edge_to_module_id: str | None = None,
    ) -> dict:
        """Read an author's graph and preserve its existing selection rules.

        Supply an authenticated teacher/admin subject and validated unit ID.
        Ownership is checked before structure or content reads. Relevant optional
        IDs are validated according to unit type; unknown selections stay empty.
        Only counts, never material/task contents, enter the workspace payload.
        Learner access and unlock states deliberately belong to Learning.
        """
        repo = self.repository
        try:
            owned = repo.unit_exists_for_author(unit_id, owner_sub)
            exists = True if owned else repo.unit_exists(unit_id)
        except TeachingRepositoryUnavailable:
            raise
        except Exception as exc:
            raise WorkspaceAccessDenied() from exc
        if not owned:
            if exists is False:
                raise WorkspaceNotFound()
            raise WorkspaceAccessDenied()
        unit = repo.get_unit_for_author(unit_id, owner_sub)
        if not unit:
            raise WorkspaceNotFound()

        unit_type = str(unit.get("unit_type") or "linear").strip().lower() or "linear"
        courses_count = sum(
            str(item.get("id") or "") == unit_id
            for course in (
                repo.list_courses_for_teacher(teacher_id=owner_sub, limit=200, offset=0) or []
            )
            if str(course.get("id") or "")
            for item in repo.list_course_units_for_owner(str(course["id"]), owner_sub)
        )

        if unit_type == "modular":
            counts, graph, selection = self._modular_graph(
                owner_sub,
                unit_id,
                courses_count,
                phase_id,
                module_id,
                edge_from_module_id,
                edge_to_module_id,
            )
        else:
            counts, graph, selection = self._linear_graph(
                owner_sub, unit_id, courses_count, section_id
            )

        body = {
            "unit": {
                "id": str(unit.get("id") or ""),
                "title": str(unit.get("title") or ""),
                "summary": unit.get("summary"),
                "unit_type": unit_type,
                "edit_href": f"/teaching/units/{unit_id}?edit=1",
            },
            "counts": counts,
            "graph": graph,
            "selection": selection,
        }
        return body

    def _modular_graph(
        self,
        owner_sub: str,
        unit_id: str,
        courses_count: int,
        phase_id: str | None,
        module_id: str | None,
        edge_from_module_id: str | None,
        edge_to_module_id: str | None,
    ) -> tuple[dict, dict, dict]:
        """Project phases/modules and prefer edge, then module, then phase selection."""
        repo = self.repository
        selection: dict[str, object] = {"kind": "none"}
        required_methods = (
            "list_unit_phases_for_author",
            "list_unit_modules_for_author",
            "list_unit_module_edges_for_author",
        )
        if not all(callable(getattr(repo, method, None)) for method in required_methods):
            raise WorkspaceRepositoryIncomplete()

        selected_phase_id = _validate_optional_uuid(phase_id, "invalid_phase_id")
        selected_module_id = _validate_optional_uuid(module_id, "invalid_module_id")
        edge_source_id = _validate_optional_uuid(edge_from_module_id, "invalid_edge_from_module_id")
        edge_target_id = _validate_optional_uuid(edge_to_module_id, "invalid_edge_to_module_id")

        phases = repo.list_unit_phases_for_author(unit_id, owner_sub) or []
        modules = repo.list_unit_modules_for_author(unit_id=unit_id, author_id=owner_sub) or []
        edges = [
            {
                "from": edge.get("from")
                if "from" in edge and "to" in edge
                else edge.get("from_module_id"),
                "to": edge.get("to")
                if "from" in edge and "to" in edge
                else edge.get("to_module_id"),
            }
            for edge in (
                repo.list_unit_module_edges_for_author(unit_id=unit_id, author_id=owner_sub) or []
            )
        ]

        module_items: list[dict[str, object]] = []
        modules_by_id: dict[str, dict[str, object]] = {}
        phase_items: list[dict[str, object]] = []
        for module in modules:
            section_id = str(module.get("section_id") or "")
            materials_count = 0
            tasks_count = 0
            if section_id:
                materials_count = len(
                    (repo.list_materials_for_section_owned(unit_id, section_id, owner_sub) or [])
                )
                tasks_count = len(
                    (repo.list_tasks_for_section_owned(unit_id, section_id, owner_sub) or [])
                )
            item = {
                "id": str(module.get("id") or ""),
                "title": str(module.get("title") or ""),
                "phase_id": str(module.get("phase_id") or ""),
                "position_in_phase": int(module.get("position_in_phase") or 0),
                "required_prereq_count": int(module.get("required_prereq_count") or 0),
                "module_kind": str(module.get("module_kind") or "learning"),
                "materials_count": materials_count,
                "tasks_count": tasks_count,
                "editor_href": f"/teaching/units/{unit_id}/nodes/{str(module.get('id') or '')}",
                "section_id": section_id or None,
            }
            module_items.append(item)
            if item["id"]:
                modules_by_id[str(item["id"])] = item

        for phase in phases:
            phase_items.append(
                {
                    "id": str(phase.get("id") or ""),
                    "title": str(phase.get("title") or ""),
                    "position": int(phase.get("position") or 0),
                    "modules": [
                        item
                        for item in module_items
                        if str(item.get("phase_id") or "") == str(phase.get("id") or "")
                    ],
                }
            )

        counts = {
            "sections_count": 0,
            "phases_count": len(phases),
            "modules_count": len(module_items),
            "courses_count": courses_count,
        }

        # An explicit phase selection must not be replaced by the default module.
        # This keeps the graph's phase inspector stable after URL navigation.
        if (
            not selected_module_id
            and not selected_phase_id
            and not (edge_source_id or edge_target_id)
            and module_items
        ):
            selected_module_id = str(module_items[0].get("id") or "")
        selected_module = modules_by_id.get(selected_module_id or "")
        selected_phase = next(
            (phase for phase in phases if str(phase.get("id") or "") == (selected_phase_id or "")),
            None,
        )
        selected_edge = None
        if edge_source_id and edge_target_id:
            source_title = str((modules_by_id.get(edge_source_id or "") or {}).get("title") or "")
            target_title = str((modules_by_id.get(edge_target_id or "") or {}).get("title") or "")
            selected_edge = {
                "from_id": edge_source_id,
                "to_id": edge_target_id,
                "from_title": source_title,
                "to_title": target_title,
                "exists": any(
                    str(edge.get("from") or "") == edge_source_id
                    and str(edge.get("to") or "") == edge_target_id
                    for edge in edges
                ),
            }

        graph = {
            "kind": "modular",
            "create_phase_href": f"/teaching/units/{unit_id}?create-phase=1",
            "create_module_href": f"/teaching/units/{unit_id}?create-module=1",
            "phases": phase_items,
            "edges": edges,
        }
        if selected_edge:
            selection = {"kind": "edge", "edge": selected_edge}
        elif selected_module:
            selection = {"kind": "module", "module": selected_module}
        elif selected_phase:
            selection = {
                "kind": "phase",
                "phase": {
                    "id": str((selected_phase or {}).get("id") or ""),
                    "title": str((selected_phase or {}).get("title") or ""),
                    "position": int((selected_phase or {}).get("position") or 0),
                },
            }
        return counts, graph, selection

    def _linear_graph(
        self,
        owner_sub: str,
        unit_id: str,
        courses_count: int,
        section_id: str | None,
    ) -> tuple[dict, dict, dict]:
        """Project ordered sections; default to the first only without explicit selection."""
        repo = self.repository
        selection: dict[str, object] = {"kind": "none"}
        selected_section_id = _validate_optional_uuid(section_id, "invalid_section_id")

        sections = repo.list_sections_for_author(unit_id, owner_sub) or []
        section_items: list[dict[str, object]] = []
        for section in sections:
            current_section_id = str(section.get("id") or "")
            section_items.append(
                {
                    "id": current_section_id,
                    "title": str(section.get("title") or ""),
                    "position": int(section.get("position") or 0),
                    "materials_count": len(
                        (
                            repo.list_materials_for_section_owned(
                                unit_id, current_section_id, owner_sub
                            )
                            or []
                        )
                    ),
                    "tasks_count": len(
                        (
                            repo.list_tasks_for_section_owned(
                                unit_id, current_section_id, owner_sub
                            )
                            or []
                        )
                    ),
                    "editor_href": f"/teaching/units/{unit_id}/nodes/{current_section_id}",
                }
            )

        counts = {
            "sections_count": len(section_items),
            "phases_count": 0,
            "modules_count": 0,
            "courses_count": courses_count,
        }

        if not selected_section_id and section_items:
            selected_section_id = str(section_items[0].get("id") or "")

        selected_structure_section = next(
            (
                section
                for section in section_items
                if str(section.get("id") or "") == (selected_section_id or "")
            ),
            None,
        )
        graph = {
            "kind": "linear",
            "create_section_href": f"/teaching/units/{unit_id}?create-section=1",
            "nodes": section_items,
        }
        if selected_structure_section:
            selection = {
                "kind": "section",
                "section": {
                    "id": str(selected_structure_section.get("id") or ""),
                    "title": str(selected_structure_section.get("title") or ""),
                    "position": int(selected_structure_section.get("position") or 0),
                    "editor_href": str(selected_structure_section.get("editor_href") or ""),
                },
            }

        return counts, graph, selection


def _validate_optional_uuid(raw_value: str | None, detail: str) -> str:
    value = str(raw_value or "").strip()
    if value:
        try:
            UUID(value)
        except (ValueError, TypeError) as exc:
            raise WorkspaceInvalidSelection(detail) from exc
    return value
