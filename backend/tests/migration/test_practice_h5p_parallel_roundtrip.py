"""Real parallel completion test for token-bound H5P practice attempts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import random
from uuid import uuid4

import pytest

from backend.learning.practice.repo_db import DBPracticeRepo
from backend.learning.practice.service import PracticeService
from backend.tests.utils.db import require_db_or_skip

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402

pytestmark = pytest.mark.db_write


def _admin_dsn() -> str:
    return os.getenv("TEST_DATABASE_ADMIN_URL") or "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def _app_dsn() -> str:
    return os.getenv("DATABASE_URL") or "postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"


def test_browser_and_finished_data_complete_one_h5p_presentation_once() -> None:
    require_db_or_skip()
    student, teacher = f"practice-h5p-{uuid4()}", f"teacher-{uuid4()}"
    ids: dict[str, object] = {}
    with psycopg.connect(_admin_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("insert into public.courses (title, teacher_id, subject, grade_level, school_year_start) values ('H5P practice', %s, 'Informatik', '10', 2026) returning id", (teacher,))
            ids["course"] = cur.fetchone()[0]
            cur.execute("insert into public.course_memberships (course_id, student_id) values (%s, %s)", (ids["course"], student))
            cur.execute("insert into public.units (title, author_id, unit_type) values ('H5P practice', %s, 'modular') returning id", (teacher,))
            ids["unit"] = cur.fetchone()[0]
            cur.execute("insert into public.course_modules (course_id, unit_id, position) values (%s, %s, 1)", (ids["course"], ids["unit"]))
            cur.execute("insert into public.unit_phases (unit_id, title, position) values (%s, 'Phase', 1) returning id", (ids["unit"],))
            phase = cur.fetchone()[0]
            cur.execute("insert into public.unit_sections (unit_id, title, position) values (%s, 'H5P-Stapel', 1) returning id", (ids["unit"],))
            section = cur.fetchone()[0]
            cur.execute("insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase, module_kind) values (%s, %s, %s, 1, 'practice') returning id", (ids["unit"], section, phase))
            ids["module"] = cur.fetchone()[0]
            cur.execute("insert into public.unit_tasks (unit_id, section_id, kind, instruction_md, criteria, h5p_content_id, position) values (%s, %s, 'h5p', 'Löse die H5P-Aufgabe.', array[]::text[], 'content-1', 1) returning id", (ids["unit"], section))
            ids["task"] = cur.fetchone()[0]
        conn.commit()
    try:
        service = PracticeService(DBPracticeRepo(_app_dsn()), rng=random.Random(4))
        session = service.create_session(student, mode="exam", stacks=[{
            "course_id": str(ids["course"]), "practice_module_id": str(ids["module"])
        }])
        item = session["current_item"]
        context = service.issue_h5p_context(student, session["id"], item["id"])

        def complete() -> dict:
            local = PracticeService(DBPracticeRepo(_app_dsn()))
            return local.complete_h5p_attempt(
                student, session["id"], item["id"], score_raw=4, score_max=4,
                completion_token=context["practice_completion_token"],
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: complete(), range(2)))
        assert results[0] == results[1]
        attempt = service.get_attempt(student, results[0]["attempt_id"])
        assert attempt["classification"] == "secure"
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from public.learning_practice_attempts where session_item_id=%s", (item["id"],))
                assert cur.fetchone()[0] == 1
                cur.execute("select count(*) from public.learning_submissions where task_id=%s and student_sub=%s", (ids["task"], student))
                assert cur.fetchone()[0] == 1
                cur.execute("select review_count from public.learning_practice_states where course_id=%s and student_sub=%s and task_id=%s", (ids["course"], student, ids["task"]))
                assert cur.fetchone()[0] == 1
    finally:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("delete from public.courses where id=%s", (ids["course"],))
                cur.execute("delete from public.units where id=%s", (ids["unit"],))
            conn.commit()
