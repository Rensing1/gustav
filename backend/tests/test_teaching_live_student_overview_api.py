"""
Teaching API — Student live overview across course units (RED)
"""
from __future__ import annotations

import importlib
import uuid
from urllib.parse import quote

import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

main = importlib.import_module("backend.web.main")
teaching = importlib.import_module("backend.web.routes.teaching")
teaching_guards = importlib.import_module("backend.web.routes.teaching_guards")
learning = importlib.import_module("backend.web.routes.learning")


@pytest.fixture(autouse=True)
def _fresh_session_store(monkeypatch: pytest.MonkeyPatch) -> None:
    install_session_store(monkeypatch, main)


def _session_store():
    return main.RUNTIME.session_store


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title, "subject": "Testfach", "grade_level": "10", "school_year_start": 2026})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Abschnitt") -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_task(client: httpx.AsyncClient, unit_id: str, section_id: str, instruction: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction, "criteria": ["Kriterium 1"], "max_attempts": 3},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201, r.text
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204), r.text


@pytest.mark.anyio
async def test_student_live_overview_requires_teacher_owner_and_valid_ids() -> None:
    async with (await _client()) as c:
        r = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/students/some-student/submissions/overview"
        )
        assert r.status_code == 401

    student = _session_store().create(sub="s-live-overview-unauth", name="S", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/students/{student.sub}/submissions/overview"
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_student_live_overview_lists_all_units_and_supports_filtering() -> None:
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for student live overview")

    owner = _session_store().create(sub="t-student-live-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = _session_store().create(sub="s-student-live-1", name="Anna", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs Live Schueler")
        unit_a = await _create_unit(c_owner, "Einheit A")
        unit_b = await _create_unit(c_owner, "Einheit B")
        sec_a = await _create_section(c_owner, unit_a["id"], "S1")
        sec_b = await _create_section(c_owner, unit_b["id"], "S2")
        task_a1 = await _create_task(c_owner, unit_a["id"], sec_a["id"], "### Aufgabe A1")
        task_b1 = await _create_task(c_owner, unit_b["id"], sec_b["id"], "### Aufgabe B1")
        mod_a = await _attach_unit(c_owner, cid, unit_a["id"])
        _mod_b = await _attach_unit(c_owner, cid, unit_b["id"])
        await _add_member(c_owner, cid, learner.sub)

        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{mod_a['id']}/sections/{sec_a['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200, r_vis.text
        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task_a1['id']}/submissions",
            json={"kind": "text", "text_body": "Meine Antwort"},
        )
        assert r_sub.status_code in (200, 201, 202), r_sub.text

        r_all = await c_owner.get(
            f"/api/teaching/courses/{cid}/students/{learner.sub}/submissions/overview"
        )
        assert r_all.status_code == 200, r_all.text
        assert r_all.headers.get("Cache-Control") == "private, no-store"
        assert r_all.headers.get("Vary") == "Origin"
        body = r_all.json()
        assert body["student"]["sub"] == learner.sub
        assert len(body["units"]) == 2
        units = {u["id"]: u for u in body["units"]}
        assert units[unit_a["id"]]["tasks"][0]["id"] == task_a1["id"]
        assert units[unit_a["id"]]["tasks"][0]["has_submission"] is True
        assert units[unit_b["id"]]["tasks"][0]["id"] == task_b1["id"]
        assert units[unit_b["id"]]["tasks"][0]["has_submission"] is False

        r_filtered = await c_owner.get(
            f"/api/teaching/courses/{cid}/students/{learner.sub}/submissions/overview",
            params={"unit_ids": [unit_b["id"]]},
        )
        assert r_filtered.status_code == 200, r_filtered.text
        filtered = r_filtered.json()
        assert [u["id"] for u in filtered["units"]] == [unit_b["id"]]


@pytest.mark.anyio
async def test_student_live_overview_rejects_foreign_unit_and_non_member() -> None:
    _require_db_or_skip()

    try:
        from backend.teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for student live overview")

    owner = _session_store().create(sub="t-student-live-owner-2", name="Owner", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Kurs Live Schueler Guards")
        unit = await _create_unit(c, "Einheit Zugeordnet")
        foreign_unit = await _create_unit(c, "Einheit Fremd")
        await _attach_unit(c, cid, unit["id"])

        r_foreign = await c.get(
            f"/api/teaching/courses/{cid}/students/not-enrolled/submissions/overview",
            params={"unit_ids": [foreign_unit["id"]]},
        )
        assert r_foreign.status_code == 404, r_foreign.text


@pytest.mark.anyio
async def test_student_live_overview_deduplicates_unit_ids_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _session_store().create(sub="t-live-overview-casefold-owner", name="Owner", roles=["teacher"])  # type: ignore
    course_id = str(uuid.uuid4())
    unit_id = str(uuid.uuid4())

    class _FakeOverview:
        def to_dict(self, *, student_name: str) -> dict:
            return {"student": {"sub": "student-1", "name": student_name}, "units": []}

    class _FakeService:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def build(self, *, course_id: str, owner_sub: str, student_sub: str, raw_unit_ids):
            self.calls.append(list(raw_unit_ids or []))
            return _FakeOverview()

    fake_service = _FakeService()
    monkeypatch.setattr(teaching, "MAX_UNIT_IDS", 1, raising=False)
    monkeypatch.setattr(
        teaching_guards,
        "_guard_course_owner",
        lambda _course_id, _owner_sub, repo_provider=None: None,
        raising=False,
    )
    monkeypatch.setattr(teaching, "_get_student_live_overview_service", lambda: fake_service, raising=False)
    monkeypatch.setattr(
        teaching,
        "resolve_student_login_labels_by_sub",
        lambda subs: {str(subs[0]): "anna.login"},
        raising=False,
    )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(
            f"/api/teaching/courses/{course_id}/students/student-1/submissions/overview",
            params=[("unit_ids", unit_id), ("unit_ids", unit_id.upper())],
        )

    assert r.status_code == 200, r.text
    assert fake_service.calls == [[unit_id]]
    assert (r.json().get("student") or {}).get("name") == "anna.login"


@pytest.mark.anyio
async def test_student_live_overview_accepts_path_encoded_student_sub_with_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _session_store().create(sub="t-live-overview-path-owner", name="Owner", roles=["teacher"])  # type: ignore
    course_id = str(uuid.uuid4())
    student_sub = "legacy/student"

    class _FakeOverview:
        def to_dict(self, *, student_name: str) -> dict:
            return {"student": {"sub": student_sub, "name": student_name}, "units": []}

    class _FakeService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def build(self, *, course_id: str, owner_sub: str, student_sub: str, raw_unit_ids):
            self.calls.append(student_sub)
            return _FakeOverview()

    fake_service = _FakeService()
    monkeypatch.setattr(
        teaching_guards,
        "_guard_course_owner",
        lambda _course_id, _owner_sub, repo_provider=None: None,
        raising=False,
    )
    monkeypatch.setattr(teaching, "_get_student_live_overview_service", lambda: fake_service, raising=False)
    monkeypatch.setattr(
        teaching,
        "resolve_student_login_labels_by_sub",
        lambda subs: {str(subs[0]): "anna.login"},
        raising=False,
    )

    encoded_student_sub = quote(student_sub, safe="")

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r = await c.get(
            f"/api/teaching/courses/{course_id}/students/{encoded_student_sub}/submissions/overview"
        )

    assert r.status_code == 200, r.text
    assert fake_service.calls == [student_sub]
    assert (r.json().get("student") or {}).get("name") == "anna.login"
