"""Exercise Live practice aggregation and owner boundaries against migrated Postgres."""

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.tests.utils.db import require_db_or_skip

pytestmark = pytest.mark.db_write


def test_live_practice_counts_access_and_membership_are_scoped() -> None:
    require_db_or_skip()
    owner, learner, second = (f"live-practice-{uuid4()}" for _ in range(3))
    dsn = os.getenv("TEST_DATABASE_ADMIN_URL") or "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        try:
            cur = conn.cursor()
            cur.execute("insert into public.courses (title, teacher_id, subject, grade_level, school_year_start) values ('Live test', %s, 'Test', '10', 2026) returning id", (owner,))
            course = cur.fetchone()["id"]
            cur.execute("insert into public.units (title, author_id, unit_type) values ('Live test', %s, 'modular') returning id", (owner,))
            unit = cur.fetchone()["id"]
            cur.execute("insert into public.course_modules (course_id, unit_id, position) values (%s, %s, 1)", (course, unit))
            cur.execute("insert into public.course_memberships (course_id, student_id) values (%s, %s), (%s, %s)", (course, learner, course, second))
            cur.execute("insert into public.unit_phases (unit_id, title, position) values (%s, 'Phase', 1) returning id", (unit,))
            phase = cur.fetchone()["id"]
            modules = []
            sections = []
            for position, kind in enumerate(["learning", "practice"], 1):
                cur.execute("insert into public.unit_sections (unit_id, title, position) values (%s, %s, %s) returning id", (unit, kind, position))
                section = cur.fetchone()["id"]
                sections.append(section)
                cur.execute("insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase, module_kind) values (%s, %s, %s, %s, %s) returning id", (unit, section, phase, position, kind))
                modules.append(cur.fetchone()["id"])
            # The unfinished learning task can later lock the practice module.
            cur.execute("insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, position) values (%s, %s, 'Start', array['Kriterium'], 1)", (unit, sections[0]))
            for position, classification in enumerate([None, "secure", "secure", "partial", "insufficient"], 1):
                cur.execute("insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, teacher_context_md, model_solution_md, position) values (%s, %s, 'Übung', array['Kriterium'], 'Kontext', 'Lösung', %s) returning id", (unit, sections[1], position))
                task = cur.fetchone()["id"]
                if classification:
                    days = -1 if position == 2 else 1
                    cur.execute("insert into public.learning_practice_states (course_id, student_sub, task_id, stability_days, interval_seconds, due_at, last_attempt_at, last_classification) values (%s, %s, %s, 1, 86400, now() + %s * interval '1 day', now(), %s)", (course, learner, task, days, classification))

            def read(*, identity=owner, claimed_owner=owner, unit_id=unit, students=None):
                cur.execute("select set_config('app.current_sub', %s, true)", (identity,))
                cur.execute("select * from public.get_unit_live_practice_aggregates_for_owner(%s, %s, %s, %s)", (claimed_owner, course, unit_id, students if students is not None else [learner]))
                result = cur.fetchall()
                return result

            row, = read()
            assert row["module_id"] == modules[1]
            assert row["task_count"] == 5
            assert [row[key] for key in ("due_tasks_count", "secure_tasks_count", "partial_tasks_count", "insufficient_tasks_count")] == [2, 1, 1, 1]
            assert row["latest_activity_at"] is not None
            assert row["next_due_at"] is not None
            assert len(read(students=[learner, second, learner, "nonmember"])) == 2
            assert read(students=[]) == []
            assert read(identity=second) == []
            assert read(identity="other-teacher", claimed_owner="other-teacher") == []
            assert read(unit_id=uuid4()) == []
            cur.execute("insert into public.unit_module_edges (unit_id, from_module_id, to_module_id) values (%s, %s, %s)", (unit, modules[0], modules[1]))
            cur.execute("update public.unit_modules set required_prereq_count=1 where id=%s", (modules[1],))
            locked, = read()
            assert locked["access_status"] == "locked"
            assert [locked[key] for key in ("due_tasks_count", "secure_tasks_count", "partial_tasks_count", "insufficient_tasks_count")] == [0, 0, 0, 0]
            cur.execute("delete from public.course_memberships where course_id=%s and student_id=%s", (course, learner))
            assert read() == []
        finally:
            # No synthetic fixture survives this test, even on assertion failure.
            conn.rollback()
