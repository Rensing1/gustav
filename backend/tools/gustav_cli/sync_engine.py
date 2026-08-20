"""Pure comparison helpers for directional CLI synchronization.

The functions in this module know nothing about HTTP or the filesystem. Keeping
the three-way comparison pure makes the data-loss guard easy to test and teach.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ChangeOrigin(str, Enum):
    """Describe which side changed since the last successful synchronization."""

    CLEAN = "clean"
    LOCAL = "local"
    REMOTE = "remote"
    DIVERGED = "diverged"


@dataclass(frozen=True)
class SnapshotComparison:
    """Result of comparing a local and remote snapshot with their shared base."""

    origin: ChangeOrigin
    base_digest: str
    local_digest: str
    remote_digest: str


def _json_safe(value: Any) -> Any:
    """Remove transport-only values before hashing semantic authoring data."""

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, bytes):
        return {"sha256": hashlib.sha256(value).hexdigest(), "size_bytes": len(value)}
    return value


def snapshot_digest(snapshot: object) -> str:
    """Return a deterministic SHA-256 digest without logging authored content."""

    payload = json.dumps(
        _json_safe(snapshot),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compare_digests(base_digest: str, local_digest: str, remote_digest: str) -> SnapshotComparison:
    """Classify drift using only digests, so the state file stores no raw content."""

    local_changed = local_digest != base_digest
    remote_changed = remote_digest != base_digest
    if local_digest == remote_digest:
        origin = ChangeOrigin.CLEAN
    elif local_changed and remote_changed:
        origin = ChangeOrigin.DIVERGED
    elif local_changed:
        origin = ChangeOrigin.LOCAL
    elif remote_changed:
        origin = ChangeOrigin.REMOTE
    else:
        origin = ChangeOrigin.DIVERGED
    return SnapshotComparison(origin, base_digest, local_digest, remote_digest)


def compare_snapshots(base: object, local: object, remote: object) -> SnapshotComparison:
    """Classify complete in-memory snapshots against a shared basis."""

    return compare_digests(
        snapshot_digest(base),
        snapshot_digest(local),
        snapshot_digest(remote),
    )


def _keys(items: object) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {str(item.get("key")) for item in items if isinstance(item, dict) and item.get("key")}


def _items_by_key(items: object) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("key")): item for item in items if isinstance(item, dict) and item.get("key")
    }


def requires_prune(source: dict[str, Any], target: dict[str, Any]) -> bool:
    """Return whether making `target` equal `source` would remove an authored object."""

    source_units = source.get("units", {})
    target_units = target.get("units", {})
    if not isinstance(source_units, dict) or not isinstance(target_units, dict):
        raise ValueError("invalid_units")
    if set(target_units) - set(source_units):
        return True
    for unit_key in set(source_units) & set(target_units):
        source_unit = source_units[unit_key]
        target_unit = target_units[unit_key]
        if not isinstance(source_unit, dict) or not isinstance(target_unit, dict):
            raise ValueError("invalid_unit")
        for field in ("sections", "phases", "modules"):
            if _keys(target_unit.get(field)) - _keys(source_unit.get(field)):
                return True
        container_field = "modules" if source_unit.get("unit_type") == "modular" else "sections"
        source_containers = {
            str(item.get("key")): item
            for item in source_unit.get(container_field, [])
            if isinstance(item, dict) and item.get("key")
        }
        target_containers = {
            str(item.get("key")): item
            for item in target_unit.get(container_field, [])
            if isinstance(item, dict) and item.get("key")
        }
        for key in set(source_containers) & set(target_containers):
            for field in ("materials", "tasks"):
                if _keys(target_containers[key].get(field)) - _keys(
                    source_containers[key].get(field)
                ):
                    return True
            source_materials = _items_by_key(source_containers[key].get("materials"))
            target_materials = _items_by_key(target_containers[key].get("materials"))
            for material_key in set(source_materials) & set(target_materials):
                desired = source_materials[material_key]
                existing = target_materials[material_key]
                if desired.get("kind") != existing.get("kind"):
                    return True
                if desired.get("kind") in {"file", "simulation"} and any(
                    desired.get(field) != existing.get(field)
                    for field in ("sha256", "filename_original", "mime_type")
                ):
                    return True
        if source_unit.get("unit_type") == "modular":
            source_edges = {
                (str(item.get("from")), str(item.get("to")))
                for item in source_unit.get("edges", [])
                if isinstance(item, dict)
            }
            target_edges = {
                (str(item.get("from")), str(item.get("to")))
                for item in target_unit.get("edges", [])
                if isinstance(item, dict)
            }
            if target_edges - source_edges:
                return True
    return False
