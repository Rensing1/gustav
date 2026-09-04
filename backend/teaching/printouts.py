"""Application logic for teacher-authored printable learning-unit content.

Why:
    Printing is a Teaching use case, not an HTTP concern. This module builds an
    author-scoped, ordered selection model without depending on FastAPI or a PDF
    library. Callers must provide the authenticated author's opaque subject.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PrintPolicy:
    """Hard resource limits shared by selection metadata and PDF generation."""

    max_selected_items: int = 200
    max_source_bytes: int = 50 * 1024 * 1024
    max_output_bytes: int = 50 * 1024 * 1024
    max_pages: int = 200

    def as_dict(self) -> dict[str, int]:
        return {
            "max_selected_items": self.max_selected_items,
            "max_source_bytes": self.max_source_bytes,
            "max_output_bytes": self.max_output_bytes,
            "max_pages": self.max_pages,
        }


DEFAULT_PRINT_POLICY = PrintPolicy()


@dataclass(frozen=True)
class PrintablePdf:
    """Binary PDF response prepared independently of the HTTP framework."""

    content: bytes
    filename: str


class PrintExportError(Exception):
    """Stable application error that HTTP adapters can map without inspection."""

    def __init__(
        self,
        code: str,
        status_code: int,
        *,
        material_title: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.material_title = material_title


def _value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _ordered(items: list[object], position_name: str = "position") -> list[object]:
    return sorted(items, key=lambda item: (int(_value(item, position_name, 0) or 0), str(_value(item, "id", ""))))


def _task_preview(markdown: object) -> str:
    """Return a short plain-text label without exposing task configuration."""

    text = str(markdown or "")
    text = re.sub(r"[`*_>#\[\]()]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:117].rstrip() + "..." if len(text) > 120 else text


def _printable_item(item: object, *, content_type: str) -> dict[str, object]:
    kind = str(_value(item, "kind", "markdown" if content_type == "material" else "native") or "")
    label = str(_value(item, "title", "") or "") if content_type == "material" else _task_preview(
        _value(item, "instruction_md", "")
    )
    return {
        "id": str(_value(item, "id", "") or ""),
        "content_type": content_type,
        "kind": kind,
        "label": label,
        "position": int(_value(item, "position", 0) or 0),
        "mime_type": _value(item, "mime_type"),
        "filename_original": _value(item, "filename_original"),
        "size_bytes": _value(item, "size_bytes"),
    }


def _node(
    repo: object,
    *,
    unit_id: str,
    section_id: str,
    author_id: str,
    node: object,
    kind: str,
    position_name: str,
    materials_by_section: dict[str, list[object]] | None = None,
    tasks_by_section: dict[str, list[object]] | None = None,
) -> dict[str, object]:
    materials = (
        materials_by_section.get(section_id, [])
        if materials_by_section is not None
        else repo.list_materials_for_section_owned(unit_id, section_id, author_id)
    )
    tasks = (
        tasks_by_section.get(section_id, [])
        if tasks_by_section is not None
        else repo.list_tasks_for_section_owned(unit_id, section_id, author_id)
    )
    return {
        "id": str(_value(node, "id", "") or ""),
        "kind": kind,
        "title": str(_value(node, "title", "") or ""),
        "position": int(_value(node, position_name, 0) or 0),
        "materials": [_printable_item(item, content_type="material") for item in _ordered(list(materials or []))],
        "tasks": [_printable_item(item, content_type="task") for item in _ordered(list(tasks or []))],
    }


def _batch_content_by_section(
    repo: object,
    *,
    unit_id: str,
    author_id: str,
) -> tuple[dict[str, list[object]], dict[str, list[object]]] | None:
    """Group optional unit-wide reads so node traversal never causes N+1."""

    material_reader = getattr(repo, "list_materials_for_unit_owned", None)
    task_reader = getattr(repo, "list_tasks_for_unit_owned", None)
    if not callable(material_reader) or not callable(task_reader):
        return None
    material_groups: dict[str, list[object]] = {}
    task_groups: dict[str, list[object]] = {}
    for material in material_reader(unit_id, author_id) or []:
        material_groups.setdefault(str(_value(material, "section_id", "") or ""), []).append(material)
    for task in task_reader(unit_id, author_id) or []:
        task_groups.setdefault(str(_value(task, "section_id", "") or ""), []).append(task)
    return material_groups, task_groups


def list_printable_content(
    repo: object,
    *,
    unit_id: str,
    author_id: str,
    policy: PrintPolicy = DEFAULT_PRINT_POLICY,
) -> dict[str, object] | None:
    """Build the ordered print-selection projection for an authored unit.

    Parameters:
        repo: Teaching repository whose reads enforce the current author.
        unit_id: Learning-unit UUID already validated by the HTTP adapter.
        author_id: Authenticated teacher subject used by every repository read.
        policy: Fixed export limits shown to the teacher.
    Returns:
        The selection projection, or ``None`` when the unit is not visible to
        the author.
    Permissions:
        The caller must be a teacher or admin; repository reads still bind all
        rows to ``author_id`` as defense in depth.
    """

    unit = repo.get_unit_for_author(unit_id, author_id)
    if not unit:
        return None
    unit_type = str(_value(unit, "unit_type", "linear") or "linear")
    linear_sections: list[dict[str, object]] = []
    modular_phases: list[dict[str, object]] = []
    batch_content = _batch_content_by_section(repo, unit_id=unit_id, author_id=author_id)
    materials_by_section, tasks_by_section = batch_content or (None, None)

    if unit_type == "modular":
        phases = _ordered(list(repo.list_unit_phases_for_author(unit_id, author_id) or []))
        modules = _ordered(
            list(repo.list_unit_modules_for_author(unit_id=unit_id, author_id=author_id) or []),
            "position_in_phase",
        )
        for phase in phases:
            phase_id = str(_value(phase, "id", "") or "")
            phase_modules: list[dict[str, object]] = []
            for module in modules:
                if str(_value(module, "phase_id", "") or "") != phase_id:
                    continue
                section_id = str(
                    _value(module, "section_id", "")
                    or _value(module, "backing_section_id", "")
                    or ""
                )
                if not section_id:
                    continue
                phase_modules.append(
                    _node(
                        repo,
                        unit_id=unit_id,
                        section_id=section_id,
                        author_id=author_id,
                        node=module,
                        kind="module",
                        position_name="position_in_phase",
                        materials_by_section=materials_by_section,
                        tasks_by_section=tasks_by_section,
                    )
                )
            modular_phases.append(
                {
                    "id": phase_id,
                    "title": str(_value(phase, "title", "") or ""),
                    "position": int(_value(phase, "position", 0) or 0),
                    "modules": phase_modules,
                }
            )
    else:
        for section in _ordered(list(repo.list_sections_for_author(unit_id, author_id) or [])):
            section_id = str(_value(section, "id", "") or "")
            linear_sections.append(
                _node(
                    repo,
                    unit_id=unit_id,
                    section_id=section_id,
                    author_id=author_id,
                    node=section,
                    kind="section",
                    position_name="position",
                    materials_by_section=materials_by_section,
                    tasks_by_section=tasks_by_section,
                )
            )

    return {
        "unit": {
            "id": str(_value(unit, "id", "") or ""),
            "title": str(_value(unit, "title", "") or ""),
            "unit_type": unit_type,
        },
        "linear_sections": linear_sections,
        "modular_phases": modular_phases,
        "limits": policy.as_dict(),
    }


def validate_selection(material_ids: object, task_ids: object, *, policy: PrintPolicy = DEFAULT_PRINT_POLICY) -> tuple[list[str], list[str]]:
    """Validate the untrusted ID lists before repository or renderer work."""

    if not isinstance(material_ids, list) or not isinstance(task_ids, list):
        raise ValueError("invalid_print_selection")
    if any(not isinstance(item, str) for item in [*material_ids, *task_ids]):
        raise ValueError("invalid_print_selection")
    if len(material_ids) != len(set(material_ids)) or len(task_ids) != len(set(task_ids)):
        raise ValueError("duplicate_print_selection")
    if not material_ids and not task_ids:
        raise ValueError("empty_print_selection")
    if len(material_ids) + len(task_ids) > policy.max_selected_items:
        raise OverflowError("selected_items_exceeded")
    return list(material_ids), list(task_ids)


def _source_nodes(repo: object, *, unit: object, unit_id: str, author_id: str) -> list[dict[str, object]]:
    """Load ordered content containers through author-scoped repository reads."""

    nodes: list[dict[str, object]] = []
    unit_type = str(_value(unit, "unit_type", "linear") or "linear")
    if unit_type == "modular":
        phases = _ordered(list(repo.list_unit_phases_for_author(unit_id, author_id) or []))
        modules = list(repo.list_unit_modules_for_author(unit_id=unit_id, author_id=author_id) or [])
        phase_positions = {str(_value(phase, "id", "")): index for index, phase in enumerate(phases)}
        modules.sort(
            key=lambda module: (
                phase_positions.get(str(_value(module, "phase_id", "")), len(phases)),
                int(_value(module, "position_in_phase", 0) or 0),
                str(_value(module, "id", "")),
            )
        )
        raw_nodes = [
            (module, str(_value(module, "section_id", "") or ""))
            for module in modules
        ]
    else:
        raw_nodes = [
            (section, str(_value(section, "id", "") or ""))
            for section in _ordered(list(repo.list_sections_for_author(unit_id, author_id) or []))
        ]

    batch_content = _batch_content_by_section(repo, unit_id=unit_id, author_id=author_id)
    materials_by_section, tasks_by_section = batch_content or (None, None)
    for node, section_id in raw_nodes:
        if not section_id:
            continue
        nodes.append(
            {
                "title": str(_value(node, "title", "") or ""),
                "materials": _ordered(
                    list(
                        materials_by_section.get(section_id, [])
                        if materials_by_section is not None
                        else repo.list_materials_for_section_owned(unit_id, section_id, author_id) or []
                    )
                ),
                "tasks": _ordered(
                    list(
                        tasks_by_section.get(section_id, [])
                        if tasks_by_section is not None
                        else repo.list_tasks_for_section_owned(unit_id, section_id, author_id) or []
                    )
                ),
            }
        )
    return nodes


def _safe_filename(title: str) -> str:
    """Create a predictable ASCII download name without path-significant text."""

    slug = title.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:80] or "lerneinheit"
    return f"gustav-{slug}-druckfassung.pdf"


_INTERACTIVE_TASK_KINDS = {"h5p", "dialog", "scratch", "calliope", "filius", "simulation"}
_DIGITAL_HINT = "Für die interaktive Bearbeitung wird ein digitales Gerät benötigt."


def _prepare_material(
    material: object,
    *,
    storage: object,
    storage_bucket: str,
    remaining_source_bytes: int,
) -> tuple[dict[str, object], int]:
    title = str(_value(material, "title", "Material") or "Material")
    kind = str(_value(material, "kind", "markdown") or "markdown")
    body_md = str(_value(material, "body_md", "") or "")
    if kind == "markdown":
        return {"type": "markdown", "title": title, "body_md": body_md}, 0
    if kind == "simulation":
        return {
            "type": "markdown",
            "title": title,
            "body_md": body_md,
            "digital_hint": _DIGITAL_HINT,
        }, 0

    mime_type = str(_value(material, "mime_type", "") or "").lower()
    item_type = "pdf" if mime_type == "application/pdf" else "image" if mime_type.startswith("image/") else None
    storage_key = str(_value(material, "storage_key", "") or "")
    if kind != "file" or item_type is None or not storage_key:
        raise PrintExportError("material_unprintable", 422, material_title=title)
    declared_size = int(_value(material, "size_bytes", 0) or 0)
    if declared_size > remaining_source_bytes:
        raise PrintExportError("source_bytes_exceeded", 413, material_title=title)
    try:
        content = storage.read_object(
            bucket=storage_bucket,
            key=storage_key,
            max_bytes=remaining_source_bytes,
        )
    except ValueError as exc:
        if str(exc) == "size_exceeded":
            raise PrintExportError("source_bytes_exceeded", 413, material_title=title) from exc
        raise PrintExportError("material_unprintable", 422, material_title=title) from exc
    except Exception as exc:
        raise PrintExportError("source_unavailable", 503, material_title=title) from exc
    if len(content) > remaining_source_bytes:
        raise PrintExportError("source_bytes_exceeded", 413, material_title=title)
    return {
        "type": item_type,
        "title": title,
        "body_md": body_md,
        "filename": str(_value(material, "filename_original", "") or "Datei"),
        "mime_type": mime_type,
        "alt_text": str(_value(material, "alt_text", "") or ""),
        "content": content,
    }, len(content)


def create_printable_pdf(
    repo: object,
    *,
    storage: object,
    renderer: object,
    unit_id: str,
    author_id: str,
    material_ids: object,
    task_ids: object,
    storage_bucket: str,
    policy: PrintPolicy = DEFAULT_PRINT_POLICY,
) -> PrintablePdf:
    """Create a transient, student-safe PDF for an authored learning unit.

    Parameters:
        repo: Teaching repository whose reads are scoped to ``author_id``.
        storage: Private material storage adapter used only for selected files.
        renderer: PDF adapter accepting the already sanitised print document.
        unit_id: Learning unit to print.
        author_id: Authenticated teacher subject.
        material_ids: Explicit material selection from the untrusted request.
        task_ids: Explicit task selection from the untrusted request.
        storage_bucket: Private bucket containing authored files.
        policy: Hard limits for selection, source data, pages and output bytes.
    Returns:
        The generated PDF bytes and a safe download filename. Nothing is stored.
    Permissions:
        The caller must be a teacher or admin and the author of the unit. Every
        repository read remains author-scoped as defense in depth.
    """

    try:
        selected_materials, selected_tasks = validate_selection(material_ids, task_ids, policy=policy)
    except OverflowError as exc:
        raise PrintExportError(str(exc), 413) from exc
    except ValueError as exc:
        raise PrintExportError(str(exc), 400) from exc

    unit = repo.get_unit_for_author(unit_id, author_id)
    if not unit:
        raise PrintExportError("not_found", 404)
    nodes = _source_nodes(repo, unit=unit, unit_id=unit_id, author_id=author_id)
    available_material_ids = {
        str(_value(material, "id", ""))
        for node in nodes
        for material in node["materials"]  # type: ignore[union-attr]
    }
    available_task_ids = {
        str(_value(task, "id", ""))
        for node in nodes
        for task in node["tasks"]  # type: ignore[union-attr]
    }
    if not set(selected_materials).issubset(available_material_ids) or not set(selected_tasks).issubset(
        available_task_ids
    ):
        # Deliberately do not reveal whether a rejected ID exists elsewhere.
        raise PrintExportError("invalid_print_selection", 400)

    selected_material_set = set(selected_materials)
    selected_task_set = set(selected_tasks)
    source_bytes = 0
    document_nodes: list[dict[str, object]] = []
    for node in nodes:
        items: list[dict[str, object]] = []
        for material in node["materials"]:  # type: ignore[union-attr]
            if str(_value(material, "id", "")) not in selected_material_set:
                continue
            item, byte_count = _prepare_material(
                material,
                storage=storage,
                storage_bucket=storage_bucket,
                remaining_source_bytes=policy.max_source_bytes - source_bytes,
            )
            source_bytes += byte_count
            items.append(item)
        for task in node["tasks"]:  # type: ignore[union-attr]
            if str(_value(task, "id", "")) not in selected_task_set:
                continue
            kind = str(_value(task, "kind", "native") or "native")
            task_item: dict[str, object] = {
                "type": "task",
                "title": "Aufgabe",
                "body_md": str(_value(task, "instruction_md", "") or ""),
            }
            if kind in _INTERACTIVE_TASK_KINDS:
                task_item["digital_hint"] = _DIGITAL_HINT
            items.append(task_item)
        if items:
            document_nodes.append({"title": str(node["title"]), "items": items})

    title = str(_value(unit, "title", "Lerneinheit") or "Lerneinheit")
    try:
        content = renderer.render({"title": title, "nodes": document_nodes}, policy=policy)
    except PrintExportError:
        raise
    except Exception as exc:
        raise PrintExportError("pdf_render_failed", 503) from exc
    if not isinstance(content, bytes) or not content.startswith(b"%PDF"):
        raise PrintExportError("pdf_render_failed", 503)
    if len(content) > policy.max_output_bytes:
        raise PrintExportError("output_bytes_exceeded", 413)
    return PrintablePdf(content=content, filename=_safe_filename(title))


__all__ = [
    "DEFAULT_PRINT_POLICY",
    "PrintExportError",
    "PrintPolicy",
    "PrintablePdf",
    "create_printable_pdf",
    "list_printable_content",
    "validate_selection",
]
