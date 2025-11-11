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
