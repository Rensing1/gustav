"""Real database roundtrip for native practice evaluation and one retry."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import random
from uuid import uuid4

import pytest

from backend.learning.practice.completion import complete_worker_practice_attempt
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


def _analysis(score: int, *, max_score: int = 10) -> dict:
    return {
        "schema": "criteria.v2",
        "criteria_results": [
            {"criterion": "Kriterium", "score": score, "max_score": max_score, "explanation_md": "Test"}
        ],
    }


def test_native_attempt_completion_solution_and_supported_retry_are_atomic() -> None:
    require_db_or_skip()
    student, teacher = f"practice-native-{uuid4()}", f"teacher-{uuid4()}"
    ids: dict[str, object] = {}
    with psycopg.connect(_admin_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.courses (title, teacher_id, subject, grade_level, school_year_start) values ('Native practice', %s, 'Informatik', '10', 2026) returning id",
                (teacher,),
            )
            ids["course"] = cur.fetchone()[0]
            cur.execute("insert into public.course_memberships (course_id, student_id) values (%s, %s)", (ids["course"], student))
            cur.execute("insert into public.units (title, author_id, unit_type) values ('Native practice', %s, 'modular') returning id", (teacher,))
            ids["unit"] = cur.fetchone()[0]
            cur.execute("insert into public.course_modules (course_id, unit_id, position) values (%s, %s, 1)", (ids["course"], ids["unit"]))
            cur.execute("insert into public.unit_phases (unit_id, title, position) values (%s, 'Phase', 1) returning id", (ids["unit"],))
            ids["phase"] = cur.fetchone()[0]
            cur.execute("insert into public.unit_sections (unit_id, title, position) values (%s, 'Stapel', 1) returning id", (ids["unit"],))
            ids["section"] = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase, module_kind) values (%s, %s, %s, 1, 'practice') returning id",
                (ids["unit"], ids["section"], ids["phase"]),
            )
            ids["module"] = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, teacher_context_md, model_solution_md, position) values (%s, %s, 'Erkläre den Test.', array['Kriterium'], 'Interner Kontext', 'Musterlösung', 1) returning id",
                (ids["unit"], ids["section"]),
            )
            ids["task"] = cur.fetchone()[0]
        conn.commit()

    try:
        service = PracticeService(DBPracticeRepo(_app_dsn()), rng=random.Random(3))
        session = service.create_session(
            student,
            mode="exam",
            stacks=[{"course_id": str(ids["course"]), "practice_module_id": str(ids["module"])}],
        )
        item = session["current_item"]
        assert item["module_title"] == "Stapel"
        assert "criteria" not in item
        assert item["latest_attempt_id"] is None
        def submit_once(answer: str) -> dict:
            local_service = PracticeService(DBPracticeRepo(_app_dsn()))
            return local_service.create_native_attempt(
                student,
                session["id"],
                item["id"],
                answer_text=answer,
                idempotency_key="native-attempt-1",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit_once, ["Erster Versuch", "Paralleler Request"]))
        assert results[0] == results[1]
        accepted = results[0]
        assert service.get_session(student, session["id"])["current_item"][
            "latest_attempt_id"
        ] == accepted["attempt_id"]
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select count(*), count(submission_id) from public.learning_practice_attempts where session_item_id=%s::uuid",
                    (item["id"],),
                )
                assert cur.fetchone() == (1, 1)
                cur.execute(
                    "select count(*) from public.learning_submission_jobs where submission_id=%s::uuid",
                    (_submission_id(conn, accepted["attempt_id"]),),
                )
                assert cur.fetchone()[0] == 1

        with psycopg.connect(_admin_dsn()) as conn:
            with pytest.raises(ValueError, match="invalid_practice_analysis"):
                complete_worker_practice_attempt(
                    conn=conn,
                    submission_id=_submission_id(conn, accepted["attempt_id"]),
                    analysis_json=_analysis(6, max_score=9),
                    feedback_md="Ungültige Auswertung",
                )
            conn.rollback()
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select count(*) from public.learning_practice_states where course_id=%s and student_sub=%s and task_id=%s",
                    (ids["course"], student, ids["task"]),
                )
                assert cur.fetchone()[0] == 0

        with psycopg.connect(_admin_dsn()) as conn:
            complete_worker_practice_attempt(
                conn=conn,
                submission_id=_submission_id(conn, accepted["attempt_id"]),
                analysis_json=_analysis(10),
                feedback_md="Sicher gelöst.",
            )
            conn.commit()
        completed = service.get_attempt(student, accepted["attempt_id"])
        assert completed["status"] == "completed"
        assert completed["classification"] == "secure"
        first_due = completed["due_at"]

        assert service.reveal_solution(student, session["id"], item["id"]) == {
            "model_solution_md": "Musterlösung"
        }
        retry_session = service.continue_session(student, session["id"])
        assert retry_session["current_item"]["presentation_number"] == 2
        second = service.create_native_attempt(
            student,
            session["id"],
            item["id"],
            answer_text="Zweiter Versuch",
            idempotency_key="native-attempt-2",
        )
        assert service.get_session(student, session["id"])["current_item"][
            "latest_attempt_id"
        ] == second["attempt_id"]
        with psycopg.connect(_admin_dsn()) as conn:
            complete_worker_practice_attempt(
                conn=conn,
                submission_id=_submission_id(conn, second["attempt_id"]),
                analysis_json=_analysis(10),
                feedback_md="Jetzt sitzt es.",
            )
            conn.commit()
        supported = service.get_attempt(student, second["attempt_id"])
        assert supported["classification"] == "partial"
        assert supported["due_at"] == first_due
        ended = service.continue_session(student, session["id"])
        assert ended["status"] == "ended"
        assert ended["end_reason"] == "completed"
        assert ended["summary"]["answered_items"] == 1
        assert ended["summary"]["skipped_items"] == 0
        assert ended["summary"]["pending_items"] == 0
        assert ended["summary"]["classification_counts"] == {
            "secure": 0,
            "partial": 1,
            "insufficient": 0,
        }
        assert ended["summary"]["next_due_at"] == first_due
    finally:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("delete from public.courses where id=%s", (ids["course"],))
                cur.execute("delete from public.units where id=%s", (ids["unit"],))
            conn.commit()


def _submission_id(conn, attempt_id: str) -> str:  # noqa: ANN001
    with conn.cursor() as cur:
        cur.execute("select submission_id::text from public.learning_practice_attempts where id=%s::uuid", (attempt_id,))
        return str(cur.fetchone()[0])
