"""
SSR UI — Detail pane below the live matrix (teacher)

We verify that the SSR partial for the detail view renders an empty state when
no submission exists and shows a text excerpt when a text submission exists.
"""
from __future__ import annotations

import os
from pathlib import Path
import uuid

import pytest
import httpx
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
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


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
async def test_detail_partial_empty_and_then_text_excerpt():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for SSR detail tests")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-detail-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ssr-detail", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs SSR Detail")
        unit = await _create_unit(c_owner, "Einheit SSR Detail")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        # Empty state
        r_empty = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/detail",
            params={"student_sub": learner.sub, "task_id": task["id"]},
        )
        assert r_empty.status_code == 200
        assert "Keine Einreichung" in r_empty.text

        # Release + submit
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Das ist eine Antwort."},
        )
        assert r_sub.status_code in (200, 201, 202)

        r_detail = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/detail",
            params={"student_sub": learner.sub, "task_id": task["id"]},
        )
        assert r_detail.status_code == 200
        assert "Einreichung" in r_detail.text
        assert "Antwort" in r_detail.text


@pytest.mark.anyio
async def test_detail_partial_file_submission_shows_text_and_file_tab():
    """File/PDF submissions should render tabs and the extracted text in SSR."""
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
        pytest.skip("DB-backed repos required for SSR detail tests")

    def _dsn() -> str:
        host = os.getenv("TEST_DB_HOST", "127.0.0.1")
        port = os.getenv("TEST_DB_PORT", "54322")
        user = os.getenv("APP_DB_USER", "gustav_app")
        password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
        return os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv(
            "DATABASE_URL"
        ) or f"postgresql://{user}:{password}@{host}:{port}/postgres"

    class _FakeStorageAdapter:
        def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict[str, str]:
            return {"url": f"https://storage.test/{bucket}/{key}", "headers": {}, "method": "GET"}

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-detail-file-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ssr-detail-file", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs SSR File Detail")
        unit = await _create_unit(c_owner, "Einheit SSR File Detail")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Datei-Aufgabe")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

    submission_id = str(uuid.uuid4())
    storage_key = f"submissions/{cid}/{task['id']}/{learner.sub}/orig/sample.pdf"
    with psycopg.connect(_dsn()) as conn:  # type: ignore
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (learner.sub,))
            cur.execute(
                """
                insert into public.learning_submissions (
                  id, course_id, task_id, student_sub, kind,
                  storage_key, mime_type, size_bytes, sha256, attempt_nr,
                  text_body, analysis_status, completed_at
                ) values (
                  %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                  %s, %s, %s, %s, 1,
                  %s, 'completed', now()
                )
                """,
                (
                    submission_id,
                    cid,
                    task["id"],
                    learner.sub,
                    storage_key,
                    "application/pdf",
                    1234,
                    "0" * 64,
                    "Extrahierter Text aus PDF",
                ),
            )
        conn.commit()

    original_teaching_adapter = teaching.STORAGE_ADAPTER
    original_learning_adapter = learning.STORAGE_ADAPTER
    teaching.set_storage_adapter(_FakeStorageAdapter())
    learning.set_storage_adapter(_FakeStorageAdapter())
    try:
        async with (await _client()) as c_owner:
            c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
            r_detail = await c_owner.get(
                f"/teaching/courses/{cid}/units/{unit['id']}/live/detail",
                params={"student_sub": learner.sub, "task_id": task["id"]},
            )
        assert r_detail.status_code == 200
        html = r_detail.text
        assert "Text" in html and "Datei" in html
        assert "Extrahierter Text" in html
        assert "tab-btn" in html  # tabs present
        assert "submission-body" in html  # wrapped text container
        # Dateigröße wird als Integer-Byteswert angezeigt
        assert "1234 Bytes" in html
    finally:
        teaching.set_storage_adapter(original_teaching_adapter)
        learning.set_storage_adapter(original_learning_adapter)


@pytest.mark.anyio
async def test_detail_partial_shows_rueckmeldung_und_auswertung_wie_schueler():
    """SSR soll Tabs „Rückmeldung“ und „Auswertung“ ohne doppelten Accordion-Toggle anzeigen.

    Given:
        - Eine textbasierte Einreichung mit feedback_md und criteria-Analyse in der DB.
    When:
        - Die Lehrkraft die Detailansicht im Live-View öffnet.
    Then:
        - Tabs „Auswertung“ und „Rückmeldung“ sind vorhanden (Auswertung vor Rückmeldung).
        - Die Auswertung wird im eigenen Tab gerendert.
        - Im Rückmeldung-Tab gibt es keinen zusätzlichen „Auswertung anzeigen“-Accordion-Toggle,
          dieser bleibt der Schüleransicht vorbehalten.
    """
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
        pytest.skip("DB-backed repos required for SSR Auswertung test")

    def _dsn() -> str:
        host = os.getenv("TEST_DB_HOST", "127.0.0.1")
        port = os.getenv("TEST_DB_PORT", "54322")
        user = os.getenv("APP_DB_USER", "gustav_app")
        password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
        return os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv(
            "DATABASE_URL"
        ) or f"postgresql://{user}:{password}@{host}:{port}/postgres"

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-ssr-detail-feedback-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-ssr-detail-feedback", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs SSR Feedback Detail")
        unit = await _create_unit(c_owner, "Einheit SSR Feedback Detail")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Feedback-Aufgabe")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

    submission_id = str(uuid.uuid4())
    feedback_md = "### Rückmeldung\nSehr gut."
    analysis_payload = {
        "schema": "criteria.v1",
        "criteria_results": [
            {"criterion": "Kriterium 1", "score": 1, "max_score": 2, "explanation_md": "Begründung."},
        ],
    }
    with psycopg.connect(_dsn()) as conn:  # type: ignore
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (learner.sub,))
            cur.execute(
                """
                insert into public.learning_submissions (
                  id, course_id, task_id, student_sub, kind,
                  text_body, attempt_nr, analysis_status, completed_at, feedback_md, analysis_json
                ) values (
                  %s::uuid, %s::uuid, %s::uuid, %s, 'text',
                  %s, 1, 'completed', now(), %s, %s
                )
                """,
                (
                    submission_id,
                    cid,
                    task["id"],
                    learner.sub,
                    "Antwort mit Feedback",
                    feedback_md,
                    analysis_payload,
                ),
            )
        conn.commit()

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_detail = await c_owner.get(
            f"/teaching/courses/{cid}/units/{unit['id']}/live/detail",
            params={"student_sub": learner.sub, "task_id": task["id"]},
        )
    assert r_detail.status_code == 200
    html = r_detail.text
    # Tabs für Rückmeldung und Auswertung vorhanden
    assert "Rückmeldung" in html
    assert "Auswertung" in html
    assert "tab-btn" in html
    # Inhalt wie in der Schüleransicht: Rückmeldungstext und Auswertungsheading
    assert "Sehr gut." in html
    assert "analysis-criteria__heading" in html or "<strong>Auswertung</strong>" in html
    # Tab-Reihenfolge: Auswertung vor Rückmeldung (für Lehrkraft sinnvoll)
    idx_analysis = html.index('data-view-tab="analysis"')
    idx_feedback = html.index('data-view-tab="feedback"')
    assert idx_analysis < idx_feedback
    # Kein doppelter Accordion-Toggle wie in der Schüleransicht
    assert "Auswertung anzeigen" not in html
    assert "analysis-feedback__details" not in html
