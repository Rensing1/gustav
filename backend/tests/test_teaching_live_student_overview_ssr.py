"""
SSR UI — Student live overview page (teacher)
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
os.environ["ALLOW_SERVICE_DSN_FOR_TESTING"] = "true"
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402
from utils.db import require_db_or_skip as _require_db_or_skip  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Kurs") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
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
async def test_student_live_overview_page_renders_grouped_units_and_empty_filter_state() -> None:
    _require_db_or_skip()
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-student-live-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ssr-student-live", name="Anna", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Kurs SSR Schueler")
        unit = await _create_unit(c, "Einheit SSR Schueler")
        sec = await _create_section(c, unit["id"], "S1")
        task = await _create_task(c, unit["id"], sec["id"], "### Aufgabe SSR mit **Markdown**")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, learner.sub)

        page = await c.get(f"/teaching/courses/{cid}/students/{learner.sub}/live")
        assert page.status_code == 200, page.text
        assert "Unterricht" in page.text
        assert "Aufgaben gesamt" in page.text
        assert "Mit Abgabe" in page.text
        assert "Offen" in page.text
        assert ">1</strong>" in page.text
        assert "Einheit SSR Schueler" in page.text
        assert "Aufgabe SSR" in page.text
        assert "Aufgabe 1" in page.text
        assert f'id="student-live-task-detail-{task["id"]}"' in page.text
        assert (
            f'hx-get="/teaching/courses/{cid}/units/{unit["id"]}/live/detail'
            f'?student_sub={learner.sub}&amp;task_id={task["id"]}"'
        ) in page.text
        assert f'name="unit_ids" value="{unit["id"]}"' in page.text
        assert "Bitte Aufgabe waehlen." not in page.text
        assert "Abgabe vorhanden" not in page.text

        empty = await c.get(
            f"/teaching/courses/{cid}/students/{learner.sub}/live",
            params=[("unit_ids", "")],
        )
        assert empty.status_code == 200, empty.text
        assert "Keine Lerneinheiten ausgewaehlt" in empty.text


def _stub_student_live_internal_api_client(
    *,
    course_id: str,
    units: list[dict],
    overview_status: int,
    overview_body: dict,
):
    class _StubResponse:
        def __init__(self, status_code: int, payload: dict | list) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

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

        async def get(self, url: str, params=None):
            if url == f"/api/teaching/courses/{course_id}":
                return _StubResponse(200, {"id": course_id, "title": "Kurs SSR Fehler"})
            if url == f"/api/teaching/courses/{course_id}/modules":
                return _StubResponse(200, [{"unit_id": unit["id"]} for unit in units])
            if url.startswith("/api/teaching/units/"):
                unit_id = url.rsplit("/", 1)[-1]
                for unit in units:
                    if unit["id"] == unit_id:
                        return _StubResponse(200, unit)
                return _StubResponse(404, {"error": "not_found"})
            if url == f"/api/teaching/courses/{course_id}/students/student-1/submissions/overview":
                return _StubResponse(overview_status, overview_body)
            raise AssertionError(url)

    return _StubClient()


def _stub_detail_internal_api_client(*, course_id: str, unit_id: str, task_id: str, student_sub: str, payload_status: int, payload: dict | None):
    class _StubResponse:
        def __init__(self, status_code: int, payload: dict | None) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

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

        async def get(self, url: str, params=None):
            expected = (
                f"/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest"
            )
            if url == expected:
                return _StubResponse(payload_status, payload)
            raise AssertionError(url)

    return _StubClient()


@pytest.mark.anyio
async def test_student_live_overview_page_renders_too_many_units_error(monkeypatch: pytest.MonkeyPatch) -> None:
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-student-live-too-many", name="Owner", roles=["teacher"])  # type: ignore
    course_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    unit_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    monkeypatch.setattr(
        main,
        "_internal_api_client",
        lambda: _stub_student_live_internal_api_client(
            course_id=course_id,
            units=[{"id": unit_id, "title": "Einheit A"}],
            overview_status=400,
            overview_body={"error": "bad_request", "detail": "too_many_unit_ids"},
        ),
        raising=False,
    )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        page = await c.get(
            f"/teaching/courses/{course_id}/students/student-1/live",
            params=[("unit_ids", unit_id)],
        )

    assert page.status_code == 400, page.text
    assert "Zu viele Lerneinheiten ausgewaehlt" in page.text
    assert page.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_student_live_overview_page_renders_forbidden_error(monkeypatch: pytest.MonkeyPatch) -> None:
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-student-live-forbidden", name="Owner", roles=["teacher"])  # type: ignore
    course_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    monkeypatch.setattr(
        main,
        "_internal_api_client",
        lambda: _stub_student_live_internal_api_client(
            course_id=course_id,
            units=[],
            overview_status=403,
            overview_body={"error": "forbidden"},
        ),
        raising=False,
    )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        page = await c.get(f"/teaching/courses/{course_id}/students/student-1/live")

    assert page.status_code == 403, page.text
    assert "Kein Zugriff auf diese Schueleransicht" in page.text
    assert page.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_student_live_overview_page_renders_inline_task_details(monkeypatch: pytest.MonkeyPatch) -> None:
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-student-live-inline", name="Owner", roles=["teacher"])  # type: ignore
    course_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    unit_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    task_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    monkeypatch.setattr(
        main,
        "_internal_api_client",
        lambda: _stub_student_live_internal_api_client(
            course_id=course_id,
            units=[{"id": unit_id, "title": "Einheit Inline"}],
            overview_status=200,
            overview_body={
                "student": {"sub": "student-1", "name": "Anna"},
                "units": [
                    {
                        "id": unit_id,
                        "title": "Einheit Inline",
                        "tasks": [
                            {
                                "id": task_id,
                                "instruction_md": "### Aufgabe Inline\n\nMit etwas Kontext.",
                                "position": 1,
                                "kind": "native",
                                "has_submission": False,
                                "average_score": None,
                                "h5p_completed": None,
                            }
                        ],
                    }
                ],
            },
        ),
        raising=False,
    )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        page = await c.get(f"/teaching/courses/{course_id}/students/student-1/live")

    assert page.status_code == 200, page.text
    assert "student-live-summary" in page.text
    assert "Aufgaben gesamt" in page.text
    assert "Mit Abgabe" in page.text
    assert "Offen" in page.text
    assert "<details" in page.text
    assert "student-live-task__summary" in page.text
    assert "student-live-task__title" in page.text
    assert "student-live-task__meta" in page.text
    assert "Mit etwas Kontext." not in page.text
    assert f'id="student-live-task-detail-{task_id}"' in page.text
    assert "Bitte Aufgabe waehlen." not in page.text


@pytest.mark.anyio
async def test_student_live_detail_partial_marks_tab_groups_for_inline_js(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inline detail partials should expose a generic tab-group hook."""
    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-student-live-tabs", name="Owner", roles=["teacher"])  # type: ignore
    course_id = "12121212-1212-1212-1212-121212121212"
    unit_id = "34343434-3434-3434-3434-343434343434"
    task_id = "56565656-5656-5656-5656-565656565656"
    student_sub = "student-tabs"
    monkeypatch.setattr(
        main,
        "_internal_api_client",
        lambda: _stub_detail_internal_api_client(
            course_id=course_id,
            unit_id=unit_id,
            task_id=task_id,
            student_sub=student_sub,
            payload_status=200,
            payload={
                "id": "submission-1",
                "created_at": "2026-03-14T12:00:00Z",
                "kind": "text",
                "instruction_md": "### Aufgabe",
                "text_body": "Antwort",
                "feedback_md": "### Rueckmeldung\nGut.",
                "analysis_json": {
                    "schema": "criteria.v2",
                    "score": 7,
                    "criteria_results": [
                        {
                            "criterion": "Kriterium 1",
                            "score": 7,
                            "max_score": 10,
                            "explanation_md": "Sauber geloest.",
                        }
                    ],
                },
                "files": [],
            },
        ),
        raising=False,
    )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_detail = await c.get(
            f"/teaching/courses/{course_id}/units/{unit_id}/live/detail",
            params={"student_sub": student_sub, "task_id": task_id},
        )

    assert r_detail.status_code == 200
    assert 'data-view-tabs="true"' in r_detail.text
    assert "Auswertung" in r_detail.text
    assert "Rückmeldung" in r_detail.text
