"""
Teaching API — Units & Course Modules (contract-first, TDD)

These tests define the desired behaviour for managing reusable Units and their
attachment to Courses as Course Modules. Implementation must follow after the
tests (red phase), ensuring Clean Architecture with DB-backed persistence and
strict RLS.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


from utils.db import require_db_or_skip as _require_db_or_skip


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    resp = await client.post("/api/teaching/courses", json={"title": title})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str = "Funktionen", summary: str | None = None) -> dict:
    payload = {"title": title}
    if summary is not None:
        payload["summary"] = summary
    resp = await client.post("/api/teaching/units", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_units_require_auth_and_teacher_role():
    main.SESSION_STORE = SessionStore()

    async with (await _client()) as client:
        # Unauthenticated → 401
        resp_unauth = await client.get("/api/teaching/units")
        assert resp_unauth.status_code == 401

    # Set up student session
    student = main.SESSION_STORE.create(sub="student-101", name="Max", roles=["student"])
    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        resp_role = await client.post("/api/teaching/units", json={"title": "Forbidden"})
        assert resp_role.status_code == 403


@pytest.mark.anyio
async def test_teacher_can_crud_units_and_ownership_is_enforced():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher_a = main.SESSION_STORE.create(sub="teacher-A", name="Frau A", roles=["teacher"])
    teacher_b = main.SESSION_STORE.create(sub="teacher-B", name="Herr B", roles=["teacher"])

    async with (await _client()) as client:
        # Teacher A creates a unit
        client.cookies.set("gustav_session", teacher_a.session_id)
        created = await _create_unit(client, title="Lineare Funktionen", summary="Einführung in Steigung")
        unit_id = created["id"]
        assert created["author_id"] == "teacher-A"

        # Teacher A lists units → sees own
        lst_a = await client.get("/api/teaching/units")
        assert lst_a.status_code == 200
        assert any(u["id"] == unit_id for u in lst_a.json())

        # Teacher B should not see A's unit
        client.cookies.set("gustav_session", teacher_b.session_id)
        lst_b = await client.get("/api/teaching/units")
        assert lst_b.status_code == 200
        assert all(u["author_id"] == "teacher-B" for u in lst_b.json())

        # Teacher B cannot update or delete A's unit
        update_forbidden = await client.patch(f"/api/teaching/units/{unit_id}", json={"title": "Verboten"})
        assert update_forbidden.status_code == 403
        delete_forbidden = await client.delete(f"/api/teaching/units/{unit_id}")
        assert delete_forbidden.status_code == 403

        # Switch back to teacher A for update
        client.cookies.set("gustav_session", teacher_a.session_id)
        patched = await client.patch(
            f"/api/teaching/units/{unit_id}",
            json={"title": "Lineare Funktionen I", "summary": "Aktualisiert"},
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Lineare Funktionen I"
        assert patched.json()["summary"] == "Aktualisiert"

        # Delete succeeds for the author
        deleted = await client.delete(f"/api/teaching/units/{unit_id}")
        assert deleted.status_code == 204
        assert deleted.text == ""

        # Unit no longer appears
        lst_after = await client.get("/api/teaching/units")
        assert all(u["id"] != unit_id for u in lst_after.json())


@pytest.mark.anyio
async def test_unit_validation_errors():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-validate", name="Frau V", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)

        # Missing title → 400
        resp_missing = await client.post("/api/teaching/units", json={})
        assert resp_missing.status_code == 400
        assert resp_missing.json().get("detail") == "invalid_title"

        # Too long title → 400
        resp_long = await client.post("/api/teaching/units", json={"title": "x" * 201})
        assert resp_long.status_code == 400
        assert resp_long.json().get("detail") == "invalid_title"

        # Patch without fields → 400
        created = await _create_unit(client, title="Valid Unit")
        resp_empty_patch = await client.patch(f"/api/teaching/units/{created['id']}", json={})
        assert resp_empty_patch.status_code == 400
        assert resp_empty_patch.json().get("detail") == "empty_payload"


@pytest.mark.anyio
async def test_course_modules_owner_workflow_and_duplicates():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher_a = main.SESSION_STORE.create(sub="teacher-mod", name="Frau Module", roles=["teacher"])
    teacher_b = main.SESSION_STORE.create(sub="teacher-other", name="Herr Fremd", roles=["teacher"])

    async with (await _client()) as client:
        # Teacher A course + unit
        client.cookies.set("gustav_session", teacher_a.session_id)
        course_id = await _create_course(client, title="Mathe 10A")
        unit = await _create_unit(client, title="Quadratische Funktionen")

        # Add module → position 1
        create_module = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"], "context_notes": "Vorbereitung"},
        )
        assert create_module.status_code == 201
        body = create_module.json()
        assert body["course_id"] == course_id
        assert body["unit_id"] == unit["id"]
        assert body["position"] == 1

        # List modules sorted by position
        lst = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert lst.status_code == 200
        arr = lst.json()
        assert len(arr) == 1
        assert arr[0]["position"] == 1

        # Duplicate add → 409
        dup = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"], "context_notes": None},
        )
        assert dup.status_code == 409

        # Non-owner cannot list/add
        client.cookies.set("gustav_session", teacher_b.session_id)
        resp_list_forbidden = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert resp_list_forbidden.status_code == 403
        resp_add_forbidden = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"]},
        )
        assert resp_add_forbidden.status_code == 403


@pytest.mark.anyio
async def test_course_modules_require_unit_author():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher_a = main.SESSION_STORE.create(sub="teacher-owner", name="Owner", roles=["teacher"])
    teacher_b = main.SESSION_STORE.create(sub="teacher-author", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        # Teacher B creates a unit
        client.cookies.set("gustav_session", teacher_b.session_id)
        foreign_unit = await _create_unit(client, title="Fremde Einheit")

        # Teacher A creates a course
        client.cookies.set("gustav_session", teacher_a.session_id)
        course_id = await _create_course(client, title="Physik 9B")

        # Teacher A cannot attach unit authored by B
        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": foreign_unit["id"]},
        )
        assert resp.status_code == 403


@pytest.mark.anyio
async def test_course_modules_reorder_updates_positions():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-reorder", name="ReOrder", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Chemie 8")
        unit_a = await _create_unit(client, title="Laborregeln")
        unit_b = await _create_unit(client, title="Atombau")
        unit_c = await _create_unit(client, title="Periodensystem")

        # Add modules in natural order
        mod_a = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        mod_b = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()
        mod_c = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_c["id"]})).json()

        reorder = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_c["id"], mod_a["id"], mod_b["id"]]},
        )
        assert reorder.status_code == 200
        ordered = reorder.json()
        assert [m["id"] for m in ordered] == [mod_c["id"], mod_a["id"], mod_b["id"]]
        assert [m["position"] for m in ordered] == [1, 2, 3]

        # GET reflects new order
        lst = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert [m["id"] for m in lst.json()] == [mod_c["id"], mod_a["id"], mod_b["id"]]


@pytest.mark.anyio
async def test_course_modules_reorder_validation_rules():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-validate-mod", name="ValidMod", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Geschichte 7")
        unit_a = await _create_unit(client, title="Mittelalter")
        unit_b = await _create_unit(client, title="Neuzeit")

        mod_a = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        mod_b = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()

        # Duplicate IDs → 400
        dup = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"], mod_a["id"]]},
        )
        assert dup.status_code == 400
        assert dup.json().get("detail") == "duplicate_module_ids"

        # Missing ID → 400
        missing = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"]]},
        )
        assert missing.status_code == 400
        assert missing.json().get("detail") == "module_mismatch"

        # Extraneous ID → 400
        extra = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"], str(uuid4()), mod_b["id"]]},
        )
        assert extra.status_code == 400
        assert extra.json().get("detail") == "module_mismatch"

        # Module from another course → 404
        other_course = await _create_course(client, title="Geschichte Parallel")
        mod_other = (
            await client.post(f"/api/teaching/courses/{other_course}/modules", json={"unit_id": unit_a["id"]})
        ).json()
        cross = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [mod_a["id"], mod_b["id"], mod_other["id"]]},
        )
        assert cross.status_code == 404


@pytest.mark.anyio
async def test_deleting_unit_cascades_course_modules():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-delete", name="Delete", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Informatik 11")
        unit = await _create_unit(client, title="Algorithmen")

        mod_resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit["id"]},
        )
        assert mod_resp.status_code == 201

        # Delete unit → expect cascade (no modules remain)
        del_unit = await client.delete(f"/api/teaching/units/{unit['id']}")
        assert del_unit.status_code == 204

        modules_after = await client.get(f"/api/teaching/courses/{course_id}/modules")
        assert modules_after.status_code == 200
        assert modules_after.json() == []


@pytest.mark.anyio
async def test_course_modules_reorder_with_invalid_uuid_returns_400():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-invalid-reorder", name="Invalid", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Biologie 8")
        unit_a = await _create_unit(client, title="Zellen")
        unit_b = await _create_unit(client, title="Genetik")

        mod_a = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        mod_b = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()

        payload = {"module_ids": [mod_a["id"], "not-a-uuid", mod_b["id"]]}
        resp = await client.post(f"/api/teaching/courses/{course_id}/modules/reorder", json=payload)
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_module_ids"


@pytest.mark.anyio
async def test_course_module_create_with_invalid_unit_uuid_returns_400():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-invalid-create", name="InvalidUnit", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Musik 7")

        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": "definitely-not-a-uuid"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_unit_id"


@pytest.mark.anyio
async def test_course_modules_reorder_empty_list_returns_400():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-empty-reorder", name="Empty", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(client, title="Informatik 9")
        unit_a = await _create_unit(client, title="Programmierung I")
        unit_b = await _create_unit(client, title="Programmierung II")

        _ = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_a["id"]})).json()
        _ = (await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_b["id"]})).json()

        # Empty array should be a 400 (not FastAPI 422)
        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": []},
        )
        assert resp.status_code == 400
        assert resp.json().get("detail") == "empty_reorder"


@pytest.mark.anyio
async def test_course_modules_reorder_invalid_course_id_returns_400():
    """Invalid course_id (not UUID) must map to 400 invalid_course_id per contract."""
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-bad-course", name="BadCourse", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        # The payload shape is otherwise fine; only path param is invalid
        resp = await client.post(
            "/api/teaching/courses/not-a-uuid/modules/reorder",
            json={"module_ids": [str(uuid4())]},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_course_id"


@pytest.mark.anyio
async def test_course_modules_reorder_non_owner_invalid_payload_is_403():
    """Non-owner should get 403 even with invalid payload (security-first, avoid error oracle)."""
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    owner = main.SESSION_STORE.create(sub="owner-guard", name="Owner", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="other-guard", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        # Owner creates a course
        client.cookies.set("gustav_session", owner.session_id)
        course_id = await _create_course(client, title="Security")

        # Non-owner attempts reorder with invalid payload (empty list)
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": []},
        )
        assert resp.status_code in (403, 404)
        # We accept 403 or 404 based on helper semantics, but not 400
        assert resp.status_code != 400


@pytest.mark.anyio
async def test_sections_reorder_non_author_invalid_payload_is_403():
    """Non-author should get 403/404 even with invalid payload (avoid error oracle for sections)."""
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="author-sec", name="Author", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="other-sec", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        # Author creates a unit
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Sicherheit")

        # Non-author attempts reorder with invalid payload (empty list)
        client.cookies.set("gustav_session", other.session_id)
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": []},
        )
        assert resp.status_code in (403, 404)
        assert resp.status_code != 400
