"""
Teaching API — Summary falls back to humanized legacy-email SUBs

We simulate a directory resolver that returns the original SUB (no match) for
all requested users. For members whose `student_sub` is a legacy-email:… value,
the API should return a humanized display name derived from the email localpart
("legacy-email:max.mustermann@schule.de" -> "Max Mustermann").

For non-email-like SUBs, the API should keep returning "Unbekannt".
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
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


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
async def test_summary_humanizes_legacy_email_sub_and_hides_random_ids(monkeypatch):
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required")

    # Directory returns identity mapping (simulates not found in KC)
    def _fake_dir_resolve(subs: list[str]) -> dict[str, str]:
        return {sid: sid for sid in subs}

    # Monkeypatch the directory used by the API adapter
    import identity_access.directory as dir_mod  # type: ignore
    monkeypatch.setattr(dir_mod, "resolve_student_names", _fake_dir_resolve)

    main.SESSION_STORE = SessionStore()
    owner = main.SESSION_STORE.create(sub="t-legacy-owner", name="Owner", roles=["teacher"])  # type: ignore

    legacy_sub = "legacy-email:raphael.fournell@schule.de"
    random_sub = "not-a-uuid-sub-xyz"

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, owner.session_id)
        cid = await _create_course(c, "Kurs Legacy Names")
        unit = await _create_unit(c, "Einheit Legacy Names")
        await _attach_unit(c, cid, unit["id"])
        await _add_member(c, cid, legacy_sub)
        await _add_member(c, cid, random_sub)

        r = await c.get(
            f"/api/teaching/courses/{cid}/units/{unit['id']}/submissions/summary",
            params={"limit": 100, "offset": 0},
        )
        assert r.status_code == 200
        rows = r.json().get("rows") or []
        assert len(rows) >= 2
        names_by_sub = {row["student"]["sub"]: row["student"]["name"] for row in rows}

        # Legacy email must be humanized: "Raphael Fournell" (no '@', no prefix)
        legacy_name = names_by_sub.get(legacy_sub, "")
        assert legacy_name and "@" not in legacy_name and not legacy_name.startswith("legacy-email:")
        assert legacy_name == "Raphael Fournell"

        # Random SUB should remain Unbekannt (no false humanization)
        assert names_by_sub.get(random_sub, "") == "Unbekannt"

