"""Teacher unit node-editor Browser-BFF route.

Why:
    The node editor read model combines unit authorization, node lookup,
    section-backed materials, and tasks. Keeping it out of app.py prevents the
    app router from becoming a mixed catalog/workspace/live-dashboard module.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.web.security.guards import has_any_role
from backend.web.routes import teaching as teaching_routes
from backend.web.routes import teaching_guards
from backend.web.routes.app_session_helpers import (
    current_user as _current_user,
    private_headers as _private_headers,
    user_payload as _user_payload,
)
from backend.web.routes.app_teacher_unit_routes import (
    _list_teacher_section_materials,
    _list_teacher_section_tasks,
    _list_teacher_unit_sections,
)


app_teacher_node_editor_router = APIRouter(tags=["App"])


@app_teacher_node_editor_router.get("/api/teaching/views/units/{unit_id}/nodes/{node_id}/editor")
async def get_teacher_unit_node_editor(request: Request, unit_id: str, node_id: str):
    """Return the shared teacher content editor read-model for a unit node."""
    user = _current_user(request)
    if user is None:
        return JSONResponse({"error": "unauthenticated"}, status_code=401, headers=_private_headers())
    if not has_any_role(user, {"teacher", "admin"}):
        return JSONResponse({"error": "forbidden"}, status_code=403, headers=_private_headers())
    if not teaching_routes._is_uuid_like(unit_id):  # type: ignore[attr-defined]
        return JSONResponse({"error": "bad_request", "detail": "invalid_unit_id"}, status_code=400, headers=_private_headers())
    if not teaching_routes._is_uuid_like(node_id):  # type: ignore[attr-defined]
        return JSONResponse({"error": "bad_request", "detail": "invalid_node_id"}, status_code=400, headers=_private_headers())

    owner_sub = str(user.get("sub") or "")
    guard = teaching_guards._guard_unit_author(
        unit_id,
        owner_sub,
        repo_provider=teaching_routes._get_repo,  # type: ignore[attr-defined]
    )
    if guard:
        return guard

    repo = teaching_routes._get_repo()  # type: ignore[attr-defined]
    unit = repo.get_unit_for_author(unit_id, owner_sub)
    if not unit:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())

    serialized_unit = teaching_routes._serialize_unit(unit)  # type: ignore[attr-defined]
    unit_type = str(serialized_unit.get("unit_type") or "linear").strip().lower() or "linear"

    node_kind = "section"
    node_title = ""
    backing_section_id = node_id
    settings: dict[str, object] = {"kind": "section"}

    if unit_type == "modular":
        repo_error = teaching_routes._require_modular_repo_methods(repo, "get_unit_module_for_author")  # type: ignore[attr-defined]
        if repo_error:
            return repo_error
        module = repo.get_unit_module_for_author(unit_id=unit_id, module_id=node_id, author_id=owner_sub)
        if not module:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
        node_kind = "module"
        node_title = str(module.get("title") or "")
        backing_section_id = str(module.get("section_id") or "")
        settings = {
            "kind": "module",
            "required_prereq_count": int(module.get("required_prereq_count") or 0),
        }
    else:
        section = next(
            (item for item in _list_teacher_unit_sections(unit_id, owner_sub) if str(item.get("id") or "") == node_id),
            None,
        )
        if not section:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=_private_headers())
        node_title = str(section.get("title") or "")

    materials = _list_teacher_section_materials(unit_id, backing_section_id, owner_sub)
    tasks = _list_teacher_section_tasks(unit_id, backing_section_id, owner_sub)

    body = {
        "user": _user_payload(user),
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
                "due_at": item.get("due_at"),
                "max_attempts": item.get("max_attempts"),
                "position": int(item.get("position") or 0),
                "kind": str(item.get("kind") or "native"),
                "h5p": item.get("h5p"),
                "visual": item.get("visual"),
                "scratch": item.get("scratch"),
                "calliope": item.get("calliope"),
            }
            for item in tasks
            if str(item.get("id") or "")
        ],
        "settings": settings,
    }
    if node_kind == "module":
        body["node"]["backing_section_id"] = backing_section_id
    return JSONResponse(body, headers=_private_headers())
