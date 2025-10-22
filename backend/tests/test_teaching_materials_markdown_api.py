"""
Teaching API — Section Materials (contract-first, Markdown-only phase)

Defines the behaviour of CRUD + reorder endpoints for Markdown materials inside
unit sections. The tests expect that the OpenAPI contract already contains the
paths and schemas. They intentionally fail until the implementation exists
according to the red-green-refactor TDD workflow.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

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


async def _create_unit(client: httpx.AsyncClient, title: str = "Physik") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Kapitel") -> dict:
    resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_material(
    client: httpx.AsyncClient, unit_id: str, section_id: str, title: str, body: str
) -> dict:
    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
        json={"title": title, "body_md": body},
    )
    assert resp.status_code == 201
    return resp.json()


async def _list_material_ids(client: httpx.AsyncClient, unit_id: str, section_id: str) -> list[str]:
    resp = await client.get(f"/api/teaching/units/{unit_id}/sections/{section_id}/materials")
    assert resp.status_code == 200
    return [item["id"] for item in resp.json()]


@pytest.mark.anyio
async def test_materials_require_auth_and_author_role():
    main.SESSION_STORE = SessionStore()

    async with (await _client()) as client:
        resp = await client.get(
            "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/"
            "00000000-0000-0000-0000-000000000000/materials"
        )
        assert resp.status_code == 401

    student = main.SESSION_STORE.create(sub="student-materials", name="Max", roles=["student"])
    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        resp = await client.post(
            "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/"
            "00000000-0000-0000-0000-000000000000/materials",
            json={"title": "Nope", "body_md": "n/a"},
        )
        assert resp.status_code == 403


@pytest.mark.anyio
async def test_author_can_crud_materials_and_non_author_is_blocked():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-materials-A", name="Autor", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-materials-B", name="Fremd", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Optik")
        section = await _create_section(client, unit["id"], title="Linsen")

        # list empty
        lst0 = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials"
        )
        assert lst0.status_code == 200
        assert lst0.json() == []

        created = await _create_material(
            client, unit["id"], section["id"], title="Einführung", body="## Agenda"
        )
        assert created["position"] == 1
        assert created["title"] == "Einführung"

        # list shows one material
        ids = await _list_material_ids(client, unit["id"], section["id"])
        assert ids == [created["id"]]

        # non-author forbidden to change or list
        client.cookies.set("gustav_session", other.session_id)
        forbidden_list = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials"
        )
        assert forbidden_list.status_code == 403
        forbidden_patch = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{created['id']}",
            json={"title": "Nope"},
        )
        assert forbidden_patch.status_code == 403
        forbidden_delete = await client.delete(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{created['id']}"
        )
        assert forbidden_delete.status_code == 403

        # author updates and deletes
        client.cookies.set("gustav_session", author.session_id)
        patched = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{created['id']}",
            json={"title": "Grundlagen", "body_md": "## Inhalte"},
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Grundlagen"

        deleted = await client.delete(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{created['id']}"
        )
        assert deleted.status_code == 204
        assert deleted.text == ""

        lst1 = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials"
        )
        assert lst1.status_code == 200
        assert lst1.json() == []


@pytest.mark.anyio
async def test_material_validation_and_unknown_ids():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-materials-validate", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Akustik")
        section = await _create_section(client, unit["id"], title="Wellen")

        too_short = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials",
            json={"title": "", "body_md": "x"},
        )
        assert too_short.status_code == 400
        assert too_short.json().get("detail") == "invalid_title"

        too_long = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials",
            json={"title": "x" * 201, "body_md": "x"},
        )
        assert too_long.status_code == 400
        assert too_long.json().get("detail") == "invalid_title"

        missing_body = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials",
            json={"title": "Ohne Body"},
        )
        assert missing_body.status_code == 400
        assert missing_body.json().get("detail") == "invalid_body_md"

        invalid_body_type = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials",
            json={"title": "Falsch", "body_md": 123},
        )
        assert invalid_body_type.status_code == 400
        assert invalid_body_type.json().get("detail") == "invalid_body_md"

        bad_path = await client.get(
            f"/api/teaching/units/not-a-uuid/sections/{section['id']}/materials"
        )
        assert bad_path.status_code == 400
        assert bad_path.json().get("detail") == "invalid_unit_id"

        unknown_material = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/"
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            json={"title": "Nope"},
        )
        assert unknown_material.status_code == 404


def _assert_positions(materials: Sequence[dict], expected_ids: Sequence[str]) -> None:
    got_ids = [m["id"] for m in materials]
    got_positions = [m["position"] for m in materials]
    assert got_ids == list(expected_ids)
    assert got_positions == list(range(1, len(expected_ids) + 1))


@pytest.mark.anyio
async def test_material_reorder_and_payload_guards():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-materials-reorder", name="Autor", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-materials-reorder-other", name="Fremd", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Mechanik")
        section = await _create_section(client, unit["id"], title="Dynamik")
        m1 = await _create_material(client, unit["id"], section["id"], title="A", body="A")
        m2 = await _create_material(client, unit["id"], section["id"], title="B", body="B")
        m3 = await _create_material(client, unit["id"], section["id"], title="C", body="C")

        reorder_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/reorder",
            json={"material_ids": [m3["id"], m1["id"], m2["id"]]},
        )
        assert reorder_resp.status_code == 200
        reordered = reorder_resp.json()
        _assert_positions(reordered, [m3["id"], m1["id"], m2["id"]])

        # invalid payload shapes
        not_array = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/reorder",
            json={"material_ids": "not-array"},
        )
        assert not_array.status_code == 400
        assert not_array.json().get("detail") == "material_ids_must_be_array"

        mismatch = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/reorder",
            json={"material_ids": [m1["id"], m2["id"]]},
        )
        assert mismatch.status_code == 400
        assert mismatch.json().get("detail") == "material_mismatch"

        duplicate = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/reorder",
            json={"material_ids": [m1["id"], m1["id"], m2["id"]]},
        )
        assert duplicate.status_code == 400
        assert duplicate.json().get("detail") == "duplicate_material_ids"

        empty = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/reorder",
            json={"material_ids": []},
        )
        assert empty.status_code == 400
        assert empty.json().get("detail") == "empty_material_ids"

        # non-author forbidden
        client.cookies.set("gustav_session", other.session_id)
        forbidden = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/reorder",
            json={"material_ids": [m1["id"], m2["id"], m3["id"]]},
        )
        assert forbidden.status_code == 403
