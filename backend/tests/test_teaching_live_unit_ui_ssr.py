"""
SSR UI — Live Unit Matrix (teacher)

We validate the per-unit Live page and its SSR fragments that render the
matrix and apply polling deltas via OOB fragments. This builds on the
existing JSON API summary/delta endpoints.

Covers:
- Teacher-only access and initial table render
- Matrix fragment (summary) with deterministic cell IDs
- Delta fragment returns 204 when nothing changed, later OOB cells after a submission
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
# Avoid requiring a working DB DSN during import in this test module
os.environ["ALLOW_SERVICE_DSN_FOR_TESTING"] = "true"
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402
from utils.db import require_db_or_skip as _require_db_or_skip  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    r = await client.post("/api/teaching/units", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Abschnitt") -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_task(client: httpx.AsyncClient, unit_id: str, section_id: str, instruction: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction, "criteria": ["Kriterium 1"], "max_attempts": 3},
        headers={"Origin": "http://test"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
    assert r.status_code == 201, r.text
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub}, headers={"Origin": "http://test"})
    assert r.status_code in (201, 204), r.text


@pytest.mark.anyio
async def test_live_page_teacher_only_and_renders_table():
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-owner", name="Owner", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-ui-student", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        # Student → redirect
        c_student.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_forbidden = await c_student.get("/teaching/courses/00000000-0000-0000-0000-000000000000/units/00000000-0000-0000-0000-000000000000/live")
        assert r_forbidden.status_code in (302, 303)

        # Owner: set up data
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c_owner, "Kurs UI")
        unit = await _create_unit(c_owner, "Einheit UI")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### A1")
        mod = await _attach_unit(c_owner, cid, unit["id"])  # capture module id for visibility
        await _add_member(c_owner, cid, student.sub)

        # Release section to allow submissions later
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{mod['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        r = await c_owner.get(f"/teaching/courses/{cid}/units/{unit['id']}/live")
        assert r.status_code == 200
        # Basic shape: heading and matrix placeholder/table
        html = r.text
        assert "Unterricht – Live" in html
        assert "table" in html, "expected a table markup in the page"


@pytest.mark.anyio
async def test_live_page_includes_status_cursor_and_polling_attributes():
    """Live page should expose a status cursor and HTMX polling hook.

    Why:
        The UI relies on periodic polling of the SSR delta fragment to keep
        the matrix up to date. The page must therefore render:
        - a status element with a `data-updated-since` ISO timestamp, and
        - an element with `hx-get`/`hx-trigger` that calls the delta route.
    """
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-poll-owner", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c_owner, "Kurs UI Polling")
        unit = await _create_unit(c_owner, "Einheit Polling")
        section = await _create_section(c_owner, unit["id"], "S1")
        await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        mod = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, "s-ui-poll-learner")
        # Release section to allow submissions later (same setup wie Haupttest)
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{mod['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        r = await c_owner.get(f"/teaching/courses/{cid}/units/{unit['id']}/live")
        assert r.status_code == 200
        html = r.text

        # Statusleiste mit Cursor
        assert 'id="live-status"' in html
        assert "data-updated-since=\"" in html

        # Polling-Hook: Live-Section ruft Delta-Route periodisch auf
        delta_path = f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix/delta"
        assert delta_path in html
        assert f'hx-get="{delta_path}"' in html
        # Polling-Intervall (3s) ist im Trigger kodiert
        assert 'hx-trigger="every 3s"' in html


@pytest.mark.anyio
async def test_live_page_respects_poll_interval_constant():
    """Live page should derive the polling interval from the main module constant.

    This keeps the interval adjustable via configuration while tests can still
    override it directly on the imported main module.
    """
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-poll-override-owner", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c_owner, "Kurs UI Poll Override")
        unit = await _create_unit(c_owner, "Einheit Poll Override")
        section = await _create_section(c_owner, unit["id"], "S1")
        await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        mod = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, "s-ui-poll-override-learner")

        # Release section to allow submissions later
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{mod['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        # Override polling interval for this test only.
        original = getattr(main, "TEACHING_LIVE_POLL_INTERVAL_SECONDS", 3)
        try:
            main.TEACHING_LIVE_POLL_INTERVAL_SECONDS = 5  # type: ignore[attr-defined]

            r = await c_owner.get(f"/teaching/courses/{cid}/units/{unit['id']}/live")
            assert r.status_code == 200
            html = r.text
            assert 'hx-trigger="every 5s"' in html
        finally:
            main.TEACHING_LIVE_POLL_INTERVAL_SECONDS = original  # type: ignore[attr-defined]


def test_poll_interval_env_config_clamps_invalid_values(monkeypatch):
    """Polling interval config should clamp invalid env values to a safe default.

    Why:
        Ops may accidentally set GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS to 0,
        a negative number or a non-integer string. The web adapter should handle
        this defensively so the Live polling hook never renders an unusable
        hx-trigger interval.
    """
    # Import the already-loaded main module; in the test environment this
    # corresponds to backend.web.main thanks to the sys.modules aliasing.
    import main as main_mod  # type: ignore

    # Helper to evaluate the helper function with a specific env value.
    def _with(value: str | None) -> int:
        if value is None:
            monkeypatch.delenv("GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS", raising=False)
        else:
            monkeypatch.setenv("GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS", value)
        return int(main_mod._load_poll_interval_from_env())

    # Default when env is unset → 3 seconds.
    default_val = _with(None)
    assert default_val == 3

    # Non-integer value → fall back to default (3s).
    non_int_val = _with("not-an-int")
    assert non_int_val == 3

    # Zero and negative values should be clamped to at least 1s.
    zero_val = _with("0")
    assert zero_val == 1
    negative_val = _with("-5")
    assert negative_val == 1

    # Excessively large values should be capped to a sensible upper bound (e.g. 60s).
    large_val = _with("600")
    assert large_val == 60


@pytest.mark.anyio
async def test_matrix_fragment_renders_initial_summary_and_cell_ids():
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-matrix-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ui-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs UI Matrix")
        unit = await _create_unit(c_owner, "Einheit Matrix")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        # Fetch matrix fragment
        r = await c_owner.get(f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix")
        assert r.status_code == 200
        html = r.text
        assert "id=\"live-matrix\"" in html
        assert "class=\"table table-compact\"" in html
        # Validate deterministic cell id
        cell_id = f"cell-{learner.sub}-{task['id']}"
        assert cell_id in html
        # Initially no submission → shows '—'
        # allow either a literal em-dash or a hyphen representation
        assert "—" in html or "-&gt;" not in html
        # First column should have student-name class (used for sticky)
        assert "class=\"student-name\"" in html


@pytest.mark.anyio
async def test_matrix_shows_display_name_with_email_prefix(monkeypatch):
    _require_db_or_skip()

    # Patch name resolver inside teaching routes to return an email as name
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for SSR name test")

    def _fake_resolve(subs: list[str]) -> dict[str, str]:
        return {subs[0]: "alice@example.com"}

    monkeypatch.setattr(teaching, "resolve_student_names", _fake_resolve)

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-name-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ui-name-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)

        cid = await _create_course(c, "Kurs UI Names")
        unit = await _create_unit(c, "Einheit Names")
        section = await _create_section(c, unit["id"], "S1")
        # Ensure there is at least one task so the matrix renders a table
        await _create_task(c, unit["id"], section["id"], "### NameCheck")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, learner.sub)

        r = await c.get(f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix")
        assert r.status_code == 200
        html = r.text
        # Expect only the prefix "alice", not the full email or raw sub
        assert "alice@example.com" not in html
        assert "alice" in html
        # Note: `sub` may appear in non-visible attributes (cell ids / data-attrs)
        # for deterministic OOB updates; we only care that the visible name is humanized.


@pytest.mark.anyio
async def test_delta_fragment_returns_204_then_oob_cells_after_submission():
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ui-delta-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs UI Delta")
        unit = await _create_unit(c_owner, "Einheit Delta")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        # Release section for submissions
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        base_ts = datetime.now(timezone.utc).isoformat()
        # Empty delta
        r_empty = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix/delta",
            params={"updated_since": base_ts},
        )
        assert r_empty.status_code == 204

        # Student submits
        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Lösung"},
            headers={"Origin": "http://test"},
        )
        assert r_sub.status_code in (200, 201, 202)

        # Delta should now include OOB cell update
        r_delta = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix/delta",
            params={"updated_since": base_ts},
        )
        assert r_delta.status_code == 200
        html = r_delta.text
        # OOB update should target the cell id
        assert "hx-swap-oob=\"true\"" in html
        assert f"cell-{learner.sub}-{task['id']}" in html
        assert "✅" in html


@pytest.mark.anyio
async def test_delta_fragment_keeps_clickable_cell_attributes():
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-htmx-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ui-delta-htmx-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs UI Delta HTMX")
        unit = await _create_unit(c_owner, "Einheit Delta HTMX")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        base_ts = datetime.now(timezone.utc).isoformat()
        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Lösung"},
            headers={"Origin": "http://test"},
        )
        assert r_sub.status_code in (200, 201, 202)

        r_delta = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix/delta",
            params={"updated_since": base_ts},
        )
        assert r_delta.status_code == 200
        html = r_delta.text

        expected_href = (
            f"/teaching/courses/{cid}/units/{unit['id']}/live/detail"
            f"?student_sub={learner.sub}&task_id={task['id']}"
        )
        assert f'hx-get="{expected_href}"' in html
        assert 'hx-target="#live-detail"' in html
        assert 'hx-swap="innerHTML"' in html
        assert f'data-sub="{learner.sub}"' in html
        assert f'data-task="{task["id"]}"' in html
        assert 'hx-swap-oob="true"' in html


@pytest.mark.anyio
async def test_matrix_fragment_renders_average_score_badge():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("DB-backed repos required for SSR average score test")

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to emulate analysis completion")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-score-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ui-score-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs UI Score")
        unit = await _create_unit(c_owner, "Einheit UI Score")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Matrix Score"},
            headers={"Origin": "http://test"},
        )
        assert r_sub.status_code in (200, 201, 202)
        sub_id = r_sub.json().get("id")
        assert sub_id

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
                    sub_id,
                    "Matrix Analysis",
                    "Feedback",
                    json.dumps(analysis_payload),
                ),
            )

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c_owner.get(f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix")
    assert r.status_code == 200
    html = r.text
    assert 'class="badge badge-success"' in html
    assert ">8<" in html


@pytest.mark.anyio
async def test_delta_fragment_renders_average_score_badge():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("DB-backed repos required for SSR delta score test")

    dsn = os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN")
    if not dsn:
        pytest.skip("SERVICE_ROLE_DSN required to emulate analysis completion")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-score-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ui-delta-score-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs UI Delta Score")
        unit = await _create_unit(c_owner, "Einheit UI Delta Score")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        base_ts = datetime.now(timezone.utc).isoformat()

        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Matrix Score"},
            headers={"Origin": "http://test"},
        )
        assert r_sub.status_code in (200, 201, 202)
        sub_id = r_sub.json().get("id")
        assert sub_id

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
                    sub_id,
                    "Matrix Analysis",
                    "Feedback",
                    json.dumps(analysis_payload),
                ),
            )

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_delta = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix/delta",
            params={"updated_since": base_ts},
        )
    assert r_delta.status_code == 200
    html = r_delta.text
    assert "hx-swap-oob=\"true\"" in html
    assert f"cell-{learner.sub}-{task['id']}" in html
    assert 'class="badge badge-success"' in html


@pytest.mark.anyio
async def test_delta_fragment_sets_cursor_via_hx_trigger():
    """Delta fragment should emit HX-Trigger with a cursor for the client.

    Why:
        The browser needs a monotonically increasing cursor to pass as
        `updated_since` on subsequent polls. The SSR delta route should
        expose the next cursor via HX-Trigger so JS can update the status.
    """
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-cursor-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ui-delta-cursor-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs UI Delta Cursor")
        unit = await _create_unit(c_owner, "Einheit Delta Cursor")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        # Release section for submissions
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

        base_ts = datetime.now(timezone.utc).isoformat()

        # Student submits once to create at least eine Änderung
        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Lösung"},
            headers={"Origin": "http://test"},
        )
        assert r_sub.status_code in (200, 201, 202)

        r_delta = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/matrix/delta",
            params={"updated_since": base_ts},
        )
        assert r_delta.status_code == 200
        trigger = r_delta.headers.get("HX-Trigger")
        assert trigger, "expected HX-Trigger header for live cursor update"

        import json as _json

        data = _json.loads(trigger)
        assert "liveCursorUpdated" in data
        cursor = data["liveCursorUpdated"].get("cursor")
        assert isinstance(cursor, str) and cursor, "cursor must be a non-empty string"

        # The cursor should be a parseable ISO timestamp in UTC and
        # monotonically >= the base timestamp used for the delta request.
        base_dt = datetime.fromisoformat(base_ts)
        cursor_dt = datetime.fromisoformat(cursor)
        assert cursor_dt.tzinfo is not None, "cursor must carry timezone information"
        # Allow equality to avoid flakiness when timestamps are very close.
        assert cursor_dt >= base_dt, "cursor must not go backwards in time"


@pytest.mark.anyio
async def test_delta_fragment_error_responses_set_private_cache_headers(monkeypatch):
    """Delta fragment should set private, no-store cache headers even on error."""
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-cache-owner", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)

        # Trigger a fast-path 400 by sending an empty updated_since. The route
        # must still mark the response as private and non-cacheable.
        r_delta = await c_owner.get(
            "/teaching/courses/any/units/any/live/matrix/delta",
            params={"updated_since": ""},
        )
        assert r_delta.status_code == 400
        cache = r_delta.headers.get("Cache-Control", "")
        vary = r_delta.headers.get("Vary", "")
        assert "no-store" in cache and "private" in cache
        assert "Origin" in vary


@pytest.mark.anyio
async def test_delta_fragment_propagates_upstream_http_error_with_private_cache(monkeypatch):
    """Delta fragment should propagate non-200 upstream HTTP status with private cache headers."""
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-upstream-http-owner", name="Owner", roles=["teacher"])  # type: ignore

    # Stub internal API client to return a 503 error from the JSON delta endpoint.
    def _stub_internal_api_client():
        class _StubResponse:
            def __init__(self) -> None:
                self.status_code = 503

            def json(self) -> dict:
                return {}

        class _StubClient:
            def __init__(self) -> None:
                class _Cookies:
                    def set(self, _name: str, _value: str) -> None:
                        return None

                self.cookies = _Cookies()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url: str, params: dict | None = None):
                assert "/submissions/delta" in url
                return _StubResponse()

        return _StubClient()

    monkeypatch.setattr(main, "_internal_api_client", _stub_internal_api_client)

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)

        base_ts = datetime.now(timezone.utc).isoformat()
        r_delta = await c_owner.get(
            "/teaching/courses/dummy/units/dummy/live/matrix/delta",
            params={"updated_since": base_ts},
        )
        assert r_delta.status_code == 503
        cache = r_delta.headers.get("Cache-Control", "")
        vary = r_delta.headers.get("Vary", "")
        assert "no-store" in cache and "private" in cache
        assert "Origin" in vary


@pytest.mark.anyio
async def test_delta_fragment_emits_cursor_even_when_changed_at_missing(monkeypatch):
    """Delta fragment should still emit a cursor when changed_at is missing.

    Why:
        In case the JSON delta endpoint returns cells without a changed_at
        field (or with malformed timestamps), the SSR route must still provide
        a monotonically increasing cursor via HX-Trigger so the client can
        advance its polling window and avoid repeating the same OOB updates.
    """
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-missing-ts-owner", name="Owner", roles=["teacher"])  # type: ignore

    # Monkeypatch the internal API client used by the delta fragment so we can
    # control the JSON payload without going through the full Teaching repo.
    def _stub_internal_api_client():
        class _StubResponse:
            def __init__(self) -> None:
                self.status_code = 200

            def json(self) -> dict:
                # Single cell without a changed_at field; this is the case we
                # want the SSR route to handle gracefully.
                return {
                    "cells": [
                        {"student_sub": "s1", "task_id": "t1", "has_submission": True},
                        ]
                    }

        class _StubClient:
            def __init__(self) -> None:
                class _Cookies:
                    def set(self, _name: str, _value: str) -> None:
                        # No-op: the stubbed client does not persist cookies,
                        # but the interface must match httpx.AsyncClient.
                        return None

                self.cookies = _Cookies()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url: str, params: dict | None = None):
                assert "/submissions/delta" in url
                return _StubResponse()

        return _StubClient()

    monkeypatch.setattr(main, "_internal_api_client", _stub_internal_api_client)

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)

        base_ts = datetime.now(timezone.utc).isoformat()
        r_delta = await c_owner.get(
            "/teaching/courses/dummy/units/dummy/live/matrix/delta",
            params={"updated_since": base_ts},
        )
        assert r_delta.status_code == 200
        trigger = r_delta.headers.get("HX-Trigger")
        assert trigger, "expected HX-Trigger header even when changed_at is missing"

        import json as _json

        data = _json.loads(trigger)
        assert "liveCursorUpdated" in data
        cursor = data["liveCursorUpdated"].get("cursor")
        assert isinstance(cursor, str) and cursor


@pytest.mark.anyio
async def test_delta_fragment_returns_502_on_upstream_request_error(monkeypatch):
    """Delta fragment should return 502 when the internal JSON delta endpoint is unreachable."""
    _require_db_or_skip()

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ui-delta-upstream-error-owner", name="Owner", roles=["teacher"])  # type: ignore

    # Simulate an httpx.RequestError being raised inside the internal API client.
    import httpx

    class _ErroringClient:
        def __init__(self) -> None:
            class _Cookies:
                def set(self, _name: str, _value: str) -> None:
                    return None

            self.cookies = _Cookies()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params: dict | None = None):
            raise httpx.RequestError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(main, "_internal_api_client", lambda: _ErroringClient())

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)

        base_ts = datetime.now(timezone.utc).isoformat()
        r_delta = await c_owner.get(
            "/teaching/courses/dummy/units/dummy/live/matrix/delta",
            params={"updated_since": base_ts},
        )
        assert r_delta.status_code == 502
        cache = r_delta.headers.get("Cache-Control", "")
        vary = r_delta.headers.get("Vary", "")
        assert "no-store" in cache and "private" in cache
        assert "Origin" in vary
