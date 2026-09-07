"""Owner-scoped content editor read model, independent of the web framework."""

from typing import Protocol

from backend.teaching.errors import TeachingRepositoryUnavailable
from backend.teaching.task_payload import serialize_task


class NodeEditorRepository(Protocol):
    """Keep every content read scoped to the authenticated author and unit."""

    def unit_exists_for_author(self, unit_id: str, author_id: str) -> bool: ...
    def unit_exists(self, unit_id: str) -> bool: ...
    def get_unit_for_author(self, unit_id: str, author_id: str) -> dict | None: ...
    def list_sections_for_author(self, unit_id: str, author_id: str) -> list[dict]: ...
    def get_unit_module_for_author(
        self, *, unit_id: str, module_id: str, author_id: str
    ) -> dict | None: ...
    def list_materials_for_section_owned(
        self, unit_id: str, section_id: str, author_id: str
    ) -> list[dict]: ...
    def list_tasks_for_section_owned(
        self, unit_id: str, section_id: str, author_id: str
    ) -> list[dict]: ...


class NodeEditorAccessDenied(PermissionError):
    """The caller is not allowed to read this unit."""


class NodeEditorNotFound(LookupError):
    """The unit or its requested node is absent."""


class NodeEditorRepositoryIncomplete(RuntimeError):
    """The adapter cannot supply modular editor data."""


class NodeEditorService:
    def __init__(self, repository: NodeEditorRepository):
        self.repository = repository

    def read(self, owner_sub: str, unit_id: str, node_id: str) -> dict:
        """Read an author's section or module and its editable content.

        The caller supplies authenticated identity and validated IDs. Ownership
        is checked before any content read. Preserve the existing distinction
        between foreign units (denied) and absent units/nodes (not found).
        """
        repo = self.repository
        try:
            owned = repo.unit_exists_for_author(unit_id, owner_sub)
            exists = True if owned else repo.unit_exists(unit_id)
        except TeachingRepositoryUnavailable:
            raise
        except Exception as exc:
            raise NodeEditorAccessDenied() from exc
        if not owned:
            if exists is False:
                raise NodeEditorNotFound()
            raise NodeEditorAccessDenied()
        serialized_unit = repo.get_unit_for_author(unit_id, owner_sub)
        if not serialized_unit:
            raise NodeEditorNotFound()
        unit_type = str(serialized_unit.get("unit_type") or "linear").strip().lower() or "linear"

        node_kind = "section"
        node_title = ""
        backing_section_id = node_id
        settings: dict[str, object] = {"kind": "section"}

        if unit_type == "modular":
            if not callable(getattr(repo, "get_unit_module_for_author", None)):
                raise NodeEditorRepositoryIncomplete()
            module = repo.get_unit_module_for_author(
                unit_id=unit_id, module_id=node_id, author_id=owner_sub
            )
            if not module:
                raise NodeEditorNotFound()
            node_kind = "module"
            node_title = str(module.get("title") or "")
            backing_section_id = str(module.get("section_id") or "")
            settings = {
                "kind": "module",
                "required_prereq_count": int(module.get("required_prereq_count") or 0),
                "module_kind": str(module.get("module_kind") or "learning"),
            }
        else:
            section = next(
                (
                    item
                    for item in repo.list_sections_for_author(unit_id, owner_sub)
                    if str(item.get("id") or "") == node_id
                ),
                None,
            )
            if not section:
                raise NodeEditorNotFound()
            node_title = str(section.get("title") or "")

        materials = repo.list_materials_for_section_owned(unit_id, backing_section_id, owner_sub)
        tasks = [
            serialize_task(task)
            for task in repo.list_tasks_for_section_owned(unit_id, backing_section_id, owner_sub)
        ]

        body = {
            "unit": {
                "id": str(serialized_unit.get("id") or ""),
                "title": str(serialized_unit.get("title") or ""),
                "summary": serialized_unit.get("summary"),
                "unit_type": unit_type,
                "edit_href": f"/teaching/units/{unit_id}?edit=1",
            },
            "node": {
                "id": node_id,
                "kind": node_kind,
                "title": node_title,
                "editor_title": node_title,
            },
            "materials": [
                {
                    "id": str(item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "kind": str(item.get("kind") or "markdown"),
                    "body_md": item.get("body_md"),
                    "position": int(item.get("position") or 0),
                    "mime_type": item.get("mime_type"),
                    "size_bytes": item.get("size_bytes"),
                    "filename_original": item.get("filename_original"),
                    "alt_text": item.get("alt_text"),
                }
                for item in materials
                if str(item.get("id") or "")
            ],
            "tasks": [
                {
                    "id": str(item.get("id") or ""),
                    "instruction_md": str(item.get("instruction_md") or ""),
                    "criteria": list(item.get("criteria") or []),
                    "teacher_context_md": item.get("teacher_context_md"),
                    "model_solution_md": item.get("model_solution_md"),
                    "due_at": item.get("due_at"),
                    "max_attempts": item.get("max_attempts"),
                    "position": int(item.get("position") or 0),
                    "kind": str(item.get("kind") or "native"),
                    "h5p": item.get("h5p"),
                    "visual": item.get("visual"),
                    "scratch": item.get("scratch"),
                    "calliope": item.get("calliope"),
                    "filius": item.get("filius"),
                    "dialog": item.get("dialog"),
                }
                for item in tasks
                if str(item.get("id") or "")
            ],
            "settings": settings,
        }
        if node_kind == "module":
            body["node"]["backing_section_id"] = backing_section_id
            body["node"]["module_kind"] = str(settings.get("module_kind") or "learning")
        return body
