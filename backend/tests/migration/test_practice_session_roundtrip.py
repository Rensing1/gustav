"""Real database roundtrip for practice stacks, snapshots and skip semantics."""

from __future__ import annotations

import os
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib import import_module
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.learning.practice.repo_db import DBPracticeRepo
from backend.learning.practice.service import ActivePracticeSessionError, PracticeService
from backend.learning.repo_db import DBLearningRepo
from backend.tests.utils.db import require_db_or_skip

pytest.importorskip("psycopg")
import psycopg  # type: ignore  # noqa: E402

pytestmark = pytest.mark.db_write


def _admin_dsn() -> str:
    return os.getenv("TEST_DATABASE_ADMIN_URL") or "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def _app_dsn() -> str:
    return os.getenv("DATABASE_URL") or "postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"


def test_practice_due_and_exam_snapshots_are_persisted_and_skip_is_noop_for_state(monkeypatch) -> None:
    require_db_or_skip()
    student = f"practice-roundtrip-{uuid4()}"
    teacher = f"teacher-{uuid4()}"
    ids: dict[str, object] = {}
    with psycopg.connect(_admin_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into public.courses (title, teacher_id, subject, grade_level, school_year_start) values ('Practice course', %s, 'Informatik', '10', 2026) returning id",
                (teacher,),
            )
            ids["course"] = cur.fetchone()[0]
            cur.execute("insert into public.course_memberships (course_id, student_id) values (%s, %s)", (ids["course"], student))
            cur.execute("insert into public.units (title, author_id, unit_type) values ('Practice unit', %s, 'modular') returning id", (teacher,))
            ids["unit"] = cur.fetchone()[0]
            cur.execute("insert into public.course_modules (course_id, unit_id, position) values (%s, %s, 1)", (ids["course"], ids["unit"]))
            cur.execute("insert into public.unit_phases (unit_id, title, position) values (%s, 'Phase', 1) returning id", (ids["unit"],))
            ids["phase"] = cur.fetchone()[0]
            cur.execute("insert into public.unit_sections (unit_id, title, position) values (%s, 'Practice stack', 1) returning id", (ids["unit"],))
            ids["section"] = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_modules (unit_id, section_id, phase_id, position_in_phase, module_kind) values (%s, %s, %s, 1, 'practice') returning id",
                (ids["unit"], ids["section"], ids["phase"]),
            )
            ids["module"] = cur.fetchone()[0]
            cur.execute(
                "insert into public.unit_tasks (unit_id, section_id, instruction_md, criteria, teacher_context_md, model_solution_md, position) values (%s, %s, 'Aufgabe eins', array['Kriterium'], 'Kontext', 'Lösung', 1), (%s, %s, 'Aufgabe zwei', array['Kriterium'], 'Kontext', 'Lösung', 2) returning id",
                (ids["unit"], ids["section"], ids["unit"], ids["section"]),
            )
            ids["task_due"], ids["task_later"] = (row[0] for row in cur.fetchall())
            cur.execute(
                "insert into public.learning_practice_states (course_id, student_sub, task_id, stability_days, interval_seconds, due_at) values (%s, %s, %s, 2.0, 172800, %s)",
                (ids["course"], student, ids["task_later"], datetime.now(timezone.utc) + timedelta(days=2)),
            )
        conn.commit()

    try:
        service = PracticeService(DBPracticeRepo(_app_dsn()), rng=random.Random(11))
        stacks = service.list_stacks(student)
        assert len(stacks) == 1
        assert stacks[0]["practice_module_id"] == str(ids["module"])
        assert stacks[0]["task_count"] == 2
        assert stacks[0]["due_tasks_count"] == 1
        graph = DBLearningRepo(_app_dsn()).get_modular_unit_graph(
            student_sub=student,
            course_id=str(ids["course"]),
            unit_id=str(ids["unit"]),
        )
        assert graph["modules"][0]["module_kind"] == "practice"
        assert graph["modules"][0]["status"] == "open"
        assert graph["modules"][0]["due_tasks_count"] == 1

        selection = [{"course_id": str(ids["course"]), "practice_module_id": str(ids["module"])}]
        due_session = service.create_session(student, mode="due", stacks=selection)
        assert due_session["total_items"] == 1
        assert due_session["current_item"]["task_id"] == str(ids["task_due"])
        assert due_session["current_item"]["module_title"] == "Practice stack"
        assert "criteria" not in due_session["current_item"]
        assert "teacher_context_md" not in due_session["current_item"]
        assert "model_solution_md" not in due_session["current_item"]
        assert service.repo.get_session(
            student_sub="another-student", session_id=due_session["id"]
        ) is None
        with pytest.raises(ActivePracticeSessionError):
            service.create_session(student, mode="exam", stacks=selection)

        ended = service.skip_item(student, due_session["id"], due_session["current_item"]["id"])
        assert ended["status"] == "ended"
        assert ended["end_reason"] == "completed"
        assert ended["summary"] == {
            "answered_items": 0,
            "skipped_items": 1,
            "pending_items": 0,
            "classification_counts": {"secure": 0, "partial": 0, "insufficient": 0},
            "next_due_at": None,
        }
        exam_session = service.create_session(student, mode="exam", stacks=selection)
        assert exam_session["total_items"] == 2

        practice = import_module("backend.web.routes.practice")
        monkeypatch.setattr(practice, "_SERVICE", service)
        app = FastAPI()
        app.include_router(practice.practice_router)

        @app.middleware("http")
        async def authenticate(request: Request, call_next):
            request.state.user = {"sub": student, "role": "student"}
            return await call_next(request)

        attempt = service.create_native_attempt(
            student, exam_session["id"], exam_session["current_item"]["id"],
            answer_text="Antwort vor dem Wechsel", idempotency_key="before-switch",
        )
        payload = {
            "mode": "exam", "stacks": selection,
            "replace_active_session_id": exam_session["id"],
        }

        def start(body):
            with TestClient(app) as client:
                return client.post("/api/learning/practice/sessions", json=body, headers={"Origin": "http://testserver"})

        stale = start({**payload, "replace_active_session_id": str(uuid4())})
        assert (stale.status_code, stale.json()["detail"]) == (409, "practice_session_changed")
        missing = start({
            **payload,
            "stacks": [{**selection[0], "practice_module_id": str(uuid4())}],
        })
        assert missing.status_code == 404
        with psycopg.connect(_admin_dsn()) as conn:
            conn.execute(
                """
                insert into public.learning_practice_states
                  (course_id, student_sub, task_id, stability_days, interval_seconds, due_at)
                values (%s, %s, %s, 2.0, 172800, now() + interval '2 days')
                """,
                (ids["course"], student, ids["task_due"]),
            )
        empty = start({**payload, "mode": "due"})
        assert (empty.status_code, empty.json()["detail"]) == (409, "practice_no_eligible_tasks")
        assert service.get_active_session(student)["id"] == exam_session["id"]
        with psycopg.connect(_admin_dsn()) as conn:
            conn.execute(
                "delete from public.learning_practice_states where course_id=%s and student_sub=%s and task_id=%s",
                (ids["course"], student, ids["task_due"]),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(start, [payload, payload]))
        assert sorted(response.status_code for response in results) == [201, 409]
        previous = service.get_session(student, exam_session["id"])
        assert previous["end_reason"] == "stopped"
        assert service.get_attempt(student, attempt["attempt_id"])["status"] == "pending"
        exam_session = next(response.json() for response in results if response.status_code == 201)
        assert exam_session["stacks"] == selection
        assert service.get_active_session(student)["id"] == exam_session["id"]

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from public.course_memberships where course_id=%s and student_id=%s",
                    (ids["course"], student),
                )
            conn.commit()
        ended_after_access_loss = service.skip_item(
            student,
            exam_session["id"],
            exam_session["current_item"]["id"],
        )
        assert ended_after_access_loss["status"] == "ended"
        assert ended_after_access_loss["end_reason"] == "completed"

        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select count(*) from public.learning_practice_states where course_id=%s and student_sub=%s",
                    (ids["course"], student),
                )
                assert int(cur.fetchone()[0]) == 1
                cur.execute(
                    "select count(*) from public.learning_practice_session_items where session_id=%s and access_skip_reason='access_lost'",
                    (exam_session["id"],),
                )
                assert int(cur.fetchone()[0]) == 1
    finally:
        with psycopg.connect(_admin_dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("delete from public.learning_submissions where student_sub=%s", (student,))
                cur.execute("delete from public.courses where id=%s", (ids["course"],))
                cur.execute("delete from public.units where id=%s", (ids["unit"],))
            conn.commit()
