"""
Teaching API — Task kinds (H5P + Visual)

Why:
    GUSTAV integrates H5P as an additional task kind (`h5p`) and introduces a
    second special kind (`visual`). Both are configured via optional config
    objects on TaskCreate/TaskUpdate:

        - `h5p`: creates/updates an H5P task (stores `content_id`)
        - `visual`: creates/updates a visual task (upload-only in learning)

    The `kind` field is read-only in the API. Clients choose the task kind by
    providing exactly one of these config objects.
"""

from __future__ import annotations

from pathlib import Path
import os
import pytest
import httpx
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))

# Allow DBTeachingRepo guardrails in tests.
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


async def _create_unit(client: httpx.AsyncClient, title: str = "Unit") -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Section") -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


@pytest.mark.anyio
async def test_create_h5p_task_sets_kind_and_returns_h5p_config():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed teaching repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p", name="T", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        unit = await _create_unit(c)
        section = await _create_section(c, unit["id"])

        r = await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={
                "instruction_md": "H5P placeholder",
                "h5p": {"content_id": None, "display_options": {"theme": "light"}},
            },
        )
        assert r.status_code == 201
        task = r.json()
        assert task["kind"] == "h5p"
        assert task["h5p"]["content_id"] is None
        assert task["h5p"]["display_options"] == {"theme": "light"}
        assert task.get("visual") is None


@pytest.mark.anyio
async def test_create_visual_task_sets_kind_and_returns_visual_config():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed teaching repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-visual", name="T", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        unit = await _create_unit(c)
        section = await _create_section(c, unit["id"])

        r = await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "Visual task", "visual": {}},
        )
        assert r.status_code == 201
        task = r.json()
        assert task["kind"] == "visual"
        assert task.get("h5p") is None
        assert task["visual"] == {}


@pytest.mark.anyio
async def test_create_task_rejects_h5p_and_visual_together():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed teaching repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-conflict", name="T", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        unit = await _create_unit(c)
        section = await _create_section(c, unit["id"])

        r = await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={
                "instruction_md": "Invalid",
                "h5p": {"content_id": None},
                "visual": {},
            },
        )
        assert r.status_code == 400
        assert r.json()["error"] == "bad_request"
        assert r.json()["detail"] in {"invalid_input", "invalid_task_kind_config"}


@pytest.mark.anyio
async def test_update_h5p_task_allows_setting_content_id():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed teaching repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-update", name="T", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        unit = await _create_unit(c)
        section = await _create_section(c, unit["id"])
        r_create = await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "H5P placeholder", "h5p": {"content_id": None}},
        )
        assert r_create.status_code == 201
        task = r_create.json()
        assert task["kind"] == "h5p"

        r_patch = await c.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}",
            json={"h5p": {"content_id": "123", "display_options": {}}},
        )
        assert r_patch.status_code == 200
        patched = r_patch.json()
        assert patched["kind"] == "h5p"
        assert patched["h5p"]["content_id"] == "123"


@pytest.mark.anyio
async def test_update_h5p_task_rejects_non_numeric_content_id():
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed teaching repo required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-h5p-bad-cid", name="T", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)

        unit = await _create_unit(c)
        section = await _create_section(c, unit["id"])
        r_create = await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "H5P placeholder", "h5p": {"content_id": None}},
        )
        assert r_create.status_code == 201
        task = r_create.json()

        r_patch = await c.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{task['id']}",
            json={"h5p": {"content_id": "not-a-number", "display_options": {}}},
        )
        assert r_patch.status_code == 400
        body = r_patch.json() or {}
        assert body.get("error") == "bad_request"
        assert body.get("detail") == "invalid_h5p_config"
