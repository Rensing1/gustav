"""Build the public task columns in teaching order, independent of SQL ordering."""

from typing import Any, Protocol


class LiveTaskReader(Protocol):
    """Both reads enforce the caller's author scope in the persistence adapter."""

    def list_sections_for_author(self, unit_id: str, author_id: str) -> list[dict[str, Any]]: ...

    def list_tasks_for_unit_owned(self, unit_id: str, author_id: str) -> list[dict[str, Any]]: ...


def load_live_tasks(repo: LiveTaskReader, unit_id: str, author_id: str) -> list[dict[str, Any]]:
    """Load a unit's public task columns with two bounded repository reads.

    The caller must own the course and be allowed to read this unit. Repository
    reads retain author-scoped authorization. Empty sections contribute no
    columns; UUID ordering must never replace the lesson's section positions.
    """
    sections = sorted(repo.list_sections_for_author(unit_id, author_id), key=lambda section: (section["position"], section["id"]))
    positions = {section["id"]: index for index, section in enumerate(sections)}
    tasks = repo.list_tasks_for_unit_owned(unit_id, author_id)
    ordered = sorted(
        (task for task in tasks if task["section_id"] in positions),
        key=lambda task: (positions[task["section_id"]], int(task.get("position") or 0), task["id"]),
    )
    return [
        {
            "id": task["id"],
            "instruction_md": task.get("instruction_md") or "",
            "position": int(task.get("position") or 0),
            "kind": str(task.get("kind") or "native"),
        }
        for task in ordered
    ]
