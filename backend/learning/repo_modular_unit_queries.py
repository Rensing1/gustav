"""Modular-unit read queries for the Learning repository.

Why:
    Modular units have a dense read surface: graph state, released sections,
    material/task payloads, and fail-closed H5P access checks. Keeping these
    SQL queries out of DBLearningRepo lets the repository facade stay readable
    while preserving the existing public method contracts.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

try:  # pragma: no cover -- optional dependency mirrors repo_db import behavior
    from psycopg import Connection
except Exception:  # pragma: no cover
    Connection = Any  # type: ignore


def get_modular_unit_graph(repo, *, psycopg_module, student_sub: str, course_id: str, unit_id: str) -> dict:
    """Return a modular unit graph payload (phases/modules/edges) for a student.

    Notes:
        Unlock/done logic is computed purely from:
        - graph metadata (`unit_modules`, `unit_phases`, `unit_module_edges`)
        - safe per-section counts (`unit_sections.tasks_total/materials_count`)
        - the student's own submissions (`learning_submissions.section_id`)

        This avoids joining `unit_tasks` for locked modules, which would
        leak content details under RLS.
    """

    course_uuid = str(UUID(course_id))
    unit_uuid = str(UUID(unit_id))
    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            # RLS context
            repo._set_current_sub(cur, student_sub)
            repo._set_current_course_id(cur, course_uuid)

            # Course membership + unit-in-course guard (404 semantics)
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise LookupError("not_course_member")
            cur.execute(
                "select exists(select 1 from public.course_modules where course_id=%s and unit_id=%s)",
                (course_uuid, unit_uuid),
            )
            if not bool(cur.fetchone()[0]):
                raise LookupError("unit_not_in_course")

            cur.execute(
                "select id::text, title, unit_type from public.units where id = %s",
                (unit_uuid,),
            )
            unit_row = cur.fetchone()
            if not unit_row:
                raise LookupError("unit_not_found")
            unit_type = str(unit_row[2] or "").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                """
                select id::text, title, position
                from public.unit_phases
                where unit_id = %s
                order by position asc, id asc
                """,
                (unit_uuid,),
            )
            phases = [{"id": r[0], "title": r[1], "position": int(r[2])} for r in (cur.fetchall() or [])]

            cur.execute(
                """
                select um.id::text,
                       um.section_id::text,
                       us.title,
                       um.phase_id::text,
                       p.position as phase_position,
                       um.position_in_phase,
                       um.required_prereq_count,
                       us.tasks_total,
                       us.materials_count
                  from public.unit_modules um
                  join public.unit_sections us on us.id = um.section_id
                  join public.unit_phases p on p.id = um.phase_id
                 where um.unit_id = %s
                 order by p.position asc, um.position_in_phase asc, um.id asc
                """,
                (unit_uuid,),
            )
            modules_raw: list[dict] = []
            for r in (cur.fetchall() or []):
                modules_raw.append(
                    {
                        "id": r[0],
                        "section_id": r[1],
                        "title": r[2],
                        "phase_id": r[3],
                        "phase_position": int(r[4] or 1),
                        "position_in_phase": int(r[5] or 1),
                        "required_prereq_count": int(r[6] or 0),
                        "tasks_total": int(r[7] or 0),
                        "materials_count": int(r[8] or 0),
                    }
                )

            cur.execute(
                """
                select from_module_id::text, to_module_id::text
                from public.unit_module_edges
                where unit_id = %s
                order by from_module_id asc, to_module_id asc
                """,
                (unit_uuid,),
            )
            edges = [{"from": r[0], "to": r[1]} for r in (cur.fetchall() or [])]
            module_state = fetch_modular_unit_module_states(
                cur=cur,
                student_sub=student_sub,
                course_uuid=course_uuid,
                unit_uuid=unit_uuid,
            )
            visible_material_counts: dict[str, int] = {}
            for module in modules_raw:
                state = module_state.get(module["id"], {})
                status = str(state.get("status") or "locked")
                if status not in {"open", "done"}:
                    continue
                if int(module["materials_count"] or 0) > 0:
                    continue
                section_id = str(module["section_id"] or "")
                if not section_id or section_id in visible_material_counts:
                    continue
                cur.execute(
                    """
                    select count(*)::int
                      from public.get_released_materials_for_student(%s, %s::uuid, %s::uuid)
                    """,
                    (student_sub, course_uuid, section_id),
                )
                visible_material_counts[section_id] = int((cur.fetchone() or [0])[0] or 0)

            modules: list[dict] = []
            for m in modules_raw:
                s = module_state.get(m["id"], {})
                section_id = str(m["section_id"] or "")
                materials_count = int(m["materials_count"] or 0)
                if str(s.get("status") or "locked") in {"open", "done"}:
                    materials_count = visible_material_counts.get(section_id, materials_count)
                modules.append(
                    {
                        "id": m["id"],
                        "title": m["title"],
                        "phase_id": m["phase_id"],
                        "position_in_phase": int(m["position_in_phase"]),
                        "required_prereq_count": int(s.get("required_prereq_count", m["required_prereq_count"]) or 0),
                        "prereq_done": int(s.get("prereq_done") or 0),
                        "prereq_required": int(s.get("prereq_required") or 0),
                        "tasks_done": int(s.get("tasks_done") or 0),
                        "tasks_total": int(s.get("tasks_total", m["tasks_total"]) or 0),
                        "materials_count": materials_count,
                        "status": str(s.get("status") or "locked"),
                    }
                )

    return {
        "unit": {"id": unit_row[0], "title": unit_row[1], "unit_type": unit_type},
        "phases": phases,
        "modules": modules,
        "edges": edges,
    }

def fetch_modular_unit_module_states(
    *,
    cur,
    student_sub: str,
    course_uuid: str,
    unit_uuid: str,
) -> dict[str, dict]:
    """Fetch per-module unlock states from the single SQL source of truth."""
    cur.execute(
        """
        select module_id::text,
               section_id::text,
               required_prereq_count,
               prereq_required,
               prereq_done,
               tasks_total,
               tasks_done,
               status
          from public.get_modular_unit_module_states_for_student(%s, %s::uuid, %s::uuid)
        """,
        (student_sub, course_uuid, unit_uuid),
    )
    rows = cur.fetchall() or []
    state: dict[str, dict] = {}
    for r in rows:
        module_id = str(r[0] or "")
        if not module_id:
            continue
        state[module_id] = {
            "section_id": str(r[1] or ""),
            "required_prereq_count": int(r[2] or 0),
            "prereq_required": int(r[3] or 0),
            "prereq_done": int(r[4] or 0),
            "tasks_total": int(r[5] or 0),
            # `tasks_done` semantics are defined in SQL:
            # non-H5P task -> any submission; H5P task -> full score only.
            "tasks_done": int(r[6] or 0),
            "status": str(r[7] or "locked"),
        }
    return state

def is_modular_section_open_or_done(
    repo,
    *,
    cur,
    course_uuid: str,
    student_sub: str,
    unit_uuid: str,
    section_uuid: str,
) -> bool:
    """Return True if a modular section's module is open/done for the student.

    Why:
        For modular units, we must not accept submissions for tasks in locked
        modules (even if a client knows the task_id). Otherwise students could
        bypass the intended progression by submitting to hidden tasks.

    Notes:
        - For linear units this helper is not used (releases are checked elsewhere).
        - This runs under RLS with `app.current_sub` and `app.current_course_id`
          already set by the caller.
    """
    # Keep linear units permissive (this helper only gates modular unlocks).
    cur.execute(
        """
        select exists(
                 select 1
                   from public.unit_modules um
                   join public.units u on u.id = um.unit_id
                  where um.unit_id = %s::uuid
                    and um.section_id = %s::uuid
                    and u.unit_type = 'modular'
               )
        """,
        (unit_uuid, section_uuid),
    )
    if not bool((cur.fetchone() or [False])[0]):
        return True

    cur.execute(
        "select public.modular_section_is_open_or_done_for_student(%s, %s::uuid, %s::uuid, %s::uuid)",
        (student_sub, course_uuid, unit_uuid, section_uuid),
    )
    return bool((cur.fetchone() or [False])[0])

def get_modular_module_content(
    repo,
    *,
    psycopg_module,
    student_sub: str,
    course_id: str,
    unit_id: str,
    module_id: str,
    include_materials: bool,
    include_tasks: bool,
) -> dict:
    """Return module content for modular units (materials/tasks) when accessible."""
    course_uuid = str(UUID(course_id))
    unit_uuid = str(UUID(unit_id))
    module_uuid = str(UUID(module_id))
    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            # RLS context
            repo._set_current_sub(cur, student_sub)
            repo._set_current_course_id(cur, course_uuid)

            # Course membership + unit-in-course guard (404 semantics)
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise LookupError("not_course_member")
            cur.execute(
                "select exists(select 1 from public.course_modules where course_id=%s and unit_id=%s)",
                (course_uuid, unit_uuid),
            )
            if not bool(cur.fetchone()[0]):
                raise LookupError("unit_not_in_course")

            # Defense-in-depth: route already enforces modular-only, but keep
            # the repo method safe when called directly.
            cur.execute("select unit_type from public.units where id = %s", (unit_uuid,))
            unit_row = cur.fetchone()
            if not unit_row:
                raise LookupError("unit_not_found")
            unit_type = str(unit_row[0] or "").strip().lower()
            if unit_type != "modular":
                raise ValueError("invalid_unit_type")

            cur.execute(
                """
                select um.id::text,
                       um.section_id::text,
                       us.title,
                       um.unit_id::text,
                       um.phase_id::text,
                       um.position_in_phase
                  from public.unit_modules um
                  join public.unit_sections us on us.id = um.section_id
                 where um.id = %s
                   and um.unit_id = %s
                """,
                (module_uuid, unit_uuid),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError("module_not_found")

            # Locked modules are intentionally indistinguishable from missing modules.
            # This prevents enumeration via guessed module_ids.
            module_state = fetch_modular_unit_module_states(
                cur=cur,
                student_sub=student_sub,
                course_uuid=course_uuid,
                unit_uuid=unit_uuid,
            )
            # Fail closed: all state lookups use canonical UUID strings.
            status = str((module_state.get(module_uuid) or {}).get("status") or "locked")
            if status == "locked":
                raise LookupError("module_locked")

            section_id = row[1]
            module = {
                "id": row[0],
                "title": row[2],
                "unit_id": row[3],
                "phase_id": row[4],
                "position_in_phase": int(row[5] or 1),
            }

            materials: list[dict] = []
            tasks: list[dict] = []
            if include_materials:
                cur.execute(
                    """
                    select id::text,
                           title,
                           kind,
                           body_md,
                           mime_type,
                           size_bytes,
                           filename_original,
                           alt_text,
                           position,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                      from public.unit_materials
                     where section_id = %s::uuid
                     order by position asc, id asc
                    """,
                    (section_id,),
                )
                for r in (cur.fetchall() or []):
                    materials.append(
                        {
                            "id": r[0],
                            "title": r[1],
                            "kind": r[2],
                            "body_md": r[3],
                            "mime_type": r[4],
                            "size_bytes": r[5],
                            "filename_original": r[6],
                            "alt_text": r[7],
                            "position": int(r[8]) if r[8] is not None else None,
                            "created_at": r[9],
                            "updated_at": r[10],
                        }
                    )

            if include_tasks:
                cur.execute(
                    """
                    select id::text,
                           instruction_md,
                           criteria,
                           case
                             when due_at is null then null
                             else to_char(due_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                           end as due_at_iso,
                           max_attempts,
                           kind,
                           h5p_content_id,
                           h5p_display_options,
                           position,
                           to_char(created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"'),
                           to_char(updated_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
                      from public.unit_tasks
                     where section_id = %s::uuid
                     order by position asc, id asc
                    """,
                    (section_id,),
                )
                for r in (cur.fetchall() or []):
                    kind = str(r[5] or "native")
                    h5p_content_id = r[6]
                    h5p_display_options = r[7]
                    display_options = h5p_display_options if isinstance(h5p_display_options, dict) else {}
                    h5p = None
                    visual = None
                    if kind == "h5p":
                        h5p = {
                            "content_id": (str(h5p_content_id) if h5p_content_id is not None else None),
                            "display_options": display_options,
                        }
                    elif kind == "visual":
                        visual = {}
                    tasks.append(
                        {
                            "id": r[0],
                            "instruction_md": r[1],
                            "criteria": list(r[2] or []),
                            "due_at": r[3],
                            "max_attempts": r[4],
                            "kind": kind,
                            "h5p": h5p,
                            "visual": visual,
                            "position": int(r[8]) if r[8] is not None else None,
                            "created_at": r[9],
                            "updated_at": r[10],
                        }
                    )

            if include_tasks and tasks:
                summaries = repo._task_submission_summary_map(
                    conn,
                    student_sub=student_sub,
                    course_id=course_uuid,
                    task_ids=[str(task["id"]) for task in tasks],
                )
                for task in tasks:
                    task.update(
                        summaries.get(
                            str(task["id"]),
                            {
                                "has_submission": False,
                                "latest_submission_intent": None,
                                "latest_submission_analysis_status": None,
                                "latest_submission_created_at": None,
                                "latest_final_submission_at": None,
                            },
                        )
                    )

    return {"module": module, "materials": materials, "tasks": tasks}

# ------------------------------------------------------------------
def list_released_sections(
    repo,
    *,
    psycopg_module,
    student_sub: str,
    course_id: str,
    include_materials: bool,
    include_tasks: bool,
    limit: int,
    offset: int,
) -> list[dict]:
    course_uuid = str(UUID(course_id))
    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            # RLS: set caller identity for membership check and all subsequent helpers
            repo._set_current_sub(cur, student_sub)
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise PermissionError("not_course_member")

            repo._set_current_sub(cur, student_sub)
            cur.execute(
                """
                select section_id::text,
                       section_title,
                       section_position,
                       unit_id::text,
                       course_module_id::text
                  from public.get_released_sections_for_student(%s, %s, %s, %s)
                """,
                (student_sub, course_uuid, int(limit), int(offset)),
            )
            rows = cur.fetchall()

        if not rows:
            raise LookupError("no_released_sections")

        sections: list[dict] = []
        for row in rows:
            section_id = row[0]
            unit_id = row[3]
            entry = {
                "section": {
                    "id": section_id,
                    "title": row[1],
                    # Contract requires integer ≥ 1; fall back to 1 if DB position is NULL
                    "position": int(row[2]) if row[2] is not None else 1,
                    # Expose owning unit to allow UI grouping/filtering per unit page.
                    "unit_id": unit_id,
                },
                "materials": [],
                "tasks": [],
            }
            if include_materials:
                entry["materials"] = fetch_materials(repo, conn, student_sub, course_uuid, section_id)
            if include_tasks:
                entry["tasks"] = fetch_tasks(repo, conn, student_sub, course_uuid, section_id)
            sections.append(entry)
        return sections

def fetch_materials(repo, conn: Connection, student_sub: str, course_id: str, section_id: str) -> list[dict]:
    with conn.cursor() as cur:
        repo._set_current_sub(cur, student_sub)
        cur.execute(
            """
            select id::text,
                   title,
                   kind,
                   body_md,
                   mime_type,
                   size_bytes,
                   filename_original,
                   alt_text,
                   material_position,
                   created_at_iso,
                   updated_at_iso
              from public.get_released_materials_for_student(%s, %s, %s)
            """,
            (student_sub, course_id, section_id),
        )
        rows = cur.fetchall()
    materials: list[dict] = []
    for row in rows:
        materials.append(
            {
                "id": row[0],
                "title": row[1],
                "kind": row[2],
                "body_md": row[3],
                "mime_type": row[4],
                "size_bytes": row[5],
                "filename_original": row[6],
                "alt_text": row[7],
                "position": int(row[8]) if row[8] is not None else None,
                "created_at": row[9],
                "updated_at": row[10],
            }
        )
    return materials

def fetch_tasks(repo, conn: Connection, student_sub: str, course_id: str, section_id: str) -> list[dict]:
    with conn.cursor() as cur:
        repo._set_current_sub(cur, student_sub)
        cur.execute(
            """
            select id::text,
                   instruction_md,
                   criteria,
                   due_at_iso,
                   max_attempts,
                   kind,
                   h5p_content_id,
                   h5p_display_options,
                   task_position,
                   created_at_iso,
                   updated_at_iso
              from public.get_released_tasks_for_student(%s, %s, %s)
            """,
            (student_sub, course_id, section_id),
        )
        rows = cur.fetchall()
    tasks: list[dict] = []
    for row in rows:
        kind = str(row[5] or "native")
        h5p_content_id = row[6]
        h5p_display_options = row[7]
        display_options = h5p_display_options if isinstance(h5p_display_options, dict) else {}
        h5p = None
        visual = None
        if kind == "h5p":
            h5p = {"content_id": (str(h5p_content_id) if h5p_content_id is not None else None), "display_options": display_options}
        elif kind == "visual":
            visual = {}
        tasks.append(
            {
                "id": row[0],
                "instruction_md": row[1],
                "criteria": list(row[2] or []),
                "due_at": row[3],
                "max_attempts": row[4],
                "kind": kind,
                "h5p": h5p,
                "visual": visual,
                "position": int(row[8]) if row[8] is not None else None,
                "created_at": row[9],
                "updated_at": row[10],
            }
        )
    if tasks:
        summaries = repo._task_submission_summary_map(
            conn,
            student_sub=student_sub,
            course_id=course_id,
            task_ids=[str(task["id"]) for task in tasks],
        )
        for task in tasks:
            task.update(
                summaries.get(
                    str(task["id"]),
                    {
                        "has_submission": False,
                        "latest_submission_intent": None,
                        "latest_submission_analysis_status": None,
                        "latest_submission_created_at": None,
                        "latest_final_submission_at": None,
                    },
                )
            )
    return tasks

def list_released_sections_by_unit(
    repo,
    *,
    psycopg_module,
    student_sub: str,
    course_id: str,
    unit_id: str,
    include_materials: bool,
    include_tasks: bool,
    limit: int,
    offset: int,
) -> list[dict]:
    """List released sections for a specific unit (student scope).

    Security:
        Validates that the student is a member of the course and that the
        unit belongs to the course (via course_modules). Uses a dedicated
        SQL helper for efficient server-side filtering.
    """
    course_uuid = str(UUID(course_id))
    unit_uuid = str(UUID(unit_id))
    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            repo._set_current_sub(cur, student_sub)
            # Ensure membership exists
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool(cur.fetchone()[0]):
                raise PermissionError("not_course_member")

            # Verify that the unit belongs to the course from the student's perspective
            cur.execute(
                """
                select exists (
                         select 1
                           from public.get_course_units_for_student(%s, %s) t
                          where t.unit_id = %s
                       )
                """,
                (student_sub, course_uuid, unit_uuid),
            )
            if not bool(cur.fetchone()[0]):
                raise LookupError("unit_not_in_course")

            # Fetch released sections for the unit (may be empty)
            cur.execute(
                """
                select section_id::text,
                       section_title,
                       section_position,
                       unit_id::text,
                       course_module_id::text
                  from public.get_released_sections_for_student_by_unit(%s, %s, %s, %s, %s)
                """,
                (student_sub, course_uuid, unit_uuid, int(limit), int(offset)),
            )
            rows = cur.fetchall()

        # Unit-scoped: return an empty list when no sections are released
        sections: list[dict] = []
        for row in rows:
            section_id = row[0]
            entry = {
                "section": {
                    "id": section_id,
                    "title": row[1],
                    # Fallback to 1 if NULL to satisfy contract >= 1
                    "position": int(row[2]) if row[2] is not None else 1,
                    "unit_id": row[3],
                },
                "materials": [],
                "tasks": [],
            }
            if include_materials:
                entry["materials"] = fetch_materials(repo, conn, student_sub, course_uuid, section_id)
            if include_tasks:
                entry["tasks"] = fetch_tasks(repo, conn, student_sub, course_uuid, section_id)
            sections.append(entry)
        return sections

def is_h5p_content_released_for_student(repo, *, psycopg_module, student_sub: str, course_id: str, content_id: str) -> bool:
    """Return True when the student may access this H5P content in the course.

    Why:
        The H5P sidecar needs a small, fail-closed authorization check to
        prevent enumeration of all released tasks/IDs and to avoid fragile
        pagination in the browser-facing service.

    Security:
        - Enforces membership via course_memberships.
        - Enforces release visibility via module_section_releases.visible.
        - Restricts to `unit_tasks.kind='h5p'` and matching `h5p_content_id`.
        - Runs under gustav_limited with `app.current_sub` set.
    """
    course_uuid = str(UUID(course_id))
    with psycopg_module.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            repo._set_current_sub(cur, student_sub)
            # Course-scoped context is required for modular unit access checks
            # (student_can_access_section uses app.current_course_id).
            repo._set_current_course_id(cur, course_uuid)

            # Fail-closed: unauthenticated or non-member callers must not be able
            # to probe which H5P content IDs exist.
            cur.execute(
                "select exists(select 1 from public.course_memberships where course_id=%s and student_id=%s)",
                (course_uuid, student_sub),
            )
            if not bool((cur.fetchone() or [False])[0]):
                return False

            # A content_id can theoretically be reused across tasks/units.
            # Allow access if ANY matching H5P task is accessible in this course.
            cur.execute(
                """
                select t.unit_id::text,
                       t.section_id::text,
                       u.unit_type,
                       m.id::text as course_module_id
                  from public.course_modules m
                  join public.unit_tasks t on t.unit_id = m.unit_id
                  join public.units u on u.id = t.unit_id
                 where m.course_id = %s::uuid
                   and t.kind = 'h5p'
                   and t.h5p_content_id = %s
                """,
                (course_uuid, str(content_id)),
            )
            candidates = cur.fetchall() or []
            if not candidates:
                return False

            for unit_id, section_id, unit_type, course_module_id in candidates:
                norm_type = str(unit_type or "").strip().lower()
                if norm_type == "linear":
                    cur.execute(
                        """
                        select exists(
                                 select 1
                                   from public.module_section_releases r
                                  where r.course_module_id = %s::uuid
                                    and r.section_id = %s::uuid
                                    and coalesce(r.visible, false) = true
                               )
                        """,
                        (course_module_id, section_id),
                    )
                    if bool((cur.fetchone() or [False])[0]):
                        return True
                elif norm_type == "modular":
                    cur.execute(
                        "select public.modular_section_is_open_or_done_for_student(%s, %s::uuid, %s::uuid, %s::uuid)",
                        (student_sub, course_uuid, unit_id, section_id),
                    )
                    if bool((cur.fetchone() or [False])[0]):
                        return True

            return False
