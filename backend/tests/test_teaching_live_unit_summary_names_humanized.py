"""
Teaching API — Summary returns humanized student names (no SUBs/emails)

We stub the directory resolver to return usernames/emails and assert that the
summary endpoint returns humanized names only.
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


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


@pytest.mark.anyio
async def test_summary_humanizes_student_names(monkeypatch):
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    # Force directory resolver to return email/legacy patterns (unhumanized)
    # The API's adapter must humanize these names before returning the summary.
    def _fake_dir_resolve(subs: list[str]) -> dict[str, str]:
        m = {}
        for i, sid in enumerate(subs):
            m[sid] = "legacy-email:raphael.fournell" if i == 0 else "alice@example.com"
        return m

    import identity_access.directory as dir_mod  # type: ignore
    monkeypatch.setattr(dir_mod, "resolve_student_names", _fake_dir_resolve)

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-humanize-owner", name="Owner", roles=["teacher"])  # type: ignore
    s1 = "sub-1"
    s2 = "sub-2"

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Kurs Namen")
        unit = await _create_unit(c, "Einheit Namen")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, s1)
        await _add_member(c, cid, s2)

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200
        body = r.json()
        rows = body.get("rows") or []
        assert rows, "expected rows with members"
        names = [row["student"]["name"] for row in rows]
        # Must not include SUBs, raw emails, or legacy prefixes
        assert not any(n.startswith("legacy-email:") for n in names)
        assert not any("@" in n for n in names)
        # Expect humanized names
        assert any(n == "Raphael Fournell" for n in names)
        assert any(n.startswith("Alice") for n in names)
