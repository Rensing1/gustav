"""Read and write the human-editable local GUSTAV mirror format."""

from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAX_YAML_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = 20 * 1024 * 1024
MAX_H5P_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_H5P_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
TEXT_FIELDS = (
    ("instruction_md", "instruction.md"),
    ("teacher_context_md", "teacher-context.md"),
    ("model_solution_md", "model-solution.md"),
)
UNIT_FIELDS = {
    "key",
    "unit_type",
    "title",
    "summary",
    "sections",
    "phases",
    "modules",
    "edges",
}
SECTION_FIELDS = {"key", "title", "materials", "tasks"}
PHASE_FIELDS = {"key", "title"}
MODULE_FIELDS = {
    "key",
    "phase",
    "title",
    "module_kind",
    "required_prereq_count",
    "materials",
    "tasks",
}
EDGE_FIELDS = {"from", "to"}
MATERIAL_FIELDS = {
    "key",
    "kind",
    "title",
    "filename_original",
    "mime_type",
    "alt_text",
    "body_file",
    "asset_file",
}
TASK_FIELDS = {
    "key",
    "kind",
    "instruction_file",
    "criteria",
    "teacher_context_file",
    "model_solution_file",
    "due_at",
    "max_attempts",
    "display_options",
    "h5p_file",
    "dialog",
    "visual",
    "scratch",
    "calliope",
    "filius",
}


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that also rejects ambiguous duplicate keys."""


def _construct_mapping(loader: _UniqueKeyLoader, node, deep: bool = False):  # noqa: ANN001
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError("duplicate_yaml_key")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("unsafe_local_path")
    if path.stat().st_size > MAX_YAML_BYTES:
        raise ValueError("yaml_too_large")
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("invalid_yaml") from exc
    if not isinstance(value, dict):
        raise ValueError("invalid_yaml_document")
    return {str(key): item for key, item in value.items()}


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value.rstrip("\n") + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(value)
    os.chmod(path, 0o600)


def _safe_filename(value: object, *, fallback: str) -> str:
    name = Path(str(value or "")).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return safe[:120] or fallback


def h5p_digest(content: bytes) -> str:
    """Hash H5P semantics while ignoring ZIP entry order and timestamps."""

    if len(content) > MAX_H5P_PACKAGE_BYTES:
        raise ValueError("h5p_package_too_large")
    digest = hashlib.sha256()
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > 5000:
                raise ValueError("h5p_package_too_large")
            for info in sorted(infos, key=lambda item: item.filename):
                path = Path(info.filename)
                if path.is_absolute() or ".." in path.parts or info.flag_bits & 0x1:
                    raise ValueError("unsafe_h5p_package")
                total += info.file_size
                if total > MAX_H5P_UNCOMPRESSED_BYTES:
                    raise ValueError("h5p_package_too_large")
                digest.update(info.filename.encode("utf-8"))
                digest.update(b"\0")
                digest.update(archive.read(info))
                digest.update(b"\0")
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("invalid_h5p_package") from exc
    return digest.hexdigest()


def _require_key(value: object) -> str:
    key = str(value or "")
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("invalid_local_key")
    return key


def _reject_unknown(value: dict[str, Any], allowed: set[str], *, kind: str) -> None:
    """Reject misspelled manifest fields instead of silently ignoring them."""

    if unknown := set(value) - allowed:
        raise ValueError(f"unknown_{kind}_field:{sorted(unknown)[0]}")


def _safe_local_file(unit_root: Path, relative: object) -> Path:
    candidate = unit_root / str(relative or "")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(unit_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError("unsafe_local_path") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise ValueError("unsafe_local_path")
    return resolved


def _containers(unit: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    field = "modules" if unit.get("unit_type") == "modular" else "sections"
    raw = unit.get(field, [])
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError(f"invalid_{field}")
    return field, raw


def _unique_items(items: object, *, kind: str) -> dict[str, dict[str, Any]]:
    """Index keyed manifest items while rejecting ambiguous duplicates."""

    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError(f"invalid_{kind}s")
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _require_key(item.get("key"))
        if key in indexed:
            raise ValueError(f"duplicate_{kind}_key")
        indexed[key] = item
    return indexed


def _validate_container_keys(containers: object, *, kind: str) -> dict[str, dict[str, Any]]:
    indexed = _unique_items(containers, kind=kind)
    for container in indexed.values():
        _unique_items(container.get("materials", []), kind="material")
        _unique_items(container.get("tasks", []), kind="task")
    return indexed


def _validate_modular_graph(unit: dict[str, Any]) -> None:
    phases = _unique_items(unit.get("phases", []), kind="phase")
    modules = _validate_container_keys(unit.get("modules", []), kind="module")
    incoming = {key: 0 for key in modules}
    adjacency = {key: set() for key in modules}
    seen_edges: set[tuple[str, str]] = set()

    for module in modules.values():
        if str(module.get("phase") or "") not in phases:
            raise ValueError("unknown_phase_key")

    edges = unit.get("edges", [])
    if not isinstance(edges, list) or any(not isinstance(edge, dict) for edge in edges):
        raise ValueError("invalid_edges")
    for edge in edges:
        source = _require_key(edge.get("from"))
        target = _require_key(edge.get("to"))
        if source not in modules or target not in modules:
            raise ValueError("unknown_edge_module")
        if source == target:
            raise ValueError("invalid_self_edge")
        if modules[source].get("module_kind", "learning") == "practice":
            raise ValueError("practice_module_outgoing_edge")
        pair = (source, target)
        if pair in seen_edges:
            raise ValueError("duplicate_edge")
        seen_edges.add(pair)
        adjacency[source].add(target)
        incoming[target] += 1

    # A topological walk mirrors the API's acyclic prerequisite invariant.
    remaining = dict(incoming)
    ready = [key for key, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        source = ready.pop()
        visited += 1
        for target in adjacency[source]:
            remaining[target] -= 1
            if remaining[target] == 0:
                ready.append(target)
    if visited != len(modules):
        raise ValueError("edge_cycle")

    for key, module in modules.items():
        required = module.get("required_prereq_count", 0)
        if isinstance(required, bool) or not isinstance(required, int):
            raise ValueError("invalid_required_prereq_count")
        if required < 0 or required > incoming[key]:
            raise ValueError("invalid_required_prereq_count")


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    """Validate local authoring relationships before any filesystem or API mutation."""

    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid_schema_version")
    units = snapshot.get("units")
    if not isinstance(units, dict):
        raise ValueError("invalid_units")
    for unit_key, unit in units.items():
        key = _require_key(unit_key)
        if not isinstance(unit, dict) or str(unit.get("key") or key) != key:
            raise ValueError("invalid_unit")
        unit_type = unit.get("unit_type")
        if unit_type == "modular":
            _validate_modular_graph(unit)
        elif unit_type == "linear":
            _validate_container_keys(unit.get("sections", []), kind="section")
        else:
            raise ValueError("invalid_unit_type")


def write_local_snapshot(root: Path, snapshot: dict[str, Any], *, base_url: str) -> None:
    """Write a normalized snapshot as YAML plus separate authored content files."""

    validate_snapshot(snapshot)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_yaml(
        root / "gustav.yaml",
        {"schema_version": SCHEMA_VERSION, "base_url": base_url.rstrip("/")},
    )
    units = snapshot.get("units", {})
    if not isinstance(units, dict):
        raise ValueError("invalid_units")
    for unit_key, raw_unit in units.items():
        key = _require_key(unit_key)
        if not isinstance(raw_unit, dict):
            raise ValueError("invalid_unit")
        unit = deepcopy(raw_unit)
        unit["key"] = key
        unit_root = root / "units" / key
        _field, containers = _containers(unit)
        for container in containers:
            container_key = _require_key(container.get("key"))
            for material in container.get("materials", []):
                material_key = _require_key(material.get("key"))
                if material.get("kind") == "markdown":
                    relative = f"content/{container_key}/materials/{material_key}.md"
                    _write_text(unit_root / relative, str(material.pop("body_md", "")))
                    material["body_file"] = relative
                elif material.get("kind") in {"file", "simulation"}:
                    content = material.pop("_asset_bytes", None)
                    if not isinstance(content, bytes):
                        raise ValueError("missing_asset_bytes")
                    if len(content) > MAX_ASSET_BYTES:
                        raise ValueError("asset_too_large")
                    filename = _safe_filename(
                        material.get("filename_original"),
                        fallback=f"{material_key}.bin",
                    )
                    relative = f"content/{container_key}/materials/{material_key}-{filename}"
                    _write_bytes(unit_root / relative, content)
                    material["asset_file"] = relative
                    material.pop("sha256", None)
                    material.pop("size_bytes", None)
                    if material.get("kind") == "simulation" and material.get("body_md") is not None:
                        body_relative = f"content/{container_key}/materials/{material_key}.md"
                        _write_text(unit_root / body_relative, str(material.pop("body_md")))
                        material["body_file"] = body_relative
            for task in container.get("tasks", []):
                task_key = _require_key(task.get("key"))
                for name, filename in TEXT_FIELDS:
                    value = task.pop(name, None)
                    if value is None:
                        continue
                    relative = f"content/{container_key}/tasks/{task_key}/{filename}"
                    _write_text(unit_root / relative, str(value))
                    task[f"{name.removesuffix('_md')}_file"] = relative
                if task.get("kind") == "h5p":
                    content = task.pop("_h5p_bytes", None)
                    digest = task.pop("h5p_sha256", None)
                    if content is None and digest is None:
                        continue
                    if not isinstance(content, bytes):
                        raise ValueError("missing_h5p_bytes")
                    h5p_digest(content)
                    relative = f"content/{container_key}/tasks/{task_key}/content.h5p"
                    _write_bytes(unit_root / relative, content)
                    task["h5p_file"] = relative
        unit["schema_version"] = SCHEMA_VERSION
        _write_yaml(unit_root / "unit.yaml", unit)


def _read_container_files(unit_root: Path, container: dict[str, Any]) -> None:
    allowed = MODULE_FIELDS if "phase" in container else SECTION_FIELDS
    _reject_unknown(container, allowed, kind="container")
    _require_key(container.get("key"))
    materials = container.get("materials", [])
    tasks = container.get("tasks", [])
    if not isinstance(materials, list) or not isinstance(tasks, list):
        raise ValueError("invalid_content_lists")
    for material in materials:
        if not isinstance(material, dict):
            raise ValueError("invalid_material")
        _reject_unknown(material, MATERIAL_FIELDS, kind="material")
        _require_key(material.get("key"))
        if material.get("kind") == "markdown":
            path = _safe_local_file(unit_root, material.pop("body_file", None))
            material["body_md"] = path.read_text(encoding="utf-8").rstrip("\n")
        elif material.get("kind") in {"file", "simulation"}:
            path = _safe_local_file(unit_root, material.pop("asset_file", None))
            if path.stat().st_size > MAX_ASSET_BYTES:
                raise ValueError("asset_too_large")
            content = path.read_bytes()
            material["_asset_bytes"] = content
            material["sha256"] = hashlib.sha256(content).hexdigest()
            material["size_bytes"] = len(content)
            body_file = material.pop("body_file", None)
            if body_file is not None:
                material["body_md"] = (
                    _safe_local_file(unit_root, body_file).read_text(encoding="utf-8").rstrip("\n")
                )
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("invalid_task")
        _reject_unknown(task, TASK_FIELDS, kind="task")
        _require_key(task.get("key"))
        for name, _filename in TEXT_FIELDS:
            field = f"{name.removesuffix('_md')}_file"
            relative = task.pop(field, None)
            if relative is None:
                task[name] = None if name != "instruction_md" else ""
                continue
            task[name] = (
                _safe_local_file(unit_root, relative).read_text(encoding="utf-8").rstrip("\n")
            )
        if task.get("kind") == "h5p":
            relative = task.pop("h5p_file", None)
            if relative is None:
                task["h5p_sha256"] = None
            else:
                path = _safe_local_file(unit_root, relative)
                if path.stat().st_size > MAX_H5P_PACKAGE_BYTES:
                    raise ValueError("h5p_package_too_large")
                content = path.read_bytes()
                task["_h5p_bytes"] = content
                task["h5p_sha256"] = h5p_digest(content)


def load_local_snapshot(root: Path, *, expected_base_url: str) -> dict[str, Any]:
    """Load and validate a mirror without following paths outside its unit roots."""

    meta = _load_yaml(root / "gustav.yaml")
    expected = {"schema_version": SCHEMA_VERSION, "base_url": expected_base_url.rstrip("/")}
    if meta != expected:
        raise ValueError("mirror_binding_mismatch")
    units_root = root / "units"
    units: dict[str, dict[str, Any]] = {}
    if units_root.exists():
        if units_root.is_symlink() or not units_root.is_dir():
            raise ValueError("unsafe_local_path")
        for unit_root in sorted(path for path in units_root.iterdir() if path.is_dir()):
            if unit_root.is_symlink():
                raise ValueError("unsafe_local_path")
            unit = _load_yaml(unit_root / "unit.yaml")
            unit_key = _require_key(unit.pop("key", unit_root.name))
            if unit_key != unit_root.name or unit.pop("schema_version", None) != SCHEMA_VERSION:
                raise ValueError("invalid_unit_manifest")
            _reject_unknown(unit, UNIT_FIELDS, kind="unit")
            unit["key"] = unit_key
            _field, containers = _containers(unit)
            phases = unit.get("phases", [])
            edges = unit.get("edges", [])
            if not isinstance(phases, list) or not isinstance(edges, list):
                raise ValueError("invalid_modular_graph")
            for phase in phases:
                if not isinstance(phase, dict):
                    raise ValueError("invalid_phase")
                _reject_unknown(phase, PHASE_FIELDS, kind="phase")
                _require_key(phase.get("key"))
            for edge in edges:
                if not isinstance(edge, dict):
                    raise ValueError("invalid_edge")
                _reject_unknown(edge, EDGE_FIELDS, kind="edge")
                _require_key(edge.get("from"))
                _require_key(edge.get("to"))
            for container in containers:
                _read_container_files(unit_root, container)
            units[unit_key] = unit
    snapshot = {"schema_version": SCHEMA_VERSION, "units": units}
    validate_snapshot(snapshot)
    return snapshot
