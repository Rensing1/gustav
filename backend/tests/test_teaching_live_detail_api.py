"""
Teaching API — Latest submission detail (owner)

Contract-first tests for fetching the latest submission of a given student for
a task within a unit and course. Owner-only and privacy-preserving.
"""
from __future__ import annotations

import uuid
import pytest
import httpx
from httpx import ASGITransport
from pathlib import Path
import os

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
async def test_latest_detail_requires_owner_and_valid_ids():
    main.SESSION_STORE = SessionStore()
    async with (await _client()) as c:
        # unauthenticated
        r = await c.get(
            "/api/teaching/courses/00000000-0000-0000-0000-000000000000/units/00000000-0000-0000-0000-000000000000/tasks/00000000-0000-0000-0000-000000000000/students/s/submissions/latest"
        )
        assert r.status_code == 401

    student = main.SESSION_STORE.create(sub="s-detail", name="Schüler", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.get(
            f"/api/teaching/courses/{uuid.uuid4()}/units/{uuid.uuid4()}/tasks/{uuid.uuid4()}/students/{student.sub}/submissions/latest"
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_latest_detail_happy_path_and_no_content_cases():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required for detail tests")

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-detail-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-detail-learner", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs Detail")
        unit = await _create_unit(c_owner, "Einheit Detail")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe 1")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)

        # Initially: 204 No Content
        r_none = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
        )
        assert r_none.status_code in (204, 404)

        # Release & student submits a text
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200
        r_sub = await c_student.post(
            f"/api/learning/courses/{cid}/tasks/{task['id']}/submissions",
            json={"kind": "text", "text_body": "Das ist eine Antwort."},
        )
        # Async submission acceptance
        assert r_sub.status_code in (200, 201, 202)

        r_detail = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
        )
        assert r_detail.status_code == 200
        body = r_detail.json()
        assert body["id"]
        assert body["task_id"] == task["id"]
        assert body["student_sub"] == learner.sub
        assert body["kind"] in ("text", "file", "image", "pdf")
        # For text submissions, expect a body
        if body["kind"] == "text":
            assert isinstance(body.get("text_body"), str) and len(body["text_body"]) > 0


@pytest.mark.anyio
async def test_latest_detail_includes_text_and_files_for_pdf_submission():
    """File/PDF submissions should expose extracted text and signed file URLs."""
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
        pytest.skip("DB-backed repos and psycopg required for file submission detail test")

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
    owner = main.SESSION_STORE.create(sub="t-detail-file-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-detail-file", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs Detail File")
        unit = await _create_unit(c_owner, "Einheit Detail File")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Datei-Aufgabe")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

    # Seed a PDF submission with extracted text via service connection
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
                f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
            )
        assert r_detail.status_code == 200
        body = r_detail.json()
        assert body["id"] == submission_id
        assert body["kind"] in ("file", "pdf", "image")
        assert isinstance(body.get("text_body"), str) and "Extrahierter Text" in body["text_body"]
        files = body.get("files") or []
        assert isinstance(files, list) and len(files) >= 1
        assert "storage.test" in str(files[0].get("url"))
    finally:
        teaching.set_storage_adapter(original_teaching_adapter)
        learning.set_storage_adapter(original_learning_adapter)


@pytest.mark.anyio
async def test_latest_detail_includes_feedback_and_analysis():
    """Auswertungstab: feedback_md und kriteriumsbasierte analysis_json (criteria.v2) sollen geliefert werden.

    Given:
        - Eine textbasierte Einreichung mit gespeicherter Rückmeldung (feedback_md).
        - Ein legacy-artiges Analyse-JSON mit `summary` und einer einfachen Kriterienliste.
    When:
        - Die Lehrkraft den Latest-Detail-Endpunkt für diese Einreichung abruft.
    Then:
        - Die API liefert `feedback_md` unverändert zurück.
        - `analysis_json` wird in ein criteria.v2-kompatibles Objekt mit `schema` und `criteria_results`
          überführt (kein freies `summary`-Dict mehr im Contract).
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
        pytest.skip("DB-backed repos and psycopg required for feedback test")

    def _dsn() -> str:
        host = os.getenv("TEST_DB_HOST", "127.0.0.1")
        port = os.getenv("TEST_DB_PORT", "54322")
        user = os.getenv("APP_DB_USER", "gustav_app")
        password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
        return os.getenv("SERVICE_ROLE_DSN") or os.getenv("RLS_TEST_SERVICE_DSN") or os.getenv(
            "DATABASE_URL"
        ) or f"postgresql://{user}:{password}@{host}:{port}/postgres"

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-detail-feedback-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-detail-feedback", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs Detail Feedback")
        unit = await _create_unit(c_owner, "Einheit Detail Feedback")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Aufgabe Feedback")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

    submission_id = str(uuid.uuid4())
    feedback_md = "## Feedback\nGute Arbeit."
    # Legacy/alternatives Format: freies Dict mit summary + einfacher Kriterienliste.
    analysis_payload = {
        "summary": "ok",
        "criteria": [
            {
                "title": "Kriterium 1",
                "comment": "passt",
                "score": "ok",
            }
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
                    "Antwort für Feedback",
                    feedback_md,
                    analysis_payload,
                ),
            )
        conn.commit()

    async with (await _client()) as c_owner:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        r_detail = await c_owner.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
        )
    assert r_detail.status_code == 200
    body = r_detail.json()
    assert body["id"] == submission_id
    # Feedback wird unverändert zurückgegeben
    assert body.get("feedback_md", "").startswith("## Feedback")

    analysis = body.get("analysis_json")
    assert isinstance(analysis, dict)
    # Contract: criteria.v1/v2-Objekt mit Schema-Tag und Kriterienliste
    assert analysis.get("schema") in ("criteria.v1", "criteria.v2")
    results = analysis.get("criteria_results")
    assert isinstance(results, list) and len(results) >= 1
    first = results[0]
    assert first.get("criterion") == "Kriterium 1"
    # Kommentar/Erklärung aus dem Legacy-Format wird übernommen
    assert "passt" in str(first.get("explanation_md") or "")


@pytest.mark.anyio
async def test_latest_detail_includes_integer_file_size_for_pdf_submission():
    """Datei-Einreichungen: files[].size muss immer ein Integer sein.

    Given:
        - Eine PDF-Einreichung mit gesetztem size_bytes in der DB.
    When:
        - Die Lehrkraft den Latest-Detail-Endpunkt abruft.
    Then:
        - Die API liefert in files[0].size einen Integer (keine Nullwerte).
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
        pytest.skip("DB-backed repos and psycopg required for file size detail test")

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
    owner = main.SESSION_STORE.create(sub="t-detail-file-size-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-detail-file-size", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs Detail File Size")
        unit = await _create_unit(c_owner, "Einheit Detail File Size")
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
                f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
            )
        assert r_detail.status_code == 200
        body = r_detail.json()
        assert body["id"] == submission_id
        files = body.get("files") or []
        assert isinstance(files, list) and len(files) >= 1
        first = files[0]
        assert isinstance(first.get("size"), int)
        assert first["size"] == 1234
        assert "storage.test" in str(first.get("url"))
    finally:
        teaching.set_storage_adapter(original_teaching_adapter)
        learning.set_storage_adapter(original_learning_adapter)


@pytest.mark.anyio
async def test_latest_detail_omits_files_when_size_unknown():
    """Datei-Einreichungen ohne size_bytes sollen keine invalide files[].size liefern.

    Given:
        - Eine Datei-Einreichung mit fehlender Größe (size_bytes = NULL) in der DB.
    When:
        - Die Lehrkraft den Latest-Detail-Endpunkt abruft.
    Then:
        - Entweder ist das files-Array leer/fehlend oder alle enthaltenen Einträge
          besitzen ein Integer-`size` (kein `null` im Contract).
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
        pytest.skip("DB-backed repos and psycopg required for file size degradation test")

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
    owner = main.SESSION_STORE.create(sub="t-detail-file-size-missing-owner", name="Owner", roles=["teacher"])  # type: ignore
    learner = main.SESSION_STORE.create(sub="s-detail-file-size-missing", name="L", roles=["student"])  # type: ignore

    async with (await _client()) as c_owner, (await _client()) as c_student:
        c_owner.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        c_student.cookies.set(main.SESSION_COOKIE_NAME, learner.session_id)

        cid = await _create_course(c_owner, "Kurs Detail File Size Missing")
        unit = await _create_unit(c_owner, "Einheit Detail File Size Missing")
        section = await _create_section(c_owner, unit["id"], "S1")
        task = await _create_task(c_owner, unit["id"], section["id"], "### Datei-Aufgabe ohne Größe")
        module = await _attach_unit(c_owner, cid, unit["id"])
        await _add_member(c_owner, cid, learner.sub)
        r_vis = await c_owner.patch(
            f"/api/teaching/courses/{cid}/modules/{module['id']}/sections/{section['id']}/visibility",
            json={"visible": True},
        )
        assert r_vis.status_code == 200

    submission_id = str(uuid.uuid4())
    storage_key = f"submissions/{cid}/{task['id']}/{learner.sub}/orig/sample-unknown-size.pdf"
    with psycopg.connect(_dsn()) as conn:  # type: ignore
        with conn.cursor() as cur:
            cur.execute("select set_config('app.current_sub', %s, false)", (learner.sub,))
            # size_bytes explizit als NULL setzen
            cur.execute(
                """
                insert into public.learning_submissions (
                  id, course_id, task_id, student_sub, kind,
                  storage_key, mime_type, size_bytes, sha256, attempt_nr,
                  text_body, analysis_status, completed_at
                ) values (
                  %s::uuid, %s::uuid, %s::uuid, %s, 'file',
                  %s, %s, NULL, %s, 1,
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
                    "0" * 64,
                    "Extrahierter Text aus PDF ohne Größe",
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
                f"/api/teaching/courses/{cid}/units/{unit['id']}/tasks/{task['id']}/students/{learner.sub}/submissions/latest"
            )
        assert r_detail.status_code == 200
        body = r_detail.json()
        assert body["id"] == submission_id
        files = body.get("files") or []
        # Entweder keine Dateien oder alle haben integer size
        for f in files:
            assert isinstance(f.get("size"), int)
    finally:
        teaching.set_storage_adapter(original_teaching_adapter)
        learning.set_storage_adapter(original_learning_adapter)
