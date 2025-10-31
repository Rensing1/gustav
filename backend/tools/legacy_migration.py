"""Command line entry point for migrating legacy data into Alpha2.

Why:
    The CLI coordinates the staged import of legacy records into the Alpha2 schema.
    Phase 1 focuses on the identity mapping (legacy UUID → OIDC `sub`) so that
    subsequent migration steps can rely on consistent foreign keys.
"""
from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import click

try:  # pragma: no cover - import guard for optional dependency
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore

LEGACY_USER_ENTITY = "legacy_user"
COURSE_ENTITY = "legacy_course"
COURSE_MEMBERSHIP_ENTITY = "legacy_course_membership"
LEGACY_UNIT_ENTITY = "legacy_unit"
UNIT_SECTION_ENTITY = "legacy_unit_section"
COURSE_MODULE_ENTITY = "legacy_course_module"
SECTION_RELEASE_ENTITY = "legacy_section_release"
TARGET_USER_TABLE = "legacy_user_map"
TARGET_COURSE_TABLE = "courses"
TARGET_MEMBERSHIP_TABLE = "course_memberships"
TARGET_UNIT_TABLE = "units"
TARGET_UNIT_SECTION_TABLE = "unit_sections"
TARGET_COURSE_MODULE_TABLE = "course_modules"
TARGET_SECTION_RELEASE_TABLE = "module_section_releases"
LEGACY_MATERIAL_ENTITY = "legacy_material"
LEGACY_TASK_ENTITY = "legacy_task"
LEGACY_SUBMISSION_ENTITY = "legacy_submission"


def _ensure_psycopg() -> None:
    if psycopg is None:  # pragma: no cover - defensive branch
        click.echo("psycopg is required for the migration CLI.", err=True)
        raise click.Abort()


def _ensure_audit_structures(conn: "psycopg.Connection") -> None:
    """Create audit and mapping tables when missing (idempotent)."""
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            """
            create table if not exists public.import_audit_runs (
              id uuid primary key default gen_random_uuid(),
              source text not null,
              started_at_utc timestamptz not null default now(),
              ended_at_utc timestamptz null,
              notes text null
            );
            create table if not exists public.import_audit_mappings (
              run_id uuid not null references public.import_audit_runs(id) on delete cascade,
              entity text not null,
              legacy_id text not null,
              target_table text not null,
              target_id text null,
              status text not null check (status in ('ok','skip','conflict','error')),
              reason text null,
              created_at_utc timestamptz not null default now()
            );
            create table if not exists public.legacy_user_map (
              legacy_id uuid primary key,
              sub text unique
            );
            """
        )


def _start_run(conn: "psycopg.Connection", source: str, dry_run: bool) -> str:
    notes = "dry-run" if dry_run else None
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            """
            insert into public.import_audit_runs (source, notes)
            values (%s, %s)
            returning id
            """,
            (source, notes),
        )
        row = cur.fetchone()
    return str(row[0])


def _finish_run(conn: "psycopg.Connection", run_id: str) -> None:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "update public.import_audit_runs set ended_at_utc = now() where id = %s",
            (run_id,),
        )


def _fail_run(conn: "psycopg.Connection", run_id: str, message: str) -> None:
    """Mark an audit run as failed and record the error message.

    Kept simple: we reuse the existing 'notes' column to store the failure
    reason and close the run with 'ended_at_utc'. This avoids schema changes
    while still providing an auditable failure trail.
    """
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "update public.import_audit_runs set ended_at_utc = now(), notes = left(%s, 512) where id = %s",
            (f"failed: {message}", run_id),
        )


def _load_staging_users(conn: "psycopg.Connection") -> Sequence[Tuple[str, str]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select id::text, sub from staging.users order by id"
        )
        rows = cur.fetchall()
    return [(row[0], row[1]) for row in rows]


def _record_audit_batch(
    conn: "psycopg.Connection",
    records: Sequence[Tuple[str, str, str, str, str | None, str, str | None]],
) -> None:
    """Insert audit entries in bulk to keep logging consistent across phases."""
    if not records:
        return
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.executemany(
            """
            insert into public.import_audit_mappings
                (run_id, entity, legacy_id, target_table, target_id, status, reason)
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            records,
        )


def _record_identity_audit(
    conn: "psycopg.Connection",
    run_id: str,
    rows: Iterable[Tuple[str, str]],
    status: str,
    reason: str | None,
) -> None:
    entries = [
        (
            run_id,
            LEGACY_USER_ENTITY,
            legacy_id,
            TARGET_USER_TABLE,
            sub if status == "ok" else None,
            status,
            reason,
        )
        for legacy_id, sub in rows
    ]
    _record_audit_batch(conn, entries)


def _completed_phases(conn: "psycopg.Connection", resume_run_id: str) -> set[str]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select legacy_id from public.import_audit_mappings where run_id = %s::uuid and entity = 'phase' and status = 'ok'",
            (resume_run_id,),
        )
        rows = cur.fetchall()
    return {r[0] for r in rows}


def _mark_phase(conn: "psycopg.Connection", run_id: str, phase: str, status: str = "ok") -> None:
    _record_audit_batch(
        conn,
        [(run_id, "phase", phase, "system", None, status, None)],
    )


def _apply_identity_map(
    conn: "psycopg.Connection",
    run_id: str,
    legacy_users: Sequence[Tuple[str, str]],
    dry_run: bool,
    batch_size: int | None = None,
) -> None:
    if dry_run:
        _record_identity_audit(conn, run_id, legacy_users, status="skip", reason="dry-run")
        return

    persisted: list[Tuple[str, str]] = []
    total = len(legacy_users)
    for idx, (legacy_id, sub) in enumerate(legacy_users, start=1):
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            # Idempotent upsert keeps reruns safe when mapping already exists.
            cur.execute(
                """
                insert into public.legacy_user_map (legacy_id, sub)
                values (%s::uuid, %s)
                on conflict (legacy_id) do update set sub = excluded.sub
                """,
                (legacy_id, sub),
            )
        persisted.append((legacy_id, sub))
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … identity_map progress {idx}/{total}")
    _record_identity_audit(conn, run_id, persisted, status="ok", reason=None)


def _load_legacy_user_map(conn: "psycopg.Connection") -> dict[str, str]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute("select legacy_id::text, sub from public.legacy_user_map")
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


def _load_staging_courses(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select id::text, title, creator_id::text from staging.courses order by title"
        )
        rows = cur.fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def _load_staging_course_memberships(conn: "psycopg.Connection") -> Sequence[Tuple[str, str]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select course_id::text, student_id::text from staging.course_students order by course_id"
        )
        rows = cur.fetchall()
    return [(row[0], row[1]) for row in rows]


def _load_staging_units(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str | None]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select id::text, title, description from staging.learning_units order by title"
        )
        rows = cur.fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def _load_staging_units_with_authors(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str | None, str]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select id::text, title, description, creator_id::text from staging.learning_units order by title"
        )
        rows = cur.fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in rows]


def _load_staging_unit_sections(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str, int]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select id::text, unit_id::text, title, order_in_unit from staging.unit_sections order by title"
        )
        rows = cur.fetchall()
    return [(row[0], row[1], row[2], int(row[3])) for row in rows]


def _load_staging_course_unit_assignments(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, int | None]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select course_id::text, unit_id::text, position from staging.course_unit_assignments order by course_id, position nulls last, unit_id"
        )
        rows = cur.fetchall()
    return [(row[0], row[1], (int(row[2]) if row[2] is not None else None)) for row in rows]


def _load_staging_section_releases(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str, bool, object | None]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select course_id::text, unit_id::text, section_id::text, coalesce(visible, true), released_at from staging.section_releases"
        )
        rows = cur.fetchall()
    return [(row[0], row[1], row[2], bool(row[3]), row[4]) for row in rows]


def _apply_courses(
    conn: "psycopg.Connection",
    run_id: str,
    courses: Sequence[Tuple[str, str, str]],
    identity_map: dict[str, str],
    dry_run: bool,
    batch_size: int | None = None,
) -> set[str]:
    imported: set[str] = set()
    total = len(courses)
    for idx, (course_id, title, legacy_creator) in enumerate(courses, start=1):
        teacher_sub = identity_map.get(legacy_creator)
        if not teacher_sub:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        COURSE_ENTITY,
                        course_id,
                        TARGET_COURSE_TABLE,
                        None,
                        "conflict",
                        "missing_teacher_identity",
                    )
                ],
            )
            continue
        if dry_run:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        COURSE_ENTITY,
                        course_id,
                        TARGET_COURSE_TABLE,
                        None,
                        "skip",
                        "dry-run",
                    )
                ],
            )
            imported.add(course_id)
            continue
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """
                insert into public.courses (id, title, teacher_id)
                values (%s::uuid, %s, %s)
                on conflict (id) do update set title = excluded.title, teacher_id = excluded.teacher_id
                """,
                (course_id, title, teacher_sub),
            )
        _record_audit_batch(
            conn,
            [
                (
                    run_id,
                    COURSE_ENTITY,
                    course_id,
                    TARGET_COURSE_TABLE,
                    teacher_sub,
                    "ok",
                    None,
                )
            ],
        )
        imported.add(course_id)
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … courses progress {idx}/{total}")
    return imported


def _apply_course_memberships(
    conn: "psycopg.Connection",
    run_id: str,
    memberships: Sequence[Tuple[str, str]],
    identity_map: dict[str, str],
    available_courses: set[str],
    dry_run: bool,
    batch_size: int | None = None,
) -> None:
    total = len(memberships)
    for idx, (course_id, legacy_student) in enumerate(memberships, start=1):
        if course_id not in available_courses:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        COURSE_MEMBERSHIP_ENTITY,
                        f"{course_id}:{legacy_student}",
                        TARGET_MEMBERSHIP_TABLE,
                        None,
                        "skip",
                        "course_not_imported",
                    )
                ],
            )
            continue
        student_sub = identity_map.get(legacy_student)
        if not student_sub:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        COURSE_MEMBERSHIP_ENTITY,
                        f"{course_id}:{legacy_student}",
                        TARGET_MEMBERSHIP_TABLE,
                        None,
                        "skip",
                        "missing_student_identity",
                    )
                ],
            )
            continue
        if dry_run:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        COURSE_MEMBERSHIP_ENTITY,
                        f"{course_id}:{legacy_student}",
                        TARGET_MEMBERSHIP_TABLE,
                        None,
                        "skip",
                        "dry-run",
                    )
                ],
            )
            continue
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """
                insert into public.course_memberships (course_id, student_id)
                select %s::uuid, %s
                where not exists (
                    select 1
                    from public.course_memberships
                    where course_id = %s::uuid and student_id = %s
                )
                """,
                (course_id, student_sub, course_id, student_sub),
            )
        _record_audit_batch(
            conn,
            [
                (
                    run_id,
                    COURSE_MEMBERSHIP_ENTITY,
                    f"{course_id}:{legacy_student}",
                    TARGET_MEMBERSHIP_TABLE,
                    student_sub,
                    "ok",
                    None,
                )
            ],
        )
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … memberships progress {idx}/{total}")


def _apply_units(
    conn: "psycopg.Connection",
    run_id: str,
    units: Sequence[Tuple[str, str, str | None, str]],
    identity_map: dict[str, str],
    dry_run: bool,
    batch_size: int | None = None,
) -> set[str]:
    imported: set[str] = set()
    total = len(units)
    for idx, (unit_id, title, description, legacy_creator) in enumerate(units, start=1):
        author_sub = identity_map.get(legacy_creator)
        if not author_sub:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        LEGACY_UNIT_ENTITY,
                        unit_id,
                        TARGET_UNIT_TABLE,
                        None,
                        "conflict",
                        "missing_author_identity",
                    )
                ],
            )
            continue
        if dry_run:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        LEGACY_UNIT_ENTITY,
                        unit_id,
                        TARGET_UNIT_TABLE,
                        None,
                        "skip",
                        "dry-run",
                    )
                ],
            )
            imported.add(unit_id)
            continue
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """
                insert into public.units (id, title, summary, author_id)
                values (%s::uuid, %s, %s, %s)
                on conflict (id) do update set title = excluded.title, summary = excluded.summary, author_id = excluded.author_id
                """,
                (unit_id, title, description, author_sub),
            )
        _record_audit_batch(
            conn,
            [
                (
                    run_id,
                    LEGACY_UNIT_ENTITY,
                    unit_id,
                    TARGET_UNIT_TABLE,
                    author_sub,
                    "ok",
                    None,
                )
            ],
        )
        imported.add(unit_id)
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … units progress {idx}/{total}")
    return imported


def _apply_unit_sections(
    conn: "psycopg.Connection",
    run_id: str,
    sections: Sequence[Tuple[str, str, str, int]],
    available_units: set[str],
    dry_run: bool,
    batch_size: int | None = None,
) -> None:
    total = len(sections)
    # Track per-unit occupied and next positions to avoid unique constraint errors
    occupied: dict[str, set[int]] = {}
    next_pos_cache: dict[str, int] = {}
    for idx, (section_id, unit_id, title, position) in enumerate(sections, start=1):
        if unit_id not in available_units:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        UNIT_SECTION_ENTITY,
                        section_id,
                        TARGET_UNIT_SECTION_TABLE,
                        None,
                        "skip",
                        "unit_not_imported",
                    )
                ],
            )
            continue
        if dry_run:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        UNIT_SECTION_ENTITY,
                        section_id,
                        TARGET_UNIT_SECTION_TABLE,
                        None,
                        "skip",
                        "dry-run",
                    )
                ],
            )
            continue
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            # Determine a conflict-free position
            used = occupied.setdefault(unit_id, set())
            pos: int | None = position if isinstance(position, int) and position > 0 else None
            if unit_id not in next_pos_cache:
                cur.execute(
                    "select coalesce(max(position),0) from public.unit_sections where unit_id = %s::uuid",
                    (unit_id,),
                )
                next_pos_cache[unit_id] = int(cur.fetchone()[0]) + 1
                # Also cache already occupied positions from DB to prevent collisions
                cur.execute(
                    "select position from public.unit_sections where unit_id = %s::uuid",
                    (unit_id,),
                )
                used.update(p for (p,) in cur.fetchall())
            if pos is None or pos in used or pos <= 0:
                # ensure we pick a position beyond any occupied slot
                base = max(next_pos_cache[unit_id], (max(used) + 1) if used else 1)
                pos = base
                next_pos_cache[unit_id] = pos + 1
            used.add(pos)
            cur.execute(
                """
                insert into public.unit_sections (id, unit_id, title, position)
                values (%s::uuid, %s::uuid, %s, %s)
                on conflict (id) do update set unit_id = excluded.unit_id, title = excluded.title, position = excluded.position
                """,
                (section_id, unit_id, title, pos),
            )
        _record_audit_batch(
            conn,
            [
                (
                    run_id,
                    UNIT_SECTION_ENTITY,
                    section_id,
                    TARGET_UNIT_SECTION_TABLE,
                    unit_id,
                    "ok",
                    None,
                )
            ],
        )
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … sections progress {idx}/{total}")


def _apply_course_modules(
    conn: "psycopg.Connection",
    run_id: str,
    assignments: Sequence[Tuple[str, str, int | None]],
    dry_run: bool,
    batch_size: int | None = None,
) -> set[Tuple[str, str]]:
    processed: set[Tuple[str, str]] = set()
    from collections import defaultdict

    per_course: dict[str, list[Tuple[str, int | None]]] = defaultdict(list)
    for course_id, unit_id, pos in assignments:
        per_course[course_id].append((unit_id, pos))

    normalized: list[Tuple[str, str, int]] = []
    for course_id, items in per_course.items():
        manual = [it for it in items if it[1] is not None]
        auto = [it for it in items if it[1] is None]
        taken = {int(p) for _u, p in manual}
        next_pos = 1
        for unit_id, p in manual:
            normalized.append((course_id, unit_id, int(p)))
        for unit_id, _ in auto:
            while next_pos in taken:
                next_pos += 1
            normalized.append((course_id, unit_id, next_pos))
            taken.add(next_pos)
            next_pos += 1

    total = len(normalized)
    for idx, (course_id, unit_id, position) in enumerate(normalized, start=1):
        processed.add((course_id, unit_id))
        if dry_run:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        COURSE_MODULE_ENTITY,
                        f"{course_id}:{unit_id}",
                        TARGET_COURSE_MODULE_TABLE,
                        None,
                        "skip",
                        "dry-run",
                    )
                ],
            )
            continue
        # Guard against FK errors when staging contains entries for non-existent targets
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                "select exists(select 1 from public.courses where id = %s::uuid), exists(select 1 from public.units where id = %s::uuid)",
                (course_id, unit_id),
            )
            exists_course, exists_unit = cur.fetchone()
        if not (exists_course and exists_unit):
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        COURSE_MODULE_ENTITY,
                        f"{course_id}:{unit_id}",
                        TARGET_COURSE_MODULE_TABLE,
                        None,
                        "skip",
                        "missing_target",
                    )
                ],
            )
            continue
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """
                insert into public.course_modules (course_id, unit_id, position)
                values (%s::uuid, %s::uuid, %s)
                on conflict (course_id, unit_id) do update set position = excluded.position
                """,
                (course_id, unit_id, position),
            )
        _record_audit_batch(
            conn,
            [
                (
                    run_id,
                    COURSE_MODULE_ENTITY,
                    f"{course_id}:{unit_id}",
                    TARGET_COURSE_MODULE_TABLE,
                    None,
                    "ok",
                    None,
                )
            ],
        )
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … modules progress {idx}/{total}")
    return processed


def _apply_section_releases(
    conn: "psycopg.Connection",
    run_id: str,
    releases: Sequence[Tuple[str, str, str, bool, object | None]],
    dry_run: bool,
    batch_size: int | None = None,
) -> None:
    total = len(releases)
    for idx, (course_id, unit_id, section_id, visible, released_at) in enumerate(releases, start=1):
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                "select id::text from public.course_modules where course_id = %s::uuid and unit_id = %s::uuid",
                (course_id, unit_id),
            )
            row = cur.fetchone()
        if not row:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        SECTION_RELEASE_ENTITY,
                        f"{course_id}:{unit_id}:{section_id}",
                        TARGET_SECTION_RELEASE_TABLE,
                        None,
                        "skip",
                        "course_module_missing",
                    )
                ],
            )
            continue
        course_module_id = row[0]
        if not visible:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        SECTION_RELEASE_ENTITY,
                        f"{course_id}:{unit_id}:{section_id}",
                        TARGET_SECTION_RELEASE_TABLE,
                        None,
                        "skip",
                        "invisible",
                    )
                ],
            )
            continue
        released_by = "system"
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("select teacher_id from public.courses where id = %s::uuid", (course_id,))
            owner = cur.fetchone()
            if owner and owner[0]:
                released_by = owner[0]
        if dry_run:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        SECTION_RELEASE_ENTITY,
                        f"{course_id}:{unit_id}:{section_id}",
                        TARGET_SECTION_RELEASE_TABLE,
                        None,
                        "skip",
                        "dry-run",
                    )
                ],
            )
            continue
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """
                insert into public.module_section_releases (course_module_id, section_id, visible, released_at, released_by)
                values (%s::uuid, %s::uuid, true, coalesce(%s, now()), %s)
                on conflict (course_module_id, section_id) do update set visible = true, released_at = coalesce(excluded.released_at, public.module_section_releases.released_at), released_by = excluded.released_by
                """,
                (course_module_id, section_id, released_at, released_by),
            )
        _record_audit_batch(
            conn,
            [
                (
                    run_id,
                    SECTION_RELEASE_ENTITY,
                    f"{course_id}:{unit_id}:{section_id}",
                    TARGET_SECTION_RELEASE_TABLE,
                    course_module_id,
                    "ok",
                    None,
                )
            ],
        )
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … releases progress {idx}/{total}")

def _load_staging_materials(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str, str | None, str | None, str | None, int | None, str | None, int, object | None, str | None]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        try:
            cur.execute(
                """
                select id::text, section_id::text, kind, title, body_md, storage_key, size_bytes, sha256, position, created_at, mime_type, legacy_url
                from staging.materials_json
                order by section_id, position, id
                """
            )
        except Exception:
            # Fallback for minimal schemas: project missing columns as NULLs
            cur.execute(
                """
                select id::text,
                       section_id::text,
                       kind,
                       title,
                       body_md,
                       null::text as storage_key,
                       null::bigint as size_bytes,
                       null::text as sha256,
                       position,
                       null::timestamptz as created_at,
                       null::text as mime_type,
                       null::text as legacy_url
                from staging.materials_json
                order by section_id, position, id
                """
            )
        rows = cur.fetchall()
    return [
        (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            (int(row[6]) if row[6] is not None else None),
            row[7],
            int(row[8]),
            row[9],
            row[10],
            row[11] if len(row) > 11 else None,
        )
        for row in rows
    ]


def _apply_materials(
    conn: "psycopg.Connection",
    run_id: str,
    materials: Sequence[Tuple[str, str, str, str | None, str | None, str | None, int | None, str | None, int, object | None, str | None]],
    dry_run: bool,
    batch_size: int | None = None,
) -> None:
    total = len(materials)
    used_positions: dict[str, set[int]] = {}
    next_pos_cache: dict[str, int] = {}
    for idx, (
        mat_id,
        section_id,
        kind,
        title,
        body_md,
        storage_key,
        size_bytes,
        sha256,
        position,
        created_at,
        mime_type,
        legacy_url,
    ) in enumerate(materials, start=1):
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("select unit_id::text from public.unit_sections where id = %s::uuid", (section_id,))
            row = cur.fetchone()
        if not row:
            _record_audit_batch(
                conn,
                [(run_id, LEGACY_MATERIAL_ENTITY, mat_id, "unit_materials", None, "skip", "section_missing")],
            )
            continue
        unit_id = row[0]
        if dry_run:
            _record_audit_batch(
                conn,
                [(run_id, LEGACY_MATERIAL_ENTITY, mat_id, "unit_materials", None, "skip", "dry-run")],
            )
            continue
        # resolve conflict-free position per section
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            used = used_positions.setdefault(section_id, set())
            if section_id not in next_pos_cache:
                cur.execute("select coalesce(max(position),0) from public.unit_materials where section_id = %s::uuid", (section_id,))
                next_pos_cache[section_id] = int(cur.fetchone()[0]) + 1
                cur.execute("select position from public.unit_materials where section_id = %s::uuid", (section_id,))
                used.update(p for (p,) in cur.fetchall())
            pos = position if isinstance(position, int) and position > 0 and position not in used else None
            if pos is None:
                base = max(next_pos_cache[section_id], (max(used)+1) if used else 1)
                pos = base
                next_pos_cache[section_id] = pos + 1
            used.add(pos)

        if kind == "markdown":
            with conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute(
                    """
                    insert into public.unit_materials (id, unit_id, section_id, kind, title, body_md, position)
                    values (%s::uuid, %s::uuid, %s::uuid, 'markdown', %s, %s, %s)
                    on conflict (id) do update set title = excluded.title, body_md = excluded.body_md, position = excluded.position
                    """,
                    (mat_id, unit_id, section_id, title, body_md or '', pos),
                )
        elif kind == "file" and storage_key and size_bytes and size_bytes > 0 and sha256 and len(sha256) == 64 and mime_type in ("image/jpeg", "image/png", "image/webp", "application/pdf"):
            with conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute(
                    """
                    insert into public.unit_materials (
                      id, unit_id, section_id, kind, title, body_md, storage_key, filename_original, mime_type, size_bytes, sha256, position
                    )
                    values (
                      %s::uuid, %s::uuid, %s::uuid, 'file', %s, '', %s, %s, %s, %s, %s, %s
                    )
                    on conflict (id) do update set
                      title = excluded.title,
                      body_md = excluded.body_md,
                      storage_key = excluded.storage_key,
                      filename_original = excluded.filename_original,
                      mime_type = excluded.mime_type,
                      size_bytes = excluded.size_bytes,
                      sha256 = excluded.sha256,
                      position = excluded.position
                    """,
                    (mat_id, unit_id, section_id, title, storage_key, title, mime_type, size_bytes, sha256, pos),
                )
        else:
            note = f"Datei nicht verfügbar: {legacy_url or storage_key or ''}".strip()
            with conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute(
                    """
                    insert into public.unit_materials (id, unit_id, section_id, kind, title, body_md, position)
                    values (%s::uuid, %s::uuid, %s::uuid, 'markdown', %s, %s, %s)
                    on conflict (id) do update set title = excluded.title, body_md = excluded.body_md, position = excluded.position
                    """,
                    (mat_id, unit_id, section_id, title, note, pos),
                )
        _record_audit_batch(
            conn,
            [(run_id, LEGACY_MATERIAL_ENTITY, mat_id, "unit_materials", section_id, "ok", None)],
        )
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … materials progress {idx}/{total}")


def _load_staging_tasks(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str, list[str], str | None, int | None, int, object | None]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            "select tr.id::text, tr.section_id::text, tb.instruction_md, tb.assessment_criteria, tb.hints_md, tr.max_attempts, tr.order_in_section, tr.created_at from staging.tasks_regular tr join staging.tasks_base tb on tb.id = tr.id"
        )
        rows = cur.fetchall()
    tasks = []
    for row in rows:
        crit: list[str] = []
        seen: set[str] = set()
        raw = row[3]
        arr = []
        try:
            if raw is None:
                arr = []
            elif isinstance(raw, str):
                import json
                arr = json.loads(raw)
            else:
                arr = list(raw)
        except Exception:
            arr = []
        for x in arr:
            t = str(x).strip()
            if not t or t in seen:
                continue
            crit.append(t)
            seen.add(t)
            if len(crit) >= 10:
                break
        pos = int(row[6]) if row[6] is not None else 1
        tasks.append((row[0], row[1], row[2], crit, row[4], (int(row[5]) if row[5] is not None else None), pos, row[7]))
    return tasks


def _apply_tasks(
    conn: "psycopg.Connection",
    run_id: str,
    tasks: Sequence[Tuple[str, str, str, list[str], str | None, int | None, int, object | None]],
    dry_run: bool,
    batch_size: int | None = None,
) -> None:
    total = len(tasks)
    used_positions: dict[str, set[int]] = {}
    next_pos_cache: dict[str, int] = {}
    for idx, (tid, section_id, instruction_md, criteria, hints_md, max_attempts, position, created_at) in enumerate(tasks, start=1):
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("select unit_id::text from public.unit_sections where id = %s::uuid", (section_id,))
            row = cur.fetchone()
        if not row:
            _record_audit_batch(
                conn,
                [(run_id, LEGACY_TASK_ENTITY, tid, "unit_tasks", None, "skip", "section_missing")],
            )
            continue
        unit_id = row[0]
        if dry_run:
            _record_audit_batch(
                conn,
                [(run_id, LEGACY_TASK_ENTITY, tid, "unit_tasks", None, "skip", "dry-run")],
            )
            continue
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            used = used_positions.setdefault(section_id, set())
            if section_id not in next_pos_cache:
                cur.execute("select coalesce(max(position),0) from public.unit_tasks where section_id = %s::uuid", (section_id,))
                next_pos_cache[section_id] = int(cur.fetchone()[0]) + 1
                cur.execute("select position from public.unit_tasks where section_id = %s::uuid", (section_id,))
                used.update(p for (p,) in cur.fetchall())
            pos = position if isinstance(position, int) and position > 0 else None
            if pos is None or pos in used or pos <= 0:
                base = max(next_pos_cache[section_id], (max(used)+1) if used else 1)
                pos = base
                next_pos_cache[section_id] = pos + 1
            used.add(pos)
            cur.execute(
                """
                insert into public.unit_tasks (id, unit_id, section_id, instruction_md, criteria, hints_md, due_at, max_attempts, position, created_at)
                values (%s::uuid, %s::uuid, %s::uuid, %s, %s::text[], %s, null, %s, %s, coalesce(%s, now()))
                on conflict (id) do update set instruction_md = excluded.instruction_md, criteria = excluded.criteria, hints_md = excluded.hints_md, max_attempts = excluded.max_attempts, position = excluded.position
                """,
                (tid, unit_id, section_id, instruction_md, criteria, hints_md, max_attempts, pos, created_at),
            )
        _record_audit_batch(
            conn,
            [(run_id, LEGACY_TASK_ENTITY, tid, "unit_tasks", section_id, "ok", None)],
        )
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … tasks progress {idx}/{total}")


def _load_staging_submissions(conn: "psycopg.Connection") -> Sequence[Tuple[str, str, str, str, str | None, str | None, str | None, int | None, str | None, object]]:
    with conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(
            """
            select id::text, task_id::text, student_sub, kind, text_body, storage_key, mime_type, size_bytes, sha256, created_at
            from staging.submissions
            order by created_at asc
            """
        )
        rows = cur.fetchall()
    return [
        (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6], (int(row[7]) if row[7] is not None else None), row[8], row[9]
        )
        for row in rows
    ]


def _apply_submissions(
    conn: "psycopg.Connection",
    run_id: str,
    subs: Sequence[Tuple[str, str, str, str, str | None, str | None, str | None, int | None, str | None, object]],
    dry_run: bool,
    batch_size: int | None = None,
) -> None:
    # Helper: resolve course candidates for a given (task_id, student_sub)
    def _candidate_courses(task_id: str, student_sub: str) -> list[str]:
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """
                select distinct c.id::text
                from public.unit_tasks t
                join public.course_memberships cm on cm.student_id = %s
                join public.course_modules m on m.course_id = cm.course_id and m.unit_id = t.unit_id
                join public.module_section_releases r on r.course_module_id = m.id and r.section_id = t.section_id and coalesce(r.visible, false) = true
                join public.courses c on c.id = cm.course_id
                where t.id = %s::uuid
                """,
                (student_sub, task_id),
            )
            rows = cur.fetchall()
        return [r[0] for r in rows]

    # Attempt counters per (course_id, task_id, student)
    counters: dict[tuple[str, str, str], int] = {}

    total = len(subs)
    for idx, (sid, task_id, student, kind, text_body, storage_key, mime_type, size_bytes, sha256, created_at) in enumerate(subs, start=1):
        courses = _candidate_courses(task_id, student)
        if len(courses) != 1:
            _record_audit_batch(
                conn,
                [
                    (
                        run_id,
                        LEGACY_SUBMISSION_ENTITY,
                        sid,
                        "learning_submissions",
                        None,
                        "skip",
                        "ambiguous_course" if len(courses) > 1 else "missing_course",
                    )
                ],
            )
            continue
        course_id = courses[0]

        # Validate payload
        if kind == "text":
            if not text_body:
                _record_audit_batch(conn, [(run_id, LEGACY_SUBMISSION_ENTITY, sid, "learning_submissions", None, "skip", "invalid_payload")])
                continue
        elif kind == "image":
            ok = storage_key and mime_type in ("image/jpeg", "image/png") and size_bytes and size_bytes > 0 and sha256 and len(sha256) == 64
            if not ok:
                _record_audit_batch(conn, [(run_id, LEGACY_SUBMISSION_ENTITY, sid, "learning_submissions", None, "skip", "invalid_payload")])
                continue
        else:
            _record_audit_batch(conn, [(run_id, LEGACY_SUBMISSION_ENTITY, sid, "learning_submissions", None, "skip", "unsupported_kind")])
            continue

        # Compute attempt number
        key = (course_id, task_id, student)
        if key not in counters:
            with conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute(
                    "select coalesce(max(attempt_nr), 0) from public.learning_submissions where course_id = %s::uuid and task_id = %s::uuid and student_sub = %s",
                    (course_id, task_id, student),
                )
                counters[key] = int(cur.fetchone()[0])
        counters[key] += 1
        attempt_nr = counters[key]

        if dry_run:
            _record_audit_batch(conn, [(run_id, LEGACY_SUBMISSION_ENTITY, sid, "learning_submissions", None, "skip", "dry-run")])
            continue

        with conn.cursor() as cur:  # type: ignore[attr-defined]
            if kind == "text":
                cur.execute(
                    """
                    insert into public.learning_submissions(course_id, task_id, student_sub, kind, text_body, attempt_nr, created_at)
                    values (%s::uuid, %s::uuid, %s, 'text', %s, %s, %s)
                    on conflict (course_id, task_id, student_sub, attempt_nr) do nothing
                    """,
                    (course_id, task_id, student, text_body, attempt_nr, created_at),
                )
            else:
                cur.execute(
                    """
                    insert into public.learning_submissions(course_id, task_id, student_sub, kind, storage_key, mime_type, size_bytes, sha256, attempt_nr, created_at)
                    values (%s::uuid, %s::uuid, %s, 'image', %s, %s, %s, %s, %s, %s)
                    on conflict (course_id, task_id, student_sub, attempt_nr) do nothing
                    """,
                    (course_id, task_id, student, storage_key, mime_type, size_bytes, sha256, attempt_nr, created_at),
                )
        _record_audit_batch(conn, [(run_id, LEGACY_SUBMISSION_ENTITY, sid, "learning_submissions", course_id, "ok", None)])
        if batch_size and idx % batch_size == 0:
            click.echo(f"  … submissions progress {idx}/{total}")

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--db-dsn", required=True, help="Service-role DSN for the Alpha2 database.")
@click.option("--source", required=True, help="Identifier of the legacy backup snapshot.")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Process users without writing to legacy_user_map.",
)
@click.option(
    "--resume-run",
    type=str,
    required=False,
    help="Resume from a previous run id (UUID). Skips phases marked as completed.",
)
@click.option(
    "--batch-size",
    type=int,
    default=1000,
    show_default=True,
    help="Emit progress every N processed items.",
)
def cli(db_dsn: str, source: str, dry_run: bool, resume_run: str | None, batch_size: int) -> None:
    """Execute the Phase 1 legacy migration (identity map ingestion).

    Why:
        The CLI backfills `legacy_user_map` so later migration phases can rely on
        canonical identity references. The caller must supply a service-role DSN
        because Row Level Security would otherwise block the inserts.
    Parameters:
        db_dsn: Connection string for the Alpha2 database (service role required).
        source: Human-readable label of the legacy snapshot (stored in audit run).
        dry_run: When true, skip writes to `legacy_user_map` but record the intent.
    Behaviour:
        - Always records an audit run in `import_audit_runs`.
        - Emits an audit record per legacy user (status `ok` or `skip`).
        - Imports courses and memberships when the required identities exist.
        - Prints progress information to STDOUT so operators can monitor the run.
    """
    _ensure_psycopg()
    mode_text = "DRY-RUN" if dry_run else "LIVE"
    click.echo(f"Starting legacy migration ({mode_text})")

    run_id: str | None = None
    try:
        with psycopg.connect(db_dsn) as conn:  # type: ignore[arg-type]
            conn.autocommit = False
            # Ensure required audit structures exist before starting a run.
            # Keeps first-time executions reproducible without manual SQL.
            _ensure_audit_structures(conn)
            run_id = _start_run(conn, source, dry_run)
            click.echo(f"Run ID: {run_id}")
            completed: set[str] = set()
            if resume_run:
                try:
                    completed = _completed_phases(conn, resume_run)
                    click.echo(f"Resuming from run {resume_run}: completed phases = {', '.join(sorted(completed)) or 'none'}")
                except Exception:
                    click.echo("Warning: could not load completed phases; proceeding without resume.")
            legacy_users = _load_staging_users(conn)
            if resume_run and "identity_map" in completed:
                click.echo("Skipping phase identity_map (resume)")
            else:
                click.echo(f"Phase identity_map: {len(legacy_users)} items")
                _apply_identity_map(conn, run_id, legacy_users, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "identity_map")
                click.echo(f"Processed {len(legacy_users)} legacy users")
            identity_map = _load_legacy_user_map(conn)
            if dry_run:
                # Merge staged users so dry-run output reflects potential imports.
                identity_map = {**identity_map, **{legacy_id: sub for legacy_id, sub in legacy_users}}
            courses = _load_staging_courses(conn)
            if resume_run and "courses" in completed:
                imported_courses = set()
                click.echo("Skipping phase courses (resume)")
            else:
                click.echo(f"Phase courses: {len(courses)} items")
                imported_courses = _apply_courses(conn, run_id, courses, identity_map, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "courses")
                click.echo(f"Processed {len(imported_courses)}/{len(courses)} courses")
            memberships = _load_staging_course_memberships(conn)
            if dry_run:
                available_courses = {
                    course_id
                    for course_id, _title, legacy_teacher in courses
                    if identity_map.get(legacy_teacher)
                }
            else:
                available_courses = set(imported_courses)
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute("select id::text from public.courses")
                    existing = {row[0] for row in cur.fetchall()}
                available_courses |= existing
            if resume_run and "memberships" in completed:
                click.echo("Skipping phase memberships (resume)")
            else:
                click.echo(f"Phase memberships: {len(memberships)} items")
                _apply_course_memberships(
                    conn,
                    run_id,
                    memberships,
                    identity_map,
                    available_courses,
                    dry_run=dry_run,
                    batch_size=batch_size,
                )
                _mark_phase(conn, run_id, "memberships")
                click.echo(f"Processed {len(memberships)} course memberships (see audit for outcomes)")
            # Units & Sections
            units = _load_staging_units_with_authors(conn)
            if resume_run and "units" in completed:
                imported_units = set()
                click.echo("Skipping phase units (resume)")
            else:
                click.echo(f"Phase units: {len(units)} items")
                imported_units = _apply_units(conn, run_id, units, identity_map, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "units")
                click.echo(f"Processed {len(imported_units)}/{len(units)} units")
            sections = _load_staging_unit_sections(conn)
            if dry_run:
                available_units = {unit_id for unit_id, _t, _s, legacy_author in units if identity_map.get(legacy_author)}
            else:
                available_units = set(imported_units)
                with conn.cursor() as cur:  # type: ignore[attr-defined]
                    cur.execute("select id::text from public.units")
                    existing_units = {row[0] for row in cur.fetchall()}
                available_units |= existing_units
            if resume_run and "sections" in completed:
                click.echo("Skipping phase sections (resume)")
            else:
                click.echo(f"Phase sections: {len(sections)} items")
                _apply_unit_sections(conn, run_id, sections, available_units, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "sections")
                click.echo(f"Processed {len(sections)} unit sections (see audit for outcomes)")
            # Course modules & releases
            modules = _load_staging_course_unit_assignments(conn)
            if resume_run and "modules" in completed:
                click.echo("Skipping phase modules (resume)")
            else:
                click.echo(f"Phase modules: {len(modules)} items")
                processed_pairs = _apply_course_modules(conn, run_id, modules, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "modules")
                click.echo(f"Processed {len(processed_pairs)}/{len(modules)} course modules (pairs)")
            rels = _load_staging_section_releases(conn)
            if resume_run and "releases" in completed:
                click.echo("Skipping phase releases (resume)")
            else:
                click.echo(f"Phase releases: {len(rels)} items")
                _apply_section_releases(conn, run_id, rels, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "releases")
                click.echo(f"Processed {len(rels)} section releases (see audit for outcomes)")
            # Materials
            materials = _load_staging_materials(conn)
            if resume_run and "materials" in completed:
                click.echo("Skipping phase materials (resume)")
            else:
                click.echo(f"Phase materials: {len(materials)} items")
                _apply_materials(conn, run_id, materials, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "materials")
                click.echo(f"Processed {len(materials)} materials (see audit for outcomes)")
            # Tasks
            tasks = _load_staging_tasks(conn)
            if resume_run and "tasks" in completed:
                click.echo("Skipping phase tasks (resume)")
            else:
                click.echo(f"Phase tasks: {len(tasks)} items")
                _apply_tasks(conn, run_id, tasks, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "tasks")
                click.echo(f"Processed {len(tasks)} tasks (see audit for outcomes)")
            # Submissions
            subs = _load_staging_submissions(conn)
            if resume_run and "submissions" in completed:
                click.echo("Skipping phase submissions (resume)")
            else:
                click.echo(f"Phase submissions: {len(subs)} items")
                _apply_submissions(conn, run_id, subs, dry_run=dry_run, batch_size=batch_size)
                _mark_phase(conn, run_id, "submissions")
                click.echo(f"Processed {len(subs)} submissions (see audit for outcomes)")
            _finish_run(conn, run_id)
            if dry_run:
                click.echo("Dry-run complete; no writes were committed.")
            else:
                click.echo("Migration finished successfully.")
    except Exception as exc:  # pragma: no cover - error path
        # Best-effort: try to mark the run as failed for audit purposes
        try:
            if run_id is not None:
                with psycopg.connect(db_dsn) as conn:  # type: ignore[arg-type]
                    _fail_run(conn, run_id, str(exc))
        except Exception:
            pass
        click.echo(f"Migration failed: {exc}", err=True)
        raise click.Abort() from exc


if __name__ == "__main__":  # pragma: no cover
    cli()
