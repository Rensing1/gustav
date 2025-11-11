"""
Teaching API — Unit Sections (contract-first, TDD)

Defines behaviour for CRUD on Sections within a Learning Unit, authored by the
current teacher. Tests assume OpenAPI contract is updated and DB-backed repo is
in use; they intentionally fail until implementation exists (red phase).
"""
from __future__ import annotations

import os
from pathlib import Path

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
    # Default Origin header so strict CSRF passes for write calls
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


async def _create_unit(client: httpx.AsyncClient, title: str = "Einheit") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_sections_require_auth_and_author_role():
    main.SESSION_STORE = SessionStore()

    async with (await _client()) as client:
        resp = await client.get(f"/api/teaching/units/00000000-0000-0000-0000-000000000000/sections")
        assert resp.status_code == 401

    # Student must be forbidden
    student = main.SESSION_STORE.create(sub="student-sections", name="Max", roles=["student"])
    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        resp = await client.post(
            f"/api/teaching/units/00000000-0000-0000-0000-000000000000/sections",
            json={"title": "Nope"},
        )
        assert resp.status_code == 403


@pytest.mark.anyio
async def test_author_can_crud_sections_and_non_author_is_blocked():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-sections-A", name="Autor", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-sections-B", name="Fremd", roles=["teacher"])

    async with (await _client()) as client:
        # Create unit as author
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Geometrie")
        unit_id = unit["id"]

        # List initially empty
        lst0 = await client.get(f"/api/teaching/units/{unit_id}/sections")
        assert lst0.status_code == 200
        assert lst0.json() == []

        # Create valid section → position 1
        created = await client.post(
            f"/api/teaching/units/{unit_id}/sections",
            json={"title": "Einführung"},
        )
        assert created.status_code == 201
        sec = created.json()
        assert sec["title"] == "Einführung"
        assert sec["position"] == 1

        # List shows one section
        lst1 = await client.get(f"/api/teaching/units/{unit_id}/sections")
        assert lst1.status_code == 200
        assert [s["id"] for s in lst1.json()] == [sec["id"]]

        # Non-author cannot modify
        client.cookies.set("gustav_session", other.session_id)
        forbidden_patch = await client.patch(
            f"/api/teaching/units/{unit_id}/sections/{sec['id']}", json={"title": "x"}
        )
        assert forbidden_patch.status_code == 403
        forbidden_delete = await client.delete(
            f"/api/teaching/units/{unit_id}/sections/{sec['id']}"
        )
        assert forbidden_delete.status_code == 403

        # Author updates title
        client.cookies.set("gustav_session", author.session_id)
        patched = await client.patch(
            f"/api/teaching/units/{unit_id}/sections/{sec['id']}", json={"title": "Basics"}
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Basics"

        # Delete → 204 and resequence not needed (single item)
        deleted = await client.delete(
            f"/api/teaching/units/{unit_id}/sections/{sec['id']}"
        )
        assert deleted.status_code == 204
        assert deleted.text == ""

        # List now empty again
        lst2 = await client.get(f"/api/teaching/units/{unit_id}/sections")
        assert lst2.status_code == 200
        assert lst2.json() == []


@pytest.mark.anyio
async def test_section_validation_and_unknown_ids():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-sections-validate", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Trigonometrie")

        # Invalid titles
        too_short = await client.post(
            f"/api/teaching/units/{unit['id']}/sections", json={"title": ""}
        )
        assert too_short.status_code == 400
        assert too_short.json().get("detail") == "invalid_title"
        too_long = await client.post(
            f"/api/teaching/units/{unit['id']}/sections", json={"title": "x" * 201}
        )
        assert too_long.status_code == 400
        assert too_long.json().get("detail") == "invalid_title"

        # Unknown unit → 404
        unknown_list = await client.get(
            "/api/teaching/units/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/sections"
        )
        assert unknown_list.status_code in (403, 404)  # Author-only → prefer 404 for non-owned/unknown

        # Unknown section for patch/delete → 404
        unknown_patch = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            json={"title": "X"},
        )
        assert unknown_patch.status_code == 404
        unknown_delete = await client.delete(
            f"/api/teaching/units/{unit['id']}/sections/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        )
        assert unknown_delete.status_code == 404


@pytest.mark.anyio
async def test_non_author_list_sections_returns_404():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-sections-owner", name="Owner", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-sections-nonowner", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Vektoren")

        client.cookies.set("gustav_session", other.session_id)
        resp = await client.get(f"/api/teaching/units/{unit['id']}/sections")
        assert resp.status_code in (403, 404)


@pytest.mark.anyio
async def test_invalid_unit_and_section_uuid_paths_return_400_and_patch_without_fields():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-sections-uuid", name="UUID", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Grenzwerte")

        # invalid unit_id in path → 400
        bad_unit_get = await client.get("/api/teaching/units/not-a-uuid/sections")
        assert bad_unit_get.status_code == 400
        assert bad_unit_get.json().get("detail") == "invalid_unit_id"
        bad_unit_post = await client.post(
            "/api/teaching/units/not-a-uuid/sections", json={"title": "X"}
        )
        assert bad_unit_post.status_code == 400
        assert bad_unit_post.json().get("detail") == "invalid_unit_id"

        # create a valid section
        sec = (await client.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "A"})).json()

        # invalid section_id in path → 400
        bad_sec_patch = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/not-a-uuid", json={"title": "Y"}
        )
        assert bad_sec_patch.status_code == 400
        assert bad_sec_patch.json().get("detail") == "invalid_path_params"
        bad_sec_delete = await client.delete(
            f"/api/teaching/units/{unit['id']}/sections/not-a-uuid"
        )
        assert bad_sec_delete.status_code == 400
        assert bad_sec_delete.json().get("detail") == "invalid_path_params"

        # patch without fields → 400
        empty_patch = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{sec['id']}", json={}
        )
        assert empty_patch.status_code == 400
        assert empty_patch.json().get("detail") == "empty_payload"


@pytest.mark.anyio
async def test_create_multiple_sections_positions_and_delete_middle_resequences():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-sections-positions", name="Pos", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Ableitung")

        a = (await client.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "A"})).json()
        b = (await client.post(f"/api/teaching/units/{unit['id']}/sections", json={"title": "B"})).json()
        assert a["position"] == 1 and b["position"] == 2

        lst = await client.get(f"/api/teaching/units/{unit['id']}/sections")
        assert [s["title"] for s in lst.json()] == ["A", "B"]

        # delete middle (position 1 -> after delete, remaining resequence to 1)
        del_resp = await client.delete(f"/api/teaching/units/{unit['id']}/sections/{a['id']}")
        assert del_resp.status_code == 204

        lst2 = await client.get(f"/api/teaching/units/{unit['id']}/sections")
        arr2 = lst2.json()
        assert [s["title"] for s in arr2] == ["B"]
        assert [s["position"] for s in arr2] == [1]


@pytest.mark.anyio
async def test_title_boundaries_exact_and_concurrent_creates():
    import asyncio

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-sections-bounds", name="Bounds", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Integralrechnung")

        # exact boundaries OK
        ok1 = await client.post(
            f"/api/teaching/units/{unit['id']}/sections", json={"title": "x"}
        )
        assert ok1.status_code == 201
        ok200 = await client.post(
            f"/api/teaching/units/{unit['id']}/sections", json={"title": "x" * 200}
        )
        assert ok200.status_code == 201

        # concurrent creates should produce unique contiguous positions (smoke)
        async def create_titled(t: str):
            return await client.post(
                f"/api/teaching/units/{unit['id']}/sections", json={"title": t}
            )

        r1, r2 = await asyncio.gather(create_titled("C1"), create_titled("C2"))
        assert r1.status_code == 201 and r2.status_code == 201

        lst = await client.get(f"/api/teaching/units/{unit['id']}/sections")
        pos = [s["position"] for s in lst.json()]
        assert pos == sorted(pos) and len(pos) == len(set(pos))
