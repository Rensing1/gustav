"""HTTP adapter that maps the Teaching API to the local sync model."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from copy import deepcopy
from typing import Any, Callable
from urllib.parse import quote

from .cli import _http_bytes, _http_json, _http_multipart
from .config import GustavCLIConfig
from .sync_manifest import h5p_digest


class SyncAPIError(RuntimeError):
    """Report an API failure without including response bodies or authored data."""


def _slug(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")[:44] or "objekt"


def _new_key(title: object, remote_id: str, used: set[str]) -> str:
    suffix = re.sub(r"[^a-zA-Z0-9]", "", remote_id)[:8].lower() or "remote"
    base = f"{_slug(title)}-{suffix}"[:63].rstrip("-")
    key = base
    counter = 2
    while key in used:
        tail = f"-{counter}"
        key = f"{base[: 63 - len(tail)]}{tail}"
        counter += 1
    used.add(key)
    return key


def _key_for_remote(
    remote_id: str,
    title: object,
    mapping: dict[str, str],
) -> str:
    reverse = {str(value): str(key) for key, value in mapping.items()}
    if remote_id in reverse:
        return reverse[remote_id]
    key = _new_key(title, remote_id, set(mapping))
    mapping[key] = remote_id
    return key


class GustavSyncClient:
    """Use only documented Teaching endpoints to read and reconcile authoring data."""

    def __init__(self, config: GustavCLIConfig):
        self.config = config
        self.headers = {"Authorization": f"Bearer {config.token}"}

    def _json(self, method: str, path: str, body: object | None = None) -> Any:
        status, payload = _http_json(
            method,
            f"{self.config.base_url}{path}",
            headers=self.headers,
            json_body=body,
        )
        if status < 200 or status >= 300:
            raise SyncAPIError(f"api_request_failed:{method}:{path}:{status}")
        return payload

    def _bytes(self, path_or_url: str, *, authenticated: bool = True) -> bytes:
        url = (
            path_or_url
            if path_or_url.startswith("https://")
            else f"{self.config.base_url}{path_or_url}"
        )
        status, payload = _http_bytes(
            "GET",
            url,
            headers=self.headers if authenticated else None,
        )
        if status < 200 or status >= 300:
            raise SyncAPIError(f"byte_request_failed:{status}")
        return payload

    def read_owner_sub(self) -> str:
        """Return the opaque owner id used to bind a mirror to one teacher."""

        payload = self._json("GET", "/api/me")
        if not isinstance(payload, dict) or not str(payload.get("sub") or ""):
            raise SyncAPIError("invalid_owner_response")
        return str(payload["sub"])

    def list_units(self) -> list[dict[str, Any]]:
        """Read every authored unit instead of silently stopping at the API default."""

        units: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._json("GET", f"/api/teaching/units?limit=50&offset={offset}")
            if not isinstance(page, list) or any(not isinstance(item, dict) for item in page):
                raise SyncAPIError("invalid_units_response")
            units.extend(page)
            if len(page) < 50:
                return units
            offset += len(page)

    @staticmethod
    def _ordered(items: object) -> list[dict[str, Any]]:
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise SyncAPIError("invalid_collection_response")
        return sorted(
            items,
            key=lambda item: (
                int(item.get("position_in_phase") or item.get("position") or 0),
                str(item.get("id") or ""),
            ),
        )

    def _material(
        self,
        raw: dict[str, Any],
        *,
        unit_id: str,
        section_id: str,
        include_assets: bool,
    ) -> dict[str, Any]:
        kind = str(raw.get("kind") or "markdown")
        material: dict[str, Any] = {
            "kind": kind,
            "title": str(raw.get("title") or ""),
        }
        if kind == "markdown":
            material["body_md"] = str(raw.get("body_md") or "")
            return material
        for field in (
            "filename_original",
            "mime_type",
            "alt_text",
            "body_md",
            "sha256",
            "size_bytes",
        ):
            if raw.get(field) is not None:
                material[field] = raw[field]
        if not include_assets:
            return material
        material_id = quote(str(raw.get("id") or ""), safe="")
        if kind == "simulation":
            material["_asset_bytes"] = self._bytes(
                f"/api/teaching/units/{quote(unit_id, safe='')}/materials/{material_id}/simulation"
            )
        else:
            response = self._json(
                "GET",
                f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
                f"{quote(section_id, safe='')}/materials/{material_id}/"
                "download-url?disposition=attachment",
            )
            if not isinstance(response, dict) or not str(response.get("url") or "").startswith(
                "https://"
            ):
                raise SyncAPIError("invalid_download_url")
            material["_asset_bytes"] = self._bytes(str(response["url"]), authenticated=False)
        return material

    def _task(
        self,
        raw: dict[str, Any],
        *,
        unit_id: str,
        section_id: str,
        task_mapping: dict[str, Any],
        include_assets: bool,
    ) -> dict[str, Any]:
        kind = str(raw.get("kind") or "native")
        task: dict[str, Any] = {
            "kind": kind,
            "instruction_md": str(raw.get("instruction_md") or ""),
            "criteria": list(raw.get("criteria") or []),
            "teacher_context_md": raw.get("teacher_context_md"),
            "model_solution_md": raw.get("model_solution_md"),
            "due_at": raw.get("due_at"),
            "max_attempts": raw.get("max_attempts"),
        }
        if kind == "dialog":
            task["dialog"] = raw.get("dialog")
        elif kind in {"visual", "scratch", "calliope", "filius"}:
            task[kind] = raw.get(kind) or {}
        elif kind == "h5p":
            config = raw.get("h5p") if isinstance(raw.get("h5p"), dict) else {}
            content_id = str(config.get("content_id") or "")
            task["display_options"] = dict(config.get("display_options") or {})
            cached = task_mapping.get("h5p") if isinstance(task_mapping.get("h5p"), dict) else {}
            if (
                content_id
                and cached.get("content_id") == content_id
                and cached.get("sha256")
                and not include_assets
            ):
                task["h5p_sha256"] = str(cached["sha256"])
            elif content_id:
                content = self._bytes(
                    f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
                    f"{quote(section_id, safe='')}/tasks/"
                    f"{quote(str(raw.get('id') or ''), safe='')}/h5p/export"
                )
                digest = h5p_digest(content)
                task["h5p_sha256"] = digest
                task_mapping["h5p"] = {"content_id": content_id, "sha256": digest}
                if include_assets:
                    task["_h5p_bytes"] = content
            else:
                task["h5p_sha256"] = None
        return task

    def _content(
        self,
        *,
        unit_id: str,
        container_key: str,
        section_id: str,
        task_path: str,
        unit_mapping: dict[str, Any],
        include_assets: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        material_map = unit_mapping.setdefault("materials", {})
        task_map = unit_mapping.setdefault("tasks", {})
        materials_raw = self._ordered(
            self._json(
                "GET",
                f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
                f"{quote(section_id, safe='')}/materials",
            )
        )
        tasks_raw = self._ordered(self._json("GET", task_path))
        materials: list[dict[str, Any]] = []
        for raw in materials_raw:
            remote_id = str(raw.get("id") or "")
            scoped = {
                key.split("/", 1)[1]: value
                for key, value in material_map.items()
                if key.startswith(f"{container_key}/")
            }
            key = _key_for_remote(remote_id, raw.get("title"), scoped)
            material_map[f"{container_key}/{key}"] = remote_id
            materials.append(
                {
                    "key": key,
                    **self._material(
                        raw,
                        unit_id=unit_id,
                        section_id=section_id,
                        include_assets=include_assets,
                    ),
                }
            )
        tasks: list[dict[str, Any]] = []
        for raw in tasks_raw:
            remote_id = str(raw.get("id") or "")
            scoped = {
                key.split("/", 1)[1]: value.get("remote_id") if isinstance(value, dict) else value
                for key, value in task_map.items()
                if key.startswith(f"{container_key}/")
            }
            key = _key_for_remote(remote_id, raw.get("instruction_md"), scoped)
            mapping_key = f"{container_key}/{key}"
            existing = task_map.get(mapping_key)
            task_entry = existing if isinstance(existing, dict) else {"remote_id": remote_id}
            task_entry["remote_id"] = remote_id
            task_map[mapping_key] = task_entry
            tasks.append(
                {
                    "key": key,
                    **self._task(
                        raw,
                        unit_id=unit_id,
                        section_id=section_id,
                        task_mapping=task_entry,
                        include_assets=include_assets,
                    ),
                }
            )
        return materials, tasks

    def fetch_snapshot(
        self,
        mapping: dict[str, Any],
        *,
        include_assets: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return a canonical complete snapshot and refreshed stable-id mapping."""

        refreshed = deepcopy(mapping)
        unit_map = refreshed.setdefault("units", {})
        if not isinstance(unit_map, dict):
            raise SyncAPIError("invalid_mapping")
        unit_ids = {
            str(entry.get("remote_id")): key
            for key, entry in unit_map.items()
            if isinstance(entry, dict) and entry.get("remote_id")
        }
        units: dict[str, dict[str, Any]] = {}
        for raw_unit in self.list_units():
            unit_id = str(raw_unit.get("id") or "")
            unit_key = unit_ids.get(unit_id)
            if unit_key is None:
                unit_key = _new_key(raw_unit.get("title"), unit_id, set(unit_map))
                unit_map[unit_key] = {"remote_id": unit_id}
            unit_mapping = unit_map[unit_key]
            if not isinstance(unit_mapping, dict):
                raise SyncAPIError("invalid_mapping")
            unit: dict[str, Any] = {
                "key": unit_key,
                "unit_type": str(raw_unit.get("unit_type") or "linear"),
                "title": str(raw_unit.get("title") or ""),
                "summary": raw_unit.get("summary"),
            }
            container_map = unit_mapping.setdefault("containers", {})
            if unit["unit_type"] == "modular":
                self._populate_modular_unit(
                    unit,
                    unit_id=unit_id,
                    unit_mapping=unit_mapping,
                    container_map=container_map,
                    include_assets=include_assets,
                )
            else:
                sections: list[dict[str, Any]] = []
                for raw_section in self._ordered(
                    self._json("GET", f"/api/teaching/units/{quote(unit_id, safe='')}/sections")
                ):
                    section_id = str(raw_section.get("id") or "")
                    section_key = _key_for_remote(
                        section_id, raw_section.get("title"), container_map
                    )
                    materials, tasks = self._content(
                        unit_id=unit_id,
                        container_key=section_key,
                        section_id=section_id,
                        task_path=(
                            f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
                            f"{quote(section_id, safe='')}/tasks"
                        ),
                        unit_mapping=unit_mapping,
                        include_assets=include_assets,
                    )
                    sections.append(
                        {
                            "key": section_key,
                            "title": str(raw_section.get("title") or ""),
                            "materials": materials,
                            "tasks": tasks,
                        }
                    )
                unit["sections"] = sections
            units[unit_key] = unit
        return {"schema_version": 1, "units": units}, refreshed

    def _populate_modular_unit(
        self,
        unit: dict[str, Any],
        *,
        unit_id: str,
        unit_mapping: dict[str, Any],
        container_map: dict[str, str],
        include_assets: bool,
    ) -> None:
        graph = self._json("GET", f"/api/teaching/units/{quote(unit_id, safe='')}/modules/graph")
        if not isinstance(graph, dict):
            raise SyncAPIError("invalid_module_graph")
        phase_map = unit_mapping.setdefault("phases", {})
        phases: list[dict[str, Any]] = []
        phase_ids: dict[str, str] = {}
        for raw in self._ordered(graph.get("phases", [])):
            remote_id = str(raw.get("id") or "")
            key = _key_for_remote(remote_id, raw.get("title"), phase_map)
            phase_ids[remote_id] = key
            phases.append({"key": key, "title": str(raw.get("title") or "")})
        modules: list[dict[str, Any]] = []
        module_ids: dict[str, str] = {}
        for raw in self._ordered(graph.get("modules", [])):
            remote_id = str(raw.get("id") or "")
            key = _key_for_remote(remote_id, raw.get("title"), container_map)
            module_ids[remote_id] = key
            target = self._json(
                "GET",
                f"/api/teaching/units/{quote(unit_id, safe='')}/modules/"
                f"{quote(remote_id, safe='')}/content-target",
            )
            if not isinstance(target, dict) or not target.get("section_id"):
                raise SyncAPIError("invalid_content_target")
            section_id = str(target["section_id"])
            unit_mapping.setdefault("backing_sections", {})[key] = section_id
            materials, tasks = self._content(
                unit_id=unit_id,
                container_key=key,
                section_id=section_id,
                task_path=(
                    f"/api/teaching/units/{quote(unit_id, safe='')}/modules/"
                    f"{quote(remote_id, safe='')}/tasks"
                ),
                unit_mapping=unit_mapping,
                include_assets=include_assets,
            )
            modules.append(
                {
                    "key": key,
                    "phase": phase_ids.get(str(raw.get("phase_id") or ""), ""),
                    "title": str(raw.get("title") or ""),
                    "module_kind": str(raw.get("module_kind") or "learning"),
                    "required_prereq_count": int(raw.get("required_prereq_count") or 0),
                    "materials": materials,
                    "tasks": tasks,
                }
            )
        edges = []
        for raw in graph.get("edges", []):
            if not isinstance(raw, dict):
                raise SyncAPIError("invalid_module_graph")
            edges.append(
                {
                    "from": module_ids.get(str(raw.get("from") or ""), ""),
                    "to": module_ids.get(str(raw.get("to") or ""), ""),
                }
            )
        unit["phases"] = phases
        unit["modules"] = modules
        unit["edges"] = sorted(edges, key=lambda edge: (edge["from"], edge["to"]))

    @staticmethod
    def _by_key(items: object) -> dict[str, dict[str, Any]]:
        if not isinstance(items, list):
            return {}
        return {
            str(item.get("key")): item
            for item in items
            if isinstance(item, dict) and item.get("key")
        }

    def _upload_material(
        self,
        *,
        unit_id: str,
        section_id: str,
        material: dict[str, Any],
    ) -> str:
        content = material.get("_asset_bytes")
        if not isinstance(content, bytes):
            raise ValueError("missing_asset_bytes")
        intent = self._json(
            "POST",
            f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
            f"{quote(section_id, safe='')}/materials/upload-intents",
            {
                "kind": material["kind"],
                "filename": str(material.get("filename_original") or "upload.bin"),
                "mime_type": str(material.get("mime_type") or "application/octet-stream"),
                "size_bytes": len(content),
            },
        )
        if not isinstance(intent, dict) or not intent.get("intent_id") or not intent.get("url"):
            raise SyncAPIError("invalid_upload_intent")
        upload_status, _ = _http_bytes(
            "PUT",
            str(intent["url"]),
            headers={
                str(key): str(value) for key, value in dict(intent.get("headers") or {}).items()
            },
            data=content,
        )
        if upload_status < 200 or upload_status >= 300:
            raise SyncAPIError(f"asset_upload_failed:{upload_status}")
        finalize: dict[str, Any] = {
            "intent_id": str(intent["intent_id"]),
            "title": str(material.get("title") or ""),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        if material.get("alt_text") is not None:
            finalize["alt_text"] = material["alt_text"]
        if material.get("kind") == "simulation" and material.get("body_md") is not None:
            finalize["body_md"] = material["body_md"]
        created = self._json(
            "POST",
            f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
            f"{quote(section_id, safe='')}/materials/finalize",
            finalize,
        )
        if not isinstance(created, dict) or not created.get("id"):
            raise SyncAPIError("invalid_material_response")
        return str(created["id"])

    @staticmethod
    def _task_payload(task: dict[str, Any], *, previous_kind: str | None = None) -> dict[str, Any]:
        payload = {
            field: task.get(field)
            for field in (
                "instruction_md",
                "criteria",
                "teacher_context_md",
                "model_solution_md",
                "due_at",
                "max_attempts",
            )
        }
        kind = str(task.get("kind") or "native")
        if kind == "h5p":
            payload["h5p"] = {
                "content_id": None,
                "display_options": dict(task.get("display_options") or {}),
            }
        elif kind == "dialog":
            payload["dialog"] = task.get("dialog")
        elif kind in {"visual", "scratch", "calliope", "filius"}:
            payload[kind] = {}
        elif previous_kind and previous_kind != "native":
            payload[previous_kind] = None
        return payload

    def _import_h5p(
        self,
        *,
        unit_id: str,
        section_id: str,
        task_id: str,
        task: dict[str, Any],
    ) -> None:
        content = task.get("_h5p_bytes")
        if not isinstance(content, bytes):
            raise ValueError("missing_h5p_bytes")
        status, _body = _http_multipart(
            "POST",
            f"{self.config.base_url}/api/teaching/units/{quote(unit_id, safe='')}/sections/"
            f"{quote(section_id, safe='')}/tasks/{quote(task_id, safe='')}/h5p/import",
            headers=self.headers,
            field_name="file",
            filename="content.h5p",
            content=content,
            content_type="application/zip",
        )
        if status < 200 or status >= 300:
            raise SyncAPIError(f"h5p_import_failed:{status}")

    def _push_content(
        self,
        *,
        unit_id: str,
        container_key: str,
        section_id: str,
        local: dict[str, Any],
        remote: dict[str, Any],
        unit_mapping: dict[str, Any],
        prune: bool,
        checkpoint: Callable[[dict[str, Any]], None],
        complete_mapping: dict[str, Any],
    ) -> None:
        base = (
            f"/api/teaching/units/{quote(unit_id, safe='')}/sections/{quote(section_id, safe='')}"
        )
        material_map = unit_mapping.setdefault("materials", {})
        remote_materials = self._by_key(remote.get("materials"))
        local_materials = self._by_key(local.get("materials"))
        material_ids: list[str] = []
        for key, material in local_materials.items():
            map_key = f"{container_key}/{key}"
            remote_material = remote_materials.get(key)
            material_id = str(material_map.get(map_key) or "")
            replace = bool(
                remote_material
                and (
                    material.get("kind") != remote_material.get("kind")
                    or (
                        material.get("kind") in {"file", "simulation"}
                        and any(
                            material.get(field) != remote_material.get(field)
                            for field in ("sha256", "filename_original", "mime_type")
                        )
                    )
                )
            )
            if remote_material is None or replace:
                old_id = material_id if replace else ""
                if material.get("kind") == "markdown":
                    created = self._json(
                        "POST",
                        f"{base}/materials",
                        {"title": material.get("title"), "body_md": material.get("body_md")},
                    )
                    if not isinstance(created, dict) or not created.get("id"):
                        raise SyncAPIError("invalid_material_response")
                    material_id = str(created["id"])
                else:
                    material_id = self._upload_material(
                        unit_id=unit_id,
                        section_id=section_id,
                        material=material,
                    )
                material_map[map_key] = material_id
                checkpoint(complete_mapping)
                if old_id:
                    self._json("DELETE", f"{base}/materials/{quote(old_id, safe='')}")
            else:
                changes = {
                    field: material.get(field)
                    for field in ("title", "body_md", "alt_text")
                    if material.get(field) != remote_material.get(field)
                    and (field != "alt_text" or material.get("kind") == "file")
                }
                if changes:
                    self._json(
                        "PATCH",
                        f"{base}/materials/{quote(material_id, safe='')}",
                        changes,
                    )
            material_ids.append(material_id)
        if prune:
            for key in remote_materials.keys() - local_materials.keys():
                map_key = f"{container_key}/{key}"
                material_id = str(material_map.get(map_key) or "")
                if material_id:
                    self._json("DELETE", f"{base}/materials/{quote(material_id, safe='')}")
                material_map.pop(map_key, None)
        if material_ids:
            self._json("POST", f"{base}/materials/reorder", {"material_ids": material_ids})

        task_map = unit_mapping.setdefault("tasks", {})
        remote_tasks = self._by_key(remote.get("tasks"))
        local_tasks = self._by_key(local.get("tasks"))
        task_ids: list[str] = []
        for key, task in local_tasks.items():
            map_key = f"{container_key}/{key}"
            entry = task_map.get(map_key)
            if not isinstance(entry, dict):
                entry = {"remote_id": str(entry or "")}
                task_map[map_key] = entry
            task_id = str(entry.get("remote_id") or "")
            remote_task = remote_tasks.get(key)
            payload = self._task_payload(
                task,
                previous_kind=str(remote_task.get("kind") or "native") if remote_task else None,
            )
            if remote_task is None:
                created = self._json("POST", f"{base}/tasks", payload)
                if not isinstance(created, dict) or not created.get("id"):
                    raise SyncAPIError("invalid_task_response")
                task_id = str(created["id"])
                entry["remote_id"] = task_id
                checkpoint(complete_mapping)
            else:
                remote_payload = self._task_payload(remote_task)
                changes = {
                    field: value
                    for field, value in payload.items()
                    if value != remote_payload.get(field)
                }
                if changes:
                    self._json("PATCH", f"{base}/tasks/{quote(task_id, safe='')}", changes)
            if task.get("kind") == "h5p" and (
                remote_task is None or task.get("h5p_sha256") != remote_task.get("h5p_sha256")
            ):
                self._import_h5p(
                    unit_id=unit_id,
                    section_id=section_id,
                    task_id=task_id,
                    task=task,
                )
                entry["h5p"] = {"sha256": task.get("h5p_sha256")}
            task_ids.append(task_id)
        if prune:
            for key in remote_tasks.keys() - local_tasks.keys():
                map_key = f"{container_key}/{key}"
                entry = task_map.get(map_key)
                task_id = str(entry.get("remote_id") if isinstance(entry, dict) else entry or "")
                if task_id:
                    self._json("DELETE", f"{base}/tasks/{quote(task_id, safe='')}")
                task_map.pop(map_key, None)
        if task_ids:
            self._json("POST", f"{base}/tasks/reorder", {"task_ids": task_ids})

    def _push_linear(
        self,
        *,
        unit_id: str,
        local: dict[str, Any],
        remote: dict[str, Any],
        unit_mapping: dict[str, Any],
        mapping: dict[str, Any],
        prune: bool,
        checkpoint: Callable[[dict[str, Any]], None],
    ) -> None:
        container_map = unit_mapping.setdefault("containers", {})
        remote_sections = self._by_key(remote.get("sections"))
        local_sections = self._by_key(local.get("sections"))
        section_ids: list[str] = []
        for key, section in local_sections.items():
            section_id = str(container_map.get(key) or "")
            remote_section = remote_sections.get(key)
            if remote_section is None:
                created = self._json(
                    "POST",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/sections",
                    {"title": section.get("title")},
                )
                if not isinstance(created, dict) or not created.get("id"):
                    raise SyncAPIError("invalid_section_response")
                section_id = str(created["id"])
                container_map[key] = section_id
                checkpoint(mapping)
            elif section.get("title") != remote_section.get("title"):
                self._json(
                    "PATCH",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
                    f"{quote(section_id, safe='')}",
                    {"title": section.get("title")},
                )
            self._push_content(
                unit_id=unit_id,
                container_key=key,
                section_id=section_id,
                local=section,
                remote=remote_section or {"materials": [], "tasks": []},
                unit_mapping=unit_mapping,
                prune=prune,
                checkpoint=checkpoint,
                complete_mapping=mapping,
            )
            section_ids.append(section_id)
        if prune:
            for key in remote_sections.keys() - local_sections.keys():
                section_id = str(container_map.get(key) or "")
                if section_id:
                    self._json(
                        "DELETE",
                        f"/api/teaching/units/{quote(unit_id, safe='')}/sections/"
                        f"{quote(section_id, safe='')}",
                    )
                container_map.pop(key, None)
        if section_ids:
            self._json(
                "POST",
                f"/api/teaching/units/{quote(unit_id, safe='')}/sections/reorder",
                {"section_ids": section_ids},
            )

    def push_snapshot(
        self,
        local: dict[str, Any],
        remote: dict[str, Any],
        mapping: dict[str, Any],
        *,
        prune: bool,
        checkpoint: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Reconcile the remote side in dependency order and checkpoint new ids."""

        refreshed = deepcopy(mapping)
        unit_map = refreshed.setdefault("units", {})
        local_units = local.get("units", {})
        remote_units = remote.get("units", {})
        if not isinstance(local_units, dict) or not isinstance(remote_units, dict):
            raise ValueError("invalid_units")
        for key, unit in local_units.items():
            if not isinstance(unit, dict):
                raise ValueError("invalid_unit")
            entry = unit_map.get(key)
            if not isinstance(entry, dict):
                entry = {}
                unit_map[key] = entry
            unit_id = str(entry.get("remote_id") or "")
            remote_unit = remote_units.get(key)
            if remote_unit is None:
                created = self._json(
                    "POST",
                    "/api/teaching/units",
                    {
                        "title": unit.get("title"),
                        "summary": unit.get("summary"),
                        "unit_type": unit.get("unit_type"),
                    },
                )
                if not isinstance(created, dict) or not created.get("id"):
                    raise SyncAPIError("invalid_unit_response")
                unit_id = str(created["id"])
                entry["remote_id"] = unit_id
                checkpoint(refreshed)
                remote_unit = {
                    "unit_type": unit.get("unit_type"),
                    "title": unit.get("title"),
                    "summary": unit.get("summary"),
                    "sections": [],
                }
            elif unit.get("unit_type") != remote_unit.get("unit_type"):
                raise ValueError("immutable_unit_type")
            changes = {
                field: unit.get(field)
                for field in ("title", "summary")
                if unit.get(field) != remote_unit.get(field)
            }
            if changes:
                self._json(
                    "PATCH",
                    f"/api/teaching/units/{quote(unit_id, safe='')}",
                    changes,
                )
            if unit.get("unit_type") == "modular":
                self._push_modular(
                    unit_id=unit_id,
                    local=unit,
                    remote=remote_unit,
                    unit_mapping=entry,
                    mapping=refreshed,
                    prune=prune,
                    checkpoint=checkpoint,
                )
            else:
                self._push_linear(
                    unit_id=unit_id,
                    local=unit,
                    remote=remote_unit,
                    unit_mapping=entry,
                    mapping=refreshed,
                    prune=prune,
                    checkpoint=checkpoint,
                )
        if prune:
            for key in remote_units.keys() - local_units.keys():
                entry = unit_map.get(key)
                unit_id = str(entry.get("remote_id") if isinstance(entry, dict) else "")
                if unit_id:
                    self._json("DELETE", f"/api/teaching/units/{quote(unit_id, safe='')}")
                unit_map.pop(key, None)
        checkpoint(refreshed)
        return refreshed

    def _push_modular(
        self,
        *,
        unit_id: str,
        local: dict[str, Any],
        remote: dict[str, Any],
        unit_mapping: dict[str, Any],
        mapping: dict[str, Any],
        prune: bool,
        checkpoint: Callable[[dict[str, Any]], None],
    ) -> None:
        phase_map = unit_mapping.setdefault("phases", {})
        remote_phases = self._by_key(remote.get("phases"))
        local_phases = self._by_key(local.get("phases"))
        phase_ids: list[str] = []
        for key, phase in local_phases.items():
            phase_id = str(phase_map.get(key) or "")
            if key not in remote_phases:
                created = self._json(
                    "POST",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/phases",
                    {"title": phase.get("title")},
                )
                if not isinstance(created, dict) or not created.get("id"):
                    raise SyncAPIError("invalid_phase_response")
                phase_id = str(created["id"])
                phase_map[key] = phase_id
                checkpoint(mapping)
            elif phase.get("title") != remote_phases[key].get("title"):
                self._json(
                    "PATCH",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/phases/"
                    f"{quote(phase_id, safe='')}",
                    {"title": phase.get("title")},
                )
            phase_ids.append(phase_id)
        if phase_ids:
            self._json(
                "POST",
                f"/api/teaching/units/{quote(unit_id, safe='')}/phases/reorder",
                {"phase_ids": phase_ids},
            )

        container_map = unit_mapping.setdefault("containers", {})
        backing = unit_mapping.setdefault("backing_sections", {})
        remote_modules = self._by_key(remote.get("modules"))
        local_modules = self._by_key(local.get("modules"))
        for key, module in local_modules.items():
            module_id = str(container_map.get(key) or "")
            remote_module = remote_modules.get(key)
            phase_id = str(phase_map.get(str(module.get("phase") or "")) or "")
            if not phase_id:
                raise ValueError("unknown_phase_key")
            if remote_module is None:
                created = self._json(
                    "POST",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/modules",
                    {
                        "phase_id": phase_id,
                        "title": module.get("title"),
                        "module_kind": module.get("module_kind", "learning"),
                    },
                )
                if not isinstance(created, dict) or not created.get("id"):
                    raise SyncAPIError("invalid_module_response")
                module_id = str(created["id"])
                container_map[key] = module_id
                target = self._json(
                    "GET",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/modules/"
                    f"{quote(module_id, safe='')}/content-target",
                )
                if not isinstance(target, dict) or not target.get("section_id"):
                    raise SyncAPIError("invalid_content_target")
                backing[key] = str(target["section_id"])
                checkpoint(mapping)
            else:
                if module.get("module_kind") != remote_module.get("module_kind"):
                    raise ValueError("immutable_module_kind")
                changes = {
                    field: module.get(field)
                    for field in ("title", "required_prereq_count")
                    if module.get(field) != remote_module.get(field)
                }
                if changes:
                    self._json(
                        "PATCH",
                        f"/api/teaching/units/{quote(unit_id, safe='')}/modules/"
                        f"{quote(module_id, safe='')}",
                        changes,
                    )
            section_id = str(backing.get(key) or "")
            if not section_id:
                raise ValueError("missing_backing_section")
            self._push_content(
                unit_id=unit_id,
                container_key=key,
                section_id=section_id,
                local=module,
                remote=remote_module or {"materials": [], "tasks": []},
                unit_mapping=unit_mapping,
                prune=prune,
                checkpoint=checkpoint,
                complete_mapping=mapping,
            )
        desired_edges = {
            (str(edge.get("from")), str(edge.get("to")))
            for edge in local.get("edges", [])
            if isinstance(edge, dict)
        }
        remote_edges = {
            (str(edge.get("from")), str(edge.get("to")))
            for edge in remote.get("edges", [])
            if isinstance(edge, dict)
        }
        for source, target in sorted(desired_edges - remote_edges):
            self._json(
                "POST",
                f"/api/teaching/units/{quote(unit_id, safe='')}/modules/edges",
                {
                    "from_module_id": container_map[source],
                    "to_module_id": container_map[target],
                },
            )
        if prune:
            for source, target in sorted(remote_edges - desired_edges):
                self._json(
                    "DELETE",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/modules/"
                    f"{quote(str(container_map[source]), safe='')}/edges/"
                    f"{quote(str(container_map[target]), safe='')}",
                )
            for key in remote_modules.keys() - local_modules.keys():
                module_id = str(container_map.get(key) or "")
                if module_id:
                    self._json(
                        "DELETE",
                        f"/api/teaching/units/{quote(unit_id, safe='')}/modules/"
                        f"{quote(module_id, safe='')}",
                    )
                container_map.pop(key, None)
                backing.pop(key, None)
            for key in remote_phases.keys() - local_phases.keys():
                phase_id = str(phase_map.get(key) or "")
                if phase_id:
                    self._json(
                        "DELETE",
                        f"/api/teaching/units/{quote(unit_id, safe='')}/phases/"
                        f"{quote(phase_id, safe='')}",
                    )
                phase_map.pop(key, None)
        for phase_key in local_phases:
            module_ids = [
                str(container_map[module_key])
                for module_key, module in local_modules.items()
                if module.get("phase") == phase_key
            ]
            if module_ids:
                self._json(
                    "POST",
                    f"/api/teaching/units/{quote(unit_id, safe='')}/phases/"
                    f"{quote(str(phase_map[phase_key]), safe='')}/modules/reorder",
                    {"module_ids": module_ids},
                )
