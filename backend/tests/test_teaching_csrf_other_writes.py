"""
Teaching API — CSRF same-origin checks for additional write endpoints

Covers representative endpoints beyond visibility:
- POST /api/teaching/courses
- PATCH /api/teaching/courses/{course_id}
- POST /api/teaching/courses/{course_id}/members
- POST /api/teaching/units

Asserts 403 with detail=csrf_violation on cross-origin requests and success on
same-origin, with private, no-store cache headers on both paths.
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport
import uuid

import main  # type: ignore  # noqa: E402
import routes.teaching as teaching  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_course_same_origin(c: httpx.AsyncClient, *, title: str = "Kurs") -> str:
    r = await c.post("/api/teaching/courses", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _create_unit_same_origin(c: httpx.AsyncClient, *, title: str = "Unit") -> str:
    r = await c.post("/api/teaching/units", json={"title": title}, headers={"Origin": "http://test"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _create_section_same_origin(c: httpx.AsyncClient, unit_id: str, *, title: str = "Abschnitt") -> str:
    r = await c.post(
        f"/api/teaching/units/{unit_id}/sections",
        json={"title": title},
        headers={"Origin": "http://test"},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


@pytest.mark.anyio
async def test_create_course_blocks_cross_origin_and_allows_same_origin(monkeypatch: pytest.MonkeyPatch):
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-course", name="Teach", roles=["teacher"])  # type: ignore
    csrf_calls = {"count": 0}
    original_guard = teaching._csrf_guard

    def _counting_guard(request):
        csrf_calls["count"] += 1
        return original_guard(request)

    monkeypatch.setattr(teaching, "_csrf_guard", _counting_guard)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Cross-origin → 403 + csrf_violation
        r = await c.post("/api/teaching/courses", json={"title": "Kurs"}, headers={"Origin": "http://evil.local"})
        assert r.status_code == 403
        assert r.json().get("detail") == "csrf_violation"
        assert r.headers.get("Cache-Control") == "private, no-store"

        # Same-origin → 201 + private cache headers
        csrf_calls["count"] = 0
        r2 = await c.post("/api/teaching/courses", json={"title": "Kurs"}, headers={"Origin": "http://test"})
        assert r2.status_code == 201
        assert r2.headers.get("Cache-Control") == "private, no-store"
        assert csrf_calls["count"] == 1, "CSRF guard should be evaluated exactly once per request"


@pytest.mark.anyio
async def test_update_course_blocks_missing_origin_and_sets_private_cache_headers():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-course-patch", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course_same_origin(c, title="Kurs Alt")

        # Missing Origin/Referer must be rejected.
        r_missing = await c.patch(f"/api/teaching/courses/{course_id}", json={"title": "Neu"})
        assert r_missing.status_code == 403
        assert r_missing.json().get("detail") == "csrf_violation"
        assert r_missing.headers.get("Cache-Control") == "private, no-store"

        # Same-origin request succeeds and stays non-cacheable.
        r_ok = await c.patch(
            f"/api/teaching/courses/{course_id}",
            json={"title": "Neu"},
            headers={"Origin": "http://test"},
        )
        assert r_ok.status_code == 200
        assert r_ok.json().get("title") == "Neu"
        assert r_ok.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_add_member_blocks_missing_origin_and_sets_private_cache_headers():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-member-post", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course_same_origin(c, title="Kurs Mitglieder")

        # Missing Origin/Referer must be rejected.
        r_missing = await c.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": "student-a"},
        )
        assert r_missing.status_code == 403
        assert r_missing.json().get("detail") == "csrf_violation"
        assert r_missing.headers.get("Cache-Control") == "private, no-store"

        # Same-origin validation errors still must be private/no-store.
        r_bad = await c.post(
            f"/api/teaching/courses/{course_id}/members",
            json={},
            headers={"Origin": "http://test"},
        )
        assert r_bad.status_code == 400
        assert r_bad.headers.get("Cache-Control") == "private, no-store"

        # Same-origin happy path.
        r_ok = await c.post(
            f"/api/teaching/courses/{course_id}/members",
            json={"student_sub": "student-a"},
            headers={"Origin": "http://test"},
        )
        assert r_ok.status_code in (201, 204)
        assert r_ok.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_create_unit_blocks_cross_origin_and_allows_same_origin(monkeypatch: pytest.MonkeyPatch):
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-unit", name="Teach", roles=["teacher"])  # type: ignore
    csrf_calls = {"count": 0}
    original_guard = teaching._csrf_guard

    def _counting_guard(request):
        csrf_calls["count"] += 1
        return original_guard(request)

    monkeypatch.setattr(teaching, "_csrf_guard", _counting_guard)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        # Cross-origin → 403 + csrf_violation
        r = await c.post("/api/teaching/units", json={"title": "Unit"}, headers={"Origin": "http://evil.local"})
        assert r.status_code == 403
        assert r.json().get("detail") == "csrf_violation"
        assert r.headers.get("Cache-Control") == "private, no-store"

        # Same-origin → 201 + private cache headers
        csrf_calls["count"] = 0
        r2 = await c.post("/api/teaching/units", json={"title": "Unit"}, headers={"Origin": "http://test"})
        assert r2.status_code == 201
        assert r2.headers.get("Cache-Control") == "private, no-store"
        assert csrf_calls["count"] == 1, "CSRF guard should be evaluated exactly once per request"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path_tpl", "payload"),
    [
        ("POST", "/api/teaching/units/{unit_id}/phases", {"title": "Phase 2"}),
        ("POST", "/api/teaching/units/{unit_id}/modules", {"title": "M", "phase_id": "{phase_id}"}),
        (
            "POST",
            "/api/teaching/units/{unit_id}/modules/edges",
            {"from_module_id": "{module_a}", "to_module_id": "{module_b}"},
        ),
    ],
)
async def test_modular_write_endpoints_reject_missing_origin_with_csrf_violation(
    method: str,
    path_tpl: str,
    payload: dict,
):
    """New modular write endpoints must enforce strict same-origin CSRF checks."""
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-modular", name="Teach", roles=["teacher"])  # type: ignore

    unit_id = str(uuid.uuid4())
    phase_id = str(uuid.uuid4())
    module_a = str(uuid.uuid4())
    module_b = str(uuid.uuid4())
    path = (
        path_tpl.replace("{unit_id}", unit_id)
        .replace("{phase_id}", phase_id)
        .replace("{module_a}", module_a)
        .replace("{module_b}", module_b)
    )
    body = {
        key: str(value)
        .replace("{phase_id}", phase_id)
        .replace("{module_a}", module_a)
        .replace("{module_b}", module_b)
        for key, value in payload.items()
    }

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        resp = await c.request(method, path, json=body)

    assert resp.status_code == 403
    assert resp.json().get("detail") == "csrf_violation"
    assert resp.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_course_module_create_requires_same_origin_and_sets_private_cache_headers():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-course-mod-create", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course_same_origin(c, title="Kurs Module")
        unit_id = await _create_unit_same_origin(c, title="Unit Module")

        r_missing = await c.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit_id},
        )
        assert r_missing.status_code == 403
        assert r_missing.json().get("detail") == "csrf_violation"
        assert r_missing.headers.get("Cache-Control") == "private, no-store"

        r_ok = await c.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit_id},
            headers={"Origin": "http://test"},
        )
        assert r_ok.status_code == 201
        assert r_ok.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_course_module_reorder_requires_same_origin():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-course-mod-reorder", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        course_id = await _create_course_same_origin(c, title="Kurs Reorder")
        unit_id = await _create_unit_same_origin(c, title="Unit Reorder")
        module = await c.post(
            f"/api/teaching/courses/{course_id}/modules",
            json={"unit_id": unit_id},
            headers={"Origin": "http://test"},
        )
        assert module.status_code == 201, module.text
        module_id = str(module.json().get("id"))

        r_missing = await c.post(
            f"/api/teaching/courses/{course_id}/modules/reorder",
            json={"module_ids": [module_id]},
        )
        assert r_missing.status_code == 403
        assert r_missing.json().get("detail") == "csrf_violation"
        assert r_missing.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_material_create_requires_same_origin_and_sets_private_cache_headers():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-material-create", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        unit_id = await _create_unit_same_origin(c, title="Unit Material")
        section_id = await _create_section_same_origin(c, unit_id, title="Abschnitt Material")

        r_missing = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            json={"title": "M", "body_md": "x"},
        )
        assert r_missing.status_code == 403
        assert r_missing.json().get("detail") == "csrf_violation"
        assert r_missing.headers.get("Cache-Control") == "private, no-store"

        r_ok = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            json={"title": "M", "body_md": "x"},
            headers={"Origin": "http://test"},
        )
        assert r_ok.status_code == 201
        assert r_ok.headers.get("Cache-Control") == "private, no-store"


@pytest.mark.anyio
async def test_material_reorder_requires_same_origin():
    teaching.set_repo(teaching._Repo())  # type: ignore[attr-defined]
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-csrf-material-reorder", name="Teach", roles=["teacher"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        unit_id = await _create_unit_same_origin(c, title="Unit Material Reorder")
        section_id = await _create_section_same_origin(c, unit_id, title="Abschnitt Material Reorder")
        material = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            json={"title": "M", "body_md": "x"},
            headers={"Origin": "http://test"},
        )
        assert material.status_code == 201, material.text
        material_id = str(material.json().get("id"))

        r_missing = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/reorder",
            json={"material_ids": [material_id]},
        )
        assert r_missing.status_code == 403
        assert r_missing.json().get("detail") == "csrf_violation"
        assert r_missing.headers.get("Cache-Control") == "private, no-store"
