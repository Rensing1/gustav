"""Explicit teacher catalog dependencies, ownership parameters and scheduling."""

from __future__ import annotations

import asyncio
import importlib
import threading
from pathlib import Path

import httpx
import pytest

from backend.web.main import create_app
from backend.web.teacher_catalog_providers import TeacherCatalogProviders

pytestmark = pytest.mark.anyio("asyncio")
HOME_PATH = "/api/teaching/views/teacher-home"
CATALOG_PATH = "/api/teaching/views/units/catalog"


class CatalogRepository:
    def __init__(self, label="A"):
        self.label = label
        self.course_reads = 0

    def list_courses_for_teacher(self, *, teacher_id, limit, offset):
        assert teacher_id == "owner" and (limit, offset) == (200, 0)
        self.course_reads += 1
        return [{"id": "course-z", "title": "Zukunft"}, {"id": "course-a", "title": "Anfang"}]

    def list_course_units_for_owner(self, course_id, owner_sub):
        assert owner_sub == "owner"
        return [{"id": "active"}] if course_id == "course-z" else []

    def list_units_for_author(self, *, author_id, limit, offset):
        assert author_id == "owner" and (limit, offset) == (200, 0)
        return [
            {"id": key, "title": self.label + title, "summary": summary, "updated_at": date}
            for key, title, summary, date in [
                ("draft", " Entwurf", "", "2026-01-01"),
                ("active", " Unterricht", " Demokratie ", "2026-01-02"),
                ("working", " Arbeit", "", "2026-01-03"),
                ("fourth", " Vierte", "", "2026-01-04"),
            ]
        ]

    def list_sections_for_author(self, unit_id, author_id):
        assert author_id == "owner"
        return [{"updated_at": "2026-02-01"}] if unit_id in ("active", "working") else []

    def list_catalog_course_refs(self, *, owner_sub, course_ids):
        assert owner_sub == "owner"
        return [
            {"course_id": course_id, "unit_id": unit["id"]}
            for course_id in course_ids
            for unit in self.list_course_units_for_owner(course_id, owner_sub)
        ]

    def list_catalog_section_summaries(self, *, owner_sub, unit_ids):
        assert owner_sub == "owner"
        return {
            unit_id: {"count": 1, "updated_at": "2026-02-01"}
            for unit_id in unit_ids if unit_id in ("active", "working")
        }


def client_for(repo, *, role="teacher", factory=None):
    app = create_app(
        teacher_catalog_providers=TeacherCatalogProviders(repository=factory or (lambda: repo)),
        access_token_verifier=lambda token, cfg: {
            "sub": "owner",
            "realm_access": {"roles": [role]},
        },
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test.jwt"},
    )


async def test_catalog_and_home_share_rules_without_global_test_overrides():
    first, second = CatalogRepository("A"), CatalogRepository("B")
    async with client_for(first) as a, client_for(second) as b:
        for client, label in ((a, "A"), (b, "B"), (a, "A")):
            response = await client.get(CATALOG_PATH)
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "private, no-store"
            items = response.json()["items"]
            assert [item["id"] for item in items] == ["active", "working", "fourth", "draft"]
            assert all(item["title"].startswith(label) for item in items)
            assert [item["status_label"] for item in items] == [
                "Aktiv im Unterricht",
                "In Bearbeitung",
                "Entwurf",
                "Entwurf",
            ]
            assert items[0]["topic"] == "Demokratie"
            assert items[0]["courses"] == [
                {"id": "course-z", "title": "Zukunft", "href": "/teaching/courses/course-z"}
            ]
            assert items[0]["updated_at"] == "2026-02-01"
            home = (await client.get(HOME_PATH)).json()
            assert [item["id"] for item in home["recent_units"]] == [
                item["id"] for item in items[:3]
            ]
            assert [item["id"] for item in home["courses"]] == ["course-a", "course-z"]
    assert first.course_reads == 4 and second.course_reads == 2


async def test_query_sort_and_empty_catalog():
    async with client_for(CatalogRepository()) as client:
        filtered = (await client.get(CATALOG_PATH, params={"query": " DEMOKRATIE "})).json()
        assert filtered["query"] == "DEMOKRATIE" and filtered["result_count"] == 1
        sorted_view = (await client.get(CATALOG_PATH, params={"sort": "title_asc"})).json()
        assert [item["id"] for item in sorted_view["items"]] == [
            "working",
            "draft",
            "active",
            "fourth",
        ]
        assert (await client.get(CATALOG_PATH, params={"query": "missing"})).json()["items"] == []

    class Empty(CatalogRepository):
        def list_units_for_author(self, **kwargs):
            return []

        def list_courses_for_teacher(self, **kwargs):
            return []

    async with client_for(Empty()) as client:
        home = (await client.get(HOME_PATH)).json()
        assert home["courses"] == home["recent_units"] == []


async def test_catalog_never_reads_assignments_or_sections_in_a_loop():
    class Batched(CatalogRepository):
        def list_course_units_for_owner(self, *args):
            pytest.fail("per-course read")

        def list_sections_for_author(self, *args):
            pytest.fail("per-unit read")

        def list_catalog_course_refs(self, *, owner_sub, course_ids):
            assert owner_sub == "owner"
            assert course_ids == ["course-z", "course-a"]
            return [{"course_id": "course-z", "unit_id": "active"}]

    async with client_for(Batched()) as client:
        assert (await client.get(CATALOG_PATH)).status_code == 200
        assert (await client.get(HOME_PATH)).status_code == 200


@pytest.mark.parametrize("path", [HOME_PATH, CATALOG_PATH])
async def test_auth_and_roles_precede_repository_construction(path):
    def forbidden():
        pytest.fail("unauthorized adapter access")

    async with client_for(None, role="student", factory=forbidden) as client:
        assert (await client.get(path)).status_code == 403
        client.headers.pop("Authorization")
        assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("path", [HOME_PATH, CATALOG_PATH])
async def test_repository_unavailable_is_private_and_admin_keeps_access(path):
    from backend.teaching.errors import TeachingRepositoryUnavailable

    def unavailable():
        raise TeachingRepositoryUnavailable()

    async with client_for(None, factory=unavailable) as client:
        response = await client.get(path)
        assert response.status_code == 503
        assert response.json() == {
            "error": "service_unavailable",
            "detail": "teaching_repository_unavailable",
        }
        assert response.headers["Cache-Control"] == "private, no-store"
    async with client_for(CatalogRepository(), role="admin") as client:
        assert (await client.get(path)).status_code == 200


@pytest.mark.parametrize("path", [HOME_PATH, CATALOG_PATH])
async def test_slow_repository_leaves_event_loop_available(path):
    started, release = threading.Event(), threading.Event()

    def factory():
        started.set()
        assert release.wait(5)
        return CatalogRepository()

    async with client_for(None, factory=factory) as client:
        pending = asyncio.create_task(client.get(path))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert (
                await asyncio.wait_for(client.get("/api/app/session-bootstrap"), 1)
            ).status_code == 200
        finally:
            release.set()
            response = await pending
        assert response.status_code == 200


def test_production_provider_is_lazy_and_retryable(monkeypatch):
    wiring = importlib.import_module("backend.web.teacher_catalog_providers")
    calls = []

    def factory():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        return CatalogRepository()

    monkeypatch.setattr(wiring, "DBTeachingRepo", factory)
    providers = wiring.create_teacher_catalog_providers()
    assert calls == []
    with pytest.raises(wiring.TeachingRepositoryUnavailable):
        providers.repository()
    assert providers.repository() is providers.repository()
    assert len(calls) == 2


def test_catalog_service_and_routes_have_no_dynamic_facade():
    for name in ("app_teacher_catalog_routes", "app_teacher_concern_routes"):
        source = Path(importlib.import_module(f"backend.web.routes.{name}").__file__).read_text()
        for forbidden in ("_app_module", "__globals__", "sys.modules", "teaching_routes"):
            assert forbidden not in source
    service = importlib.import_module("backend.teaching.services.unit_catalog")
    source = Path(service.__file__).read_text()
    assert "backend.web" not in source and "fastapi" not in source
