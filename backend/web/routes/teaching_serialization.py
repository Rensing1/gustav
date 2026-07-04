"""Response serialization helpers for Teaching route adapters."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass


def _serialize_task(t) -> dict:
    """Serialize a task object into the API response shape.

    The persistence layer still exposes some legacy flat columns such as
    `h5p_content_id`. The API contract uses nested task-kind objects, so this
    adapter normalizes both DB rows and in-memory task objects.
    """

    if is_dataclass(t):
        data = asdict(t)
    elif isinstance(t, dict):
        data = dict(t)
    else:
        data = {
            "id": getattr(t, "id", None),
            "unit_id": getattr(t, "unit_id", None),
            "section_id": getattr(t, "section_id", None),
            "instruction_md": getattr(t, "instruction_md", None),
            "criteria": getattr(t, "criteria", []),
            "teacher_context_md": getattr(t, "teacher_context_md", None),
            "due_at": getattr(t, "due_at", None),
            "max_attempts": getattr(t, "max_attempts", None),
            "position": getattr(t, "position", None),
            "created_at": getattr(t, "created_at", None),
            "updated_at": getattr(t, "updated_at", None),
        }
    kind = str(data.get("kind") or "native")
    data["kind"] = kind
    if data.get("criteria") is None:
        data["criteria"] = []
    # Normalize optional task kind configs to match the OpenAPI contract.
    if kind == "h5p":
        h5p_cfg = data.get("h5p")
        if not isinstance(h5p_cfg, dict):
            content_id = data.get("h5p_content_id")
            display_options = data.get("h5p_display_options") or {}
            if not isinstance(display_options, dict):
                display_options = {}
            h5p_cfg = {"content_id": content_id, "display_options": display_options}
        data["h5p"] = h5p_cfg
        data["visual"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["filius"] = None
    elif kind == "visual":
        visual_cfg = data.get("visual")
        data["visual"] = visual_cfg if isinstance(visual_cfg, dict) else {}
        data["h5p"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["filius"] = None
    elif kind == "scratch":
        scratch_cfg = data.get("scratch")
        data["scratch"] = scratch_cfg if isinstance(scratch_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["calliope"] = None
        data["filius"] = None
    elif kind == "calliope":
        calliope_cfg = data.get("calliope")
        data["calliope"] = calliope_cfg if isinstance(calliope_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["filius"] = None
    elif kind == "filius":
        filius_cfg = data.get("filius")
        data["filius"] = filius_cfg if isinstance(filius_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["calliope"] = None
    else:
        data.setdefault("h5p", None)
        data.setdefault("visual", None)
        data.setdefault("scratch", None)
        data.setdefault("calliope", None)
        data.setdefault("filius", None)
    # Do not expose internal storage columns; the API uses nested objects.
    data.pop("h5p_content_id", None)
    data.pop("h5p_display_options", None)
    return data


def _serialize_unit_phase(p) -> dict:
    if is_dataclass(p):
        return asdict(p)
    if isinstance(p, dict):
        return p
    return {
        "id": getattr(p, "id", None),
        "unit_id": getattr(p, "unit_id", None),
        "title": getattr(p, "title", None),
        "position": getattr(p, "position", None),
        "created_at": getattr(p, "created_at", None),
        "updated_at": getattr(p, "updated_at", None),
    }


def _serialize_unit_phase_public(p) -> dict:
    """Serialize a unit phase for public Teaching API schemas."""

    return {
        "id": p.get("id") if isinstance(p, dict) else getattr(p, "id", None),
        "unit_id": p.get("unit_id") if isinstance(p, dict) else getattr(p, "unit_id", None),
        "title": p.get("title") if isinstance(p, dict) else getattr(p, "title", None),
        "position": p.get("position") if isinstance(p, dict) else getattr(p, "position", None),
    }


def _serialize_unit_module(m) -> dict:
    """Serialize a unit module for the teacher visual editor APIs."""

    return {
        "id": m.get("id") if isinstance(m, dict) else getattr(m, "id", None),
        "unit_id": m.get("unit_id") if isinstance(m, dict) else getattr(m, "unit_id", None),
        "phase_id": m.get("phase_id") if isinstance(m, dict) else getattr(m, "phase_id", None),
        "title": m.get("title") if isinstance(m, dict) else getattr(m, "title", None),
        "position_in_phase": (
            m.get("position_in_phase") if isinstance(m, dict) else getattr(m, "position_in_phase", None)
        ),
        "required_prereq_count": (
            m.get("required_prereq_count", 0) if isinstance(m, dict) else getattr(m, "required_prereq_count", 0)
        ),
    }


def _serialize_unit_graph_edge(e) -> dict:
    """Serialize a module edge as {from, to}."""

    if isinstance(e, dict):
        if "from" in e and "to" in e:
            return {"from": e.get("from"), "to": e.get("to")}
        return {"from": e.get("from_module_id"), "to": e.get("to_module_id")}
    return {"from": getattr(e, "from", None), "to": getattr(e, "to", None)}
