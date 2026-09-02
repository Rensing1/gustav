"""
Teaching API — Live Unit Summary (RED)

Contract-first tests for the new live unit summary endpoint that powers the
teacher's classroom view. These tests intentionally fail until the endpoint
is implemented according to the OpenAPI contract and Clean Architecture.

Covers:
- AuthZ: 401 unauthenticated; 403 wrong role or non-owner; 404 unit not in course
- Happy path: minimal status matrix (has_submission true/false)
- Headers: private, no-store + Vary: Origin on 200
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
import importlib
import pytest
import psycopg
from psycopg import errors as psy_errors
import httpx
from httpx import ASGITransport

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

main = importlib.import_module("backend.web.main")


@pytest.fixture(autouse=True)
def _fresh_session_store(monkeypatch: pytest.MonkeyPatch) -> None:
    install_session_store(monkeypatch, main)


def _session_store():
    return main.RUNTIME.session_store


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title, "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit", unit_type: str | None = None) -> dict:
    payload: dict = {"title": title}
    if unit_type is not None:
        payload["unit_type"] = unit_type
    r = await client.post("/api/teaching/units", json=payload)
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Abschnitt") -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_task(client: httpx.AsyncClient, unit_id: str, section_id: str, instruction: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction, "criteria": ["Kriterium 1"], "max_attempts": 3},
    )
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


@pytest.mark.anyio
async def test_summary_requires_auth_and_owner_role():
    async with (await _client()) as c:
        # Unauthenticated → 401
        r_unauth = await c.get(
            "/api/teaching/courses/00000000-0000-0000-0000-000000000000/units/00000000-0000-0000-0000-000000000000/submissions/summary"
        )
        assert r_unauth.status_code == 401

    # Student → 403
    student = _session_store().create(sub="s-live-unauth", name="S", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_forbidden = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/submissions/summary"
        )
        assert r_forbidden.status_code == 403

    # Owner vs non-owner
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = _session_store().create(sub="t-live-owner", name="Owner", roles=["teacher"])  # type: ignore
    other = _session_store().create(sub="t-live-other", name="Other", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        course_id = await _create_course(c, "Kurs Live")
        unit = await _create_unit(c, "Einheit U")
        # Not attached to course → 404
        r_404 = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/summary"
        )
        assert r_404.status_code in (403, 404)

        # Attach, then non-owner should get 403
        await _attach_unit(c, course_id, unit["id"])
        c.cookies.set(main.SESSION_COOKIE_NAME, other.session_id)
        r_non_owner = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/summary"
        )
        assert r_non_owner.status_code == 403

        # Invalid UUIDs → 400
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_bad = await c.get(
            "/api/teaching/courses/not-a-uuid/units/also-not-a-uuid/submissions/summary"
        )
        assert r_bad.status_code == 400


@pytest.mark.anyio
async def test_summary_rejects_pagination_outside_the_documented_bounds():
    teacher = _session_store().create(sub="t-live-pagination", name="Owner", roles=["teacher"])  # type: ignore
    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        response = await client.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/submissions/summary",
            params={"limit": 0, "offset": -1},
        )

    assert response.status_code == 400
    assert response.json() == {"error": "bad_request", "detail": "invalid_pagination"}


@pytest.mark.anyio
async def test_summary_rejects_non_integer_pagination_privately():
    teacher = _session_store().create(sub="t-live-pagination-text", name="Owner", roles=["teacher"])  # type: ignore
    async with (await _client()) as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        response = await client.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/submissions/summary",
            params={"limit": "abc"},
        )

    assert response.status_code == 400
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert response.json() == {"error": "bad_request", "detail": "invalid_pagination"}


@pytest.mark.anyio
async def test_summary_happy_path_minimal_status_matrix_and_headers():
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for live summary test")

    owner = _session_store().create(sub="t-live-matrix", name="Owner", roles=["teacher"])  # type: ignore
    s1 = _session_store().create(sub="s-live-1", name="Anna", roles=["student"])  # type: ignore
    s2 = _session_store().create(sub="s-live-2", name="Ben", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Live Kurs")
        unit = await _create_unit(c, "Live Einheit")
        sec1 = await _create_section(c, unit["id"], "S1")
        sec2 = await _create_section(c, unit["id"], "S2")
        t1 = await _create_task(c, unit["id"], sec1["id"], "### A1")
        t2 = await _create_task(c, unit["id"], sec2["id"], "### A2")
        mod = await _attach_unit(c, cid, unit["id"])
        # Enroll students
        await _add_member(c, cid, s1.sub)
        await _add_member(c, cid, s2.sub)

        # Student 1 submits for task 1
        # Release section S1 so submissions are allowed
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_vis = await c.patch(
            f"/api/teaching/courses/{cid}/modules/{mod['id']}/sections/{sec1['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        # Switch to student and submit
        c.cookies.set(main.SESSION_COOKIE_NAME, s1.session_id)
        r_sub = await c.post(
            f"/api/learning/courses/{cid}/tasks/{t1['id']}/submissions",
            json={"kind": "text", "text_body": "Meine Lösung"},
        )
        # Submissions are now async → 202 Accepted when enqueued/pending
        assert r_sub.status_code in (202, 201, 200)

        # Owner fetches summary
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "private, no-store"
        assert r.headers.get("Vary") == "Origin"
        body = r.json()
        assert isinstance(body.get("cursor"), str) and body["cursor"]
        assert sorted([t["id"] for t in body["tasks"]]) == sorted([t1["id"], t2["id"]])
        assert len(body["rows"]) == 2
        # Map by student sub for easier checks
        rows = {row["student"]["sub"]: row for row in body["rows"]}
        assert rows[s1.sub]
        assert rows[s2.sub]
        # S1 has submission in t1, none in t2
        s1_cells = {c["task_id"]: c for c in rows[s1.sub]["tasks"]}
        assert s1_cells[t1["id"]]["has_submission"] is True
        assert s1_cells[t2["id"]]["has_submission"] is False
        # S2 has nothing
        s2_cells = {c["task_id"]: c for c in rows[s2.sub]["tasks"]}
        assert s2_cells[t1["id"]]["has_submission"] is False
        assert s2_cells[t2["id"]]["has_submission"] is False


@pytest.mark.anyio
async def test_summary_cursor_can_seed_delta_for_new_changes_even_when_host_clock_is_ahead(monkeypatch):
    """The summary cursor must not jump ahead of later DB-visible submission changes.

    Why:
        The live room seeds its polling cursor from the summary response. If that
        cursor comes from an ahead-of-time host clock instead of the same DB
        snapshot, a submission created right after the summary can disappear from
        the next delta poll.
    """
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for live summary cursor regression")

    owner = _session_store().create(sub="t-live-cursor-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = _session_store().create(sub="s-live-cursor-learner", name="Student", roles=["student"])  # type: ignore

    async with (await _client()) as owner_client, (await _client()) as student_client:
        owner_client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        student_client.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        course_id = await _create_course(owner_client, "Cursor Kurs")
        unit = await _create_unit(owner_client, "Cursor Einheit")
        section = await _create_section(owner_client, unit["id"], "Abschnitt")
        task = await _create_task(owner_client, unit["id"], section["id"], "### Aufgabe")
        module = await _attach_unit(owner_client, course_id, unit["id"])
        await _add_member(owner_client, course_id, learner.sub)
        release = await owner_client.patch(
            f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert release.status_code == 200

        real_datetime = teaching.datetime

        class _AheadDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                actual = real_datetime.now(tz or timezone.utc)
                if tz is None:
                    actual = actual.astimezone(timezone.utc).replace(tzinfo=None)
                return actual + timedelta(minutes=5)

        monkeypatch.setattr(teaching, "datetime", _AheadDateTime)
        summary_response = await owner_client.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/summary"
        )
        monkeypatch.setattr(teaching, "datetime", real_datetime)
        assert summary_response.status_code == 200
        summary_cursor = summary_response.json()["cursor"]

        submit_response = await student_client.post(
            f"/api/learning/courses/{course_id}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Antwort nach Summary"},
        )
        assert submit_response.status_code in (200, 201, 202)

        delta_response = await owner_client.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/delta",
            params={"updated_since": summary_cursor},
        )
        assert delta_response.status_code == 200
        cells = delta_response.json()["cells"]
        assert any(cell["student_sub"] == learner.sub and cell["task_id"] == task["id"] for cell in cells)


@pytest.mark.anyio
async def test_summary_returns_503_when_db_cursor_seed_is_unavailable(monkeypatch):
    """The live summary must fail closed when it cannot derive the DB cursor seed.

    Why:
        OpenAPI and the live polling docs define the summary cursor as a
        database-based seed. Returning a host-clock fallback would silently
        weaken that contract and reintroduce clock-skew risk.
    """
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for live summary cursor failure test")

    owner = _session_store().create(sub="t-live-cursor-503-owner", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        course_id = await _create_course(c, "Cursor 503 Kurs")
        unit = await _create_unit(c, "Cursor 503 Einheit")
        await _attach_unit(c, course_id, unit["id"])

        monkeypatch.setattr(teaching, "_summary_snapshot_cursor", lambda _repo: None)

        response = await c.get(
            f"/api/teaching/courses/{course_id}/units/{unit['id']}/submissions/summary"
        )
        assert response.status_code == 503
        assert response.headers.get("Cache-Control") == "private, no-store"
        assert response.headers.get("Vary") == "Origin"
        assert response.json() == {
            "error": "service_unavailable",
            "detail": "summary_cursor_unavailable",
        }


@pytest.mark.anyio
async def test_summary_includes_submissions_for_modular_units_without_section_releases():
    """Modular units do not use teacher section releases, but submissions must still appear.

    Why:
        The live matrix is a teacher tool and must work for both unit types.
        For modular units, students unlock modules via progress, not via
        `module_section_releases`.
    """
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for live summary test")

    owner = _session_store().create(sub="t-live-mod-matrix", name="Owner", roles=["teacher"])  # type: ignore
    student = _session_store().create(sub="s-live-mod-1", name="Anna", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Live Kurs Modular")
        unit = await _create_unit(c, "Live Einheit Modular", unit_type="modular")
        sec1 = await _create_section(c, unit["id"], "M1")
        task = await _create_task(c, unit["id"], sec1["id"], "### A1")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, student.sub)

        # Modular: no section release step. First module should be open by default.
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_sub = await c.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Meine Lösung"},
        )
        assert r_sub.status_code in (202, 201, 200), r_sub.text

        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        rows = {row["student"]["sub"]: row for row in body["rows"]}
        cells = {cell["task_id"]: cell for cell in rows[student.sub]["tasks"]}
        assert cells[task["id"]]["has_submission"] is True


@pytest.mark.anyio
async def test_summary_includes_latest_h5p_score_x_y_and_completion_flag():
    """H5P summary cells expose latest x/y plus completion semantics.

    Semantics (MVP):
        - `score_raw/score_max` reflect the latest H5P attempt
        - `h5p_completed` stays true once a full-score attempt existed
          (score_raw == score_max, including 0/0), even if later attempts are worse
    """
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for H5P summary test")

    owner = _session_store().create(sub="t-live-h5p-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = _session_store().create(sub="s-live-h5p-learner", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Live Kurs H5P")
        unit = await _create_unit(c_owner, "Live Einheit H5P")
        section = await _create_section(c_owner, unit["id"], "S1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        # Create three H5P tasks: bearbeitet, abgeschlossen, and unscored (0/0).
        r_t_attempted = await c_owner.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={
                "instruction_md": "H5P Attempted",
                "criteria": [],
                "max_attempts": 3,
                "h5p": {"content_id": "1001", "display_options": {}},
            },
        )
        assert r_t_attempted.status_code == 201
        t_attempted = r_t_attempted.json()

        r_t_completed = await c_owner.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={
                "instruction_md": "H5P Completed",
                "criteria": [],
                "max_attempts": 3,
                "h5p": {"content_id": "1002", "display_options": {}},
            },
        )
        assert r_t_completed.status_code == 201
        t_completed = r_t_completed.json()

        r_t_unscored = await c_owner.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={
                "instruction_md": "H5P Unscored Completed",
                "criteria": [],
                "max_attempts": 3,
                "h5p": {"content_id": "1003", "display_options": {}},
            },
        )
        assert r_t_unscored.status_code == 201
        t_unscored = r_t_unscored.json()

        # Release section so student submissions are allowed.
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        # Student attempts first task but never reaches full score.
        r_a1 = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{t_attempted['id']}/submissions",
            json={"kind": "h5p", "score_raw": 0, "score_max": 1},
        )
        assert r_a1.status_code in (200, 201, 202)

        # Student completes second task at least once, then makes a worse attempt.
        r_c1 = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{t_completed['id']}/submissions",
            json={"kind": "h5p", "score_raw": 0, "score_max": 1},
        )
        assert r_c1.status_code in (200, 201, 202)
        r_c2 = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{t_completed['id']}/submissions",
            json={"kind": "h5p", "score_raw": 1, "score_max": 1},
        )
        assert r_c2.status_code in (200, 201, 202)
        r_c3 = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{t_completed['id']}/submissions",
            json={"kind": "h5p", "score_raw": 0, "score_max": 1},
        )
        assert r_c3.status_code in (200, 201, 202)

        # Unscored H5P content can report 0/0. Product decision: 0/0 counts as completed.
        r_u1 = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{t_unscored['id']}/submissions",
            json={"kind": "h5p", "score_raw": 0, "score_max": 0},
        )
        assert r_u1.status_code in (200, 201, 202)

        # Owner fetches summary and checks H5P flags.
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200
        body = r.json()
        tasks_by_id = {t["id"]: t for t in body["tasks"]}
        assert tasks_by_id[t_attempted["id"]]["kind"] == "h5p"
        assert tasks_by_id[t_completed["id"]]["kind"] == "h5p"
        assert tasks_by_id[t_unscored["id"]]["kind"] == "h5p"

        rows = {row["student"]["sub"]: row for row in body["rows"]}
        cells = {c["task_id"]: c for c in rows[learner.sub]["tasks"]}
        assert cells[t_attempted["id"]]["has_submission"] is True
        assert cells[t_attempted["id"]]["score_raw"] == 0
        assert cells[t_attempted["id"]]["score_max"] == 1
        assert cells[t_attempted["id"]].get("h5p_completed") is False

        assert cells[t_completed["id"]]["has_submission"] is True
        assert cells[t_completed["id"]]["score_raw"] == 0
        assert cells[t_completed["id"]]["score_max"] == 1
        assert cells[t_completed["id"]].get("h5p_completed") is True

        assert cells[t_unscored["id"]]["has_submission"] is True
        assert cells[t_unscored["id"]]["score_raw"] == 0
        assert cells[t_unscored["id"]]["score_max"] == 0
        assert cells[t_unscored["id"]].get("h5p_completed") is True


@pytest.mark.anyio
async def test_summary_uses_latest_h5p_attempt_when_created_at_timestamps_tie():
    """Latest H5P selection must stay deterministic when created_at ties.

    Why:
        Snapshot imports or bulk timestamp corrections can leave two attempts
        with the same `created_at`. The live summary must still pick the latest
        semantic attempt, not an arbitrary physical row.
    """
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for H5P summary tie test")

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required for H5P summary tie test")

    owner = _session_store().create(sub="t-live-h5p-tie-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = _session_store().create(sub="s-live-h5p-tie-learner", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Live Kurs H5P Tie")
        unit = await _create_unit(c_owner, "Live Einheit H5P Tie")
        section = await _create_section(c_owner, unit["id"], "S1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        r_task = await c_owner.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={
                "instruction_md": "H5P Tie Break",
                "criteria": [],
                "max_attempts": 3,
                "h5p": {"content_id": "1999", "display_options": {}},
            },
        )
        assert r_task.status_code == 201
        task = r_task.json()

        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        r_first = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "h5p", "score_raw": 0, "score_max": 1},
        )
        assert r_first.status_code in (200, 201, 202), r_first.text
        first_submission = r_first.json()

        r_second = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "h5p", "score_raw": 1, "score_max": 1},
        )
        assert r_second.status_code in (200, 201, 202), r_second.text
        second_submission = r_second.json()

        tied_ts = "2026-03-14T12:00:00+00:00"
        with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.learning_submissions
                       set created_at = %s::timestamptz,
                           completed_at = %s::timestamptz
                     where id in (%s::uuid, %s::uuid)
                    """,
                    (tied_ts, tied_ts, first_submission["id"], second_submission["id"]),
                )
            conn.commit()

        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        rows = {row["student"]["sub"]: row for row in body["rows"]}
        cells = {c["task_id"]: c for c in rows[learner.sub]["tasks"]}

        assert cells[task["id"]]["score_raw"] == 1
        assert cells[task["id"]]["score_max"] == 1
        assert cells[task["id"]].get("h5p_completed") is True


@pytest.mark.anyio
async def test_summary_includes_average_score_for_completed_analysis():
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("DB-backed repos required for summary average score test")

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to emulate analysis completion")

    owner = _session_store().create(sub="t-live-score-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = _session_store().create(sub="s-live-score-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Live Kurs Scores")
        unit = await _create_unit(c_owner, "Live Einheit Scores")
        section = await _create_section(c_owner, unit["id"], "S1")
        t1 = await _create_task(c_owner, unit["id"], section["id"], "### A1")
        t2 = await _create_task(c_owner, unit["id"], section["id"], "### A2")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        r_sub1 = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{t1['id']}/submissions",
            json={"kind": "text", "text_body": "Score A1"},
        )
        assert r_sub1.status_code in (200, 201, 202)
        sub_id_1 = r_sub1.json().get("id")
        assert sub_id_1

        r_sub2 = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{t2['id']}/submissions",
            json={"kind": "text", "text_body": "Score A2"},
        )
        assert r_sub2.status_code in (200, 201, 202)
        sub_id_2 = r_sub2.json().get("id")
        assert sub_id_2

    analysis_payload = {
        "schema": "criteria.v2",
        "criteria_results": [
            {"criterion": "K1", "score": 4, "max_score": 5},
            {"criterion": "K2", "score": 8, "max_score": 10},
        ],
    }
    with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute(
                """
                select public.learning_worker_update_completed(
                    %s::uuid,
                    %s,
                    %s,
                    %s::jsonb
                )
                """,
                (
                    sub_id_1,
                    "Matrix Analysis",
                    "Feedback",
                    json.dumps(analysis_payload),
                ),
            )

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
    assert r.status_code == 200
    body = r.json()
    rows = {row["student"]["sub"]: row for row in body["rows"]}
    cells = {c["task_id"]: c for c in rows[learner.sub]["tasks"]}
    avg = cells[t1["id"]]["average_score"]
    assert isinstance(avg, float)
    assert avg == pytest.approx(8.0)
    assert isinstance(cells[t1["id"]]["created_at"], str)
    assert cells[t1["id"]]["created_at"]
    assert isinstance(cells[t2["id"]]["created_at"], str)
    assert cells[t2["id"]]["created_at"]
    assert cells[t2["id"]]["average_score"] is None


@pytest.mark.anyio
async def test_summary_keeps_scores_for_later_learners_when_page_contains_more_cells_than_helper_limit():
    """Regression: learner-page pagination must not truncate score cells.

    Why:
        The summary endpoint paginates rows by learners. A previous implementation
        delegated the same `limit/offset` directly to a DB helper that pages by
        `(student_sub, task_id)` cells. With enough tasks per learner, later
        learners on the same page silently lost `has_submission` and
        `average_score`.
    """
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for pagination regression test")

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to emulate analysis completion")

    owner = _session_store().create(sub="t-live-page-owner", name="Owner", roles=["teacher"])  # type: ignore

    learners = [
        _session_store().create(sub=f"s-live-page-{index:02d}", name=f"Student {index:02d}", roles=["student"])  # type: ignore
        for index in range(1, 12)
    ]
    late_learner = learners[-1]

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c_owner, "Live Kurs Pagination")
        unit = await _create_unit(c_owner, "Live Einheit Pagination")
        section = await _create_section(c_owner, unit["id"], "Abschnitt")
        tasks = [
            await _create_task(c_owner, unit["id"], section["id"], f"### Aufgabe {task_index}")
            for task_index in range(1, 21)
        ]
        module = await _attach_unit(c_owner, cid, unit["id"])
        for learner in learners:
            await _add_member(c_owner, cid, learner.sub)

        release = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert release.status_code == 200

    async with (await _client()) as c_student:
        c_student.cookies.set(main.SESSION_COOKIE_NAME, late_learner.session_id)
        for task in tasks:
            submitted = await c_student.post(
                f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
                json={"kind": "text", "text_body": f"Antwort fuer {task['id']}"},
            )
            assert submitted.status_code in (200, 201, 202)
            submission_id = submitted.json().get("id")
            assert submission_id

            analysis_payload = {
                "schema": "criteria.v2",
                "criteria_results": [
                    {"criterion": "K1", "score": 4, "max_score": 5},
                    {"criterion": "K2", "score": 8, "max_score": 10},
                ],
            }
            with psycopg.connect(dsn) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select public.learning_worker_update_completed(
                            %s::uuid,
                            %s,
                            %s,
                            %s::jsonb
                        )
                        """,
                        (
                            submission_id,
                            "Regression analysis",
                            "Regression feedback",
                            json.dumps(analysis_payload),
                        ),
                    )

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        response = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 11, "offset": 0},
        )

    assert response.status_code == 200
    body = response.json()
    rows = {row["student"]["sub"]: row for row in body["rows"]}
    assert late_learner.sub in rows
    late_cells = {cell["task_id"]: cell for cell in rows[late_learner.sub]["tasks"]}
    assert len(late_cells) == len(tasks)
    for task in tasks:
        assert late_cells[task["id"]]["has_submission"] is True
        assert late_cells[task["id"]]["average_score"] == pytest.approx(8.0)


@pytest.mark.anyio
async def test_summary_can_skip_student_rows():
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for summary include_students test")

    owner = _session_store().create(sub="t-live-include", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Include Kurs")
        unit = await _create_unit(c, "Include Einheit")
        await _attach_unit(c, cid, unit["id"])

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"include_students": False},
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["tasks"], list)
        assert body["rows"] == []


@pytest.mark.anyio
async def test_summary_rejects_invalid_updated_since():
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for timestamp validation")

    owner = _session_store().create(sub="t-live-invalid-ts", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Live Kurs Invalid")
        unit = await _create_unit(c, "Live Einheit Invalid")
        await _attach_unit(c, cid, unit["id"])

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"updated_since": "not-a-timestamp"},
        )
        assert r.status_code == 400
        body = r.json()
        assert body["detail"] == "invalid_timestamp"


@pytest.mark.anyio
async def test_summary_falls_back_when_helper_is_missing(monkeypatch, caplog):
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for helper fallback test")

    monkeypatch.setattr(
        teaching,
        "resolve_student_login_labels_by_sub",
        lambda subs: {str(sid): str(sid).split("@", 1)[0].replace("legacy-email:", "") for sid in subs},
    )
    monkeypatch.setattr(
        teaching.REPO,
        "list_unit_latest_submission_aggregates_for_owner",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bulk helper unavailable in compat test")),
    )

    owner = _session_store().create(sub="t-live-fallback-owner", name="Owner", roles=["teacher"])  # type: ignore
    student = _session_store().create(sub="s-live-fallback", name="Fallback", roles=["student"])  # type: ignore

    async with (await _client()) as owner_client, (await _client()) as student_client:
        owner_client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        student_client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)

        cid = await _create_course(owner_client, "Live Kurs Fallback")
        unit = await _create_unit(owner_client, "Live Einheit Fallback")
        section = await _create_section(owner_client, unit["id"], "S Fallback")
        task = await _create_task(owner_client, unit["id"], section["id"], "### Aufgabe")
        module = await _attach_unit(owner_client, cid, unit["id"])
        await _add_member(owner_client, cid, student.sub)
        # Release section so student can submit
        r_vis = await owner_client.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        # Student creates submission (before monkeypatch to avoid interfering with learning repo)
        r_sub = await student_client.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Fallback submission"},
        )
        assert r_sub.status_code in (200, 201, 202)

        original_connect = psycopg.connect

        class _CursorWrapper:
            def __init__(self, cursor):
                self._cursor = cursor

            def __enter__(self):
                self._cursor.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._cursor.__exit__(exc_type, exc, tb)

            def execute(self, query, params=None):
                if "get_unit_latest_submissions_for_owner" in query:
                    raise psy_errors.UndefinedFunction("function get_unit_latest_submissions_for_owner does not exist")
                return self._cursor.execute(query, params)

            def fetchall(self):
                return self._cursor.fetchall()

            def __getattr__(self, name):
                return getattr(self._cursor, name)

        class _ConnectionWrapper:
            def __init__(self, connection):
                self._connection = connection

            def __enter__(self):
                self._connection.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._connection.__exit__(exc_type, exc, tb)

            def cursor(self, *args, **kwargs):
                return _CursorWrapper(self._connection.cursor(*args, **kwargs))

            def close(self):
                return self._connection.close()

            def __getattr__(self, name):
                return getattr(self._connection, name)

        def _patched_connect(*args, **kwargs):
            conn = original_connect(*args, **kwargs)
            return _ConnectionWrapper(conn)

        monkeypatch.setattr(psycopg, "connect", _patched_connect)

        caplog.clear()
        caplog.set_level("WARNING", logger="gustav.web.teaching")
        response = await owner_client.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rows"], "expected rows despite helper failure"
        student_row = next(row for row in body["rows"] if row["student"]["sub"] == student.sub)
        assert any(cell["has_submission"] for cell in student_row["tasks"])
        assert any(
            "unit_live_helper_row_lookup_failed" in msg and "error_type=UndefinedFunction" in msg
            for msg in caplog.messages
        )
        assert "get_unit_latest_submissions_for_owner does not exist" not in caplog.text


@pytest.mark.anyio
async def test_summary_falls_back_when_helper_score_columns_are_missing(monkeypatch, caplog):
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for helper compatibility test")

    monkeypatch.setattr(
        teaching,
        "resolve_student_login_labels_by_sub",
        lambda subs: {str(sid): str(sid).split("@", 1)[0].replace("legacy-email:", "") for sid in subs},
    )
    monkeypatch.setattr(
        teaching.REPO,
        "list_unit_latest_submission_aggregates_for_owner",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("bulk helper unavailable in compat test")),
    )

    owner = _session_store().create(sub="t-live-legacy-owner", name="Owner", roles=["teacher"])  # type: ignore
    student = _session_store().create(sub="s-live-legacy", name="Legacy", roles=["student"])  # type: ignore

    async with (await _client()) as owner_client, (await _client()) as student_client:
        owner_client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        student_client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)

        cid = await _create_course(owner_client, "Live Kurs Legacy")
        unit = await _create_unit(owner_client, "Live Einheit Legacy")
        section = await _create_section(owner_client, unit["id"], "S Legacy")
        task = await _create_task(owner_client, unit["id"], section["id"], "### Aufgabe")
        module = await _attach_unit(owner_client, cid, unit["id"])
        await _add_member(owner_client, cid, student.sub)

        r_vis = await owner_client.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        r_sub = await student_client.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Legacy summary submission"},
        )
        assert r_sub.status_code in (200, 201, 202)

        original_connect = psycopg.connect

        class _CursorWrapper:
            def __init__(self, cursor):
                self._cursor = cursor

            def __enter__(self):
                self._cursor.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._cursor.__exit__(exc_type, exc, tb)

            def execute(self, query, params=None):
                if "get_unit_latest_submissions_for_owner" in query and "score_raw" in query:
                    raise psy_errors.UndefinedColumn("column \"score_raw\" does not exist")
                return self._cursor.execute(query, params)

            def fetchall(self):
                return self._cursor.fetchall()

            def __getattr__(self, name):
                return getattr(self._cursor, name)

        class _ConnectionWrapper:
            def __init__(self, connection):
                self._connection = connection

            def __enter__(self):
                self._connection.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._connection.__exit__(exc_type, exc, tb)

            def cursor(self, *args, **kwargs):
                return _CursorWrapper(self._connection.cursor(*args, **kwargs))

            def rollback(self):
                return self._connection.rollback()

            def close(self):
                return self._connection.close()

            def __getattr__(self, name):
                return getattr(self._connection, name)

        def _patched_connect(*args, **kwargs):
            conn = original_connect(*args, **kwargs)
            return _ConnectionWrapper(conn)

        monkeypatch.setattr(psycopg, "connect", _patched_connect)

        caplog.clear()
        caplog.set_level("WARNING", logger="gustav.web.teaching")
        response = await owner_client.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary"
        )
        assert response.status_code == 200
        body = response.json()
        student_row = next(row for row in body["rows"] if row["student"]["sub"] == student.sub)
        assert any(cell["has_submission"] for cell in student_row["tasks"])
        assert any(
            "unit_live_helper_row_lookup_failed" in msg and "error_type=UndefinedColumn" in msg
            for msg in caplog.messages
        )
        assert 'column "score_raw" does not exist' not in caplog.text


@pytest.mark.anyio
async def test_summary_falls_back_when_bulk_aggregate_helper_is_missing(monkeypatch, caplog):
    _require_db_or_skip()
    teaching = importlib.import_module("backend.web.routes.teaching")
    learning = importlib.import_module("backend.web.routes.learning")
    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for bulk helper fallback test")

    owner = _session_store().create(sub="t-live-bulk-missing-owner", name="Owner", roles=["teacher"])  # type: ignore
    student = _session_store().create(sub="s-live-bulk-missing", name="Fallback", roles=["student"])  # type: ignore

    async with (await _client()) as owner_client, (await _client()) as student_client:
        owner_client.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        student_client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)

        cid = await _create_course(owner_client, "Live Kurs Bulk Fallback")
        unit = await _create_unit(owner_client, "Live Einheit Bulk Fallback")
        section = await _create_section(owner_client, unit["id"], "S Bulk Fallback")
        task = await _create_task(owner_client, unit["id"], section["id"], "### Aufgabe")
        module = await _attach_unit(owner_client, cid, unit["id"])
        await _add_member(owner_client, cid, student.sub)

        r_vis = await owner_client.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        r_sub = await student_client.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Bulk fallback submission"},
        )
        assert r_sub.status_code in (200, 201, 202)

        original_connect = psycopg.connect

        class _CursorWrapper:
            def __init__(self, cursor):
                self._cursor = cursor

            def __enter__(self):
                self._cursor.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._cursor.__exit__(exc_type, exc, tb)

            def execute(self, query, params=None):
                if "get_unit_latest_submission_aggregates_for_owner" in query:
                    raise psy_errors.UndefinedFunction(
                        "function get_unit_latest_submission_aggregates_for_owner does not exist"
                    )
                return self._cursor.execute(query, params)

            def fetchall(self):
                return self._cursor.fetchall()

            def __getattr__(self, name):
                return getattr(self._cursor, name)

        class _ConnectionWrapper:
            def __init__(self, connection):
                self._connection = connection

            def __enter__(self):
                self._connection.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._connection.__exit__(exc_type, exc, tb)

            def cursor(self, *args, **kwargs):
                return _CursorWrapper(self._connection.cursor(*args, **kwargs))

            def rollback(self):
                return self._connection.rollback()

            def close(self):
                return self._connection.close()

            def __getattr__(self, name):
                return getattr(self._connection, name)

        def _patched_connect(*args, **kwargs):
            conn = original_connect(*args, **kwargs)
            return _ConnectionWrapper(conn)

        monkeypatch.setattr(psycopg, "connect", _patched_connect)
        caplog.set_level("WARNING")

        response = await owner_client.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary"
        )

    assert response.status_code == 200
    body = response.json()
    student_row = next(row for row in body["rows"] if row["student"]["sub"] == student.sub)
    assert any(cell["has_submission"] for cell in student_row["tasks"])
    assert any(
        "unit_summary_bulk_aggregate_fallback" in msg and "error_type=UndefinedFunction" in msg
        for msg in caplog.messages
    )
    assert "get_unit_latest_submission_aggregates_for_owner does not exist" not in caplog.text
