"""
Teaching API — Unit Sections Reorder (contract-first, TDD)

Validates atomic reordering of sections within a unit, including error cases
for duplicates/missing/invalid IDs and edge cases like single-item reorder.
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


def _require_db_or_skip() -> None:
    dsn = os.getenv("DATABASE_URL") or ""
    try:
        import psycopg  # type: ignore

        with psycopg.connect(dsn, connect_timeout=1):
            return
    except Exception:
        pytest.skip("Database not reachable; ensure migrations applied and DATABASE_URL set")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    resp = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.anyio
async def test_sections_reorder_happy_and_get_reflects_order():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-sec-reorder", name="ReOrder", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, "Mechanik")

        a = await _create_section(client, unit["id"], "A")
        b = await _create_section(client, unit["id"], "B")
        c = await _create_section(client, unit["id"], "C")

        payload = {"section_ids": [c["id"], a["id"], b["id"]]}
        resp = await client.post(f"/api/teaching/units/{unit['id']}/sections/reorder", json=payload)
        assert resp.status_code == 200
        ordered = resp.json()
        assert [s["id"] for s in ordered] == [c["id"], a["id"], b["id"]]
        assert [s["position"] for s in ordered] == [1, 2, 3]

        # GET reflects new order
        lst = await client.get(f"/api/teaching/units/{unit['id']}/sections")
        assert [s["id"] for s in lst.json()] == [c["id"], a["id"], b["id"]]


@pytest.mark.anyio
async def test_sections_reorder_validation_rules():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-sec-reorder-validate", name="ValidSec", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, "Optik")

        a = await _create_section(client, unit["id"], "A")
        b = await _create_section(client, unit["id"], "B")

        # Duplicate IDs → 400
        dup = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": [a["id"], a["id"]]},
        )
        assert dup.status_code == 400

        # Missing ID → 400
        missing = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": [a["id"]]},
        )
        assert missing.status_code == 400

        # Extraneous ID → 400
        extra = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": [a["id"], str(uuid4()), b["id"]]},
        )
        assert extra.status_code == 400

        # Invalid UUID → 400
        invalid = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": [a["id"], "not-a-uuid", b["id"]]},
        )
        assert invalid.status_code == 400


@pytest.mark.anyio
async def test_sections_reorder_single_item_and_empty_list():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-sec-reorder-edge", name="Edge", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, "Thermodynamik")

        only = await _create_section(client, unit["id"], "Only")
        single = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": [only["id"]]},
        )
        assert single.status_code == 200
        assert [s["id"] for s in single.json()] == [only["id"]]
        assert [s["position"] for s in single.json()] == [1]

        # Empty list → 400
        empty = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": []},
        )
        assert empty.status_code == 400


@pytest.mark.anyio
async def test_non_author_reorder_forbidden_403():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-sec-reorder-owner", name="Owner", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-sec-reorder-other", name="Other", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, "Akustik")
        a = await _create_section(client, unit["id"], "A")
        b = await _create_section(client, unit["id"], "B")

        client.cookies.set("gustav_session", other.session_id)
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder",
            json={"section_ids": [a["id"], b["id"]]},
        )
        assert resp.status_code in (403, 404)


@pytest.mark.anyio
async def test_reorder_idempotent_and_cross_unit_section_returns_404():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-sec-reorder-idem", name="Idem", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit1 = await _create_unit(client, "Elektrizität")
        unit2 = await _create_unit(client, "Magnetismus")

        a = await _create_section(client, unit1["id"], "A")
        b = await _create_section(client, unit1["id"], "B")
        c = await _create_section(client, unit2["id"], "C")

        # idempotent
        idem = await client.post(
            f"/api/teaching/units/{unit1['id']}/sections/reorder",
            json={"section_ids": [a["id"], b["id"]]},
        )
        assert idem.status_code == 200
        assert [s["position"] for s in idem.json()] == [1, 2]

        # cross-unit id → 404
        cross = await client.post(
            f"/api/teaching/units/{unit1['id']}/sections/reorder",
            json={"section_ids": [a["id"], c["id"]]},
        )
        assert cross.status_code == 404


@pytest.mark.anyio
async def test_reorder_invalid_json_type_returns_400():
    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-sec-reorder-json", name="Json", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, "Strahlung")
        a = await _create_section(client, unit["id"], "A")

        # section_ids is not an array → 400
        bad_type1 = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder", json={"section_ids": None}
        )
        assert bad_type1.status_code == 400
        bad_type2 = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/reorder", json={"section_ids": a["id"]}
        )
        assert bad_type2.status_code == 400
