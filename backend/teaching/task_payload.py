"""Normalize persisted task configurations without HTTP dependencies."""

from dataclasses import asdict, is_dataclass


def serialize_task(t) -> dict:
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
            "model_solution_md": getattr(t, "model_solution_md", None),
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
        data["dialog"] = None
    elif kind == "visual":
        visual_cfg = data.get("visual")
        data["visual"] = visual_cfg if isinstance(visual_cfg, dict) else {}
        data["h5p"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["filius"] = None
        data["dialog"] = None
    elif kind == "scratch":
        scratch_cfg = data.get("scratch")
        data["scratch"] = scratch_cfg if isinstance(scratch_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["calliope"] = None
        data["filius"] = None
        data["dialog"] = None
    elif kind == "calliope":
        calliope_cfg = data.get("calliope")
        data["calliope"] = calliope_cfg if isinstance(calliope_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["filius"] = None
        data["dialog"] = None
    elif kind == "filius":
        filius_cfg = data.get("filius")
        data["filius"] = filius_cfg if isinstance(filius_cfg, dict) else {}
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["dialog"] = None
    elif kind == "dialog":
        dialog_cfg = data.get("dialog")
        data["dialog"] = dialog_cfg if isinstance(dialog_cfg, dict) else None
        data["h5p"] = None
        data["visual"] = None
        data["scratch"] = None
        data["calliope"] = None
        data["filius"] = None
    else:
        data.setdefault("h5p", None)
        data.setdefault("visual", None)
        data.setdefault("scratch", None)
        data.setdefault("calliope", None)
        data.setdefault("filius", None)
        data.setdefault("dialog", None)
    # Do not expose internal storage columns; the API uses nested objects.
    data.pop("h5p_content_id", None)
    data.pop("h5p_display_options", None)
    return data
