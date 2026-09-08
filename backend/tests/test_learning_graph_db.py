"""Real-DB Learning read parity and membership boundaries with run-owned cleanup."""

import importlib
import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import psycopg
import pytest

from backend.learning.repo_db import DBLearningRepo
from backend.tests.utils.db import is_safe_db_test_dsn, require_db_or_skip
from backend.web.main import create_app

pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]


@pytest.fixture
def app():
    require_db_or_skip()
    claims = {}
    app = create_app(access_token_verifier=lambda token, cfg: claims)
    app.state.claims = claims
    app.state.owner = f"graph-owner-{uuid4()}"
    app.state.student = f"graph-student-{uuid4()}"
    app.state.unit_ids, app.state.course_ids = [], []
    yield app
    dsn = os.environ["RLS_TEST_SERVICE_DSN"]
    assert is_safe_db_test_dsn(dsn)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "delete from public.courses where id = any(%s::uuid[])", (app.state.course_ids,)
        )
        conn.execute("delete from public.units where id = any(%s::uuid[])", (app.state.unit_ids,))


def authenticate(app, role, sub=None):
    app.state.claims.clear()
    app.state.claims.update(
        {
            "sub": sub or (app.state.owner if role == "teacher" else app.state.student),
            "realm_access": {"roles": [role]},
        }
    )


def client_for(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://test", "Authorization": "Bearer test.jwt"},
    )


async def create(client, path, data):
    response = await client.post(path, json=data)
    assert response.status_code == 201, response.text
    return response.json()


async def course(client, app):
    item = await create(
        client,
        "/api/teaching/courses",
        {
            "title": "Graphprüfung",
            "subject": "Testfach",
            "grade_level": "10",
            "school_year_start": 2026,
        },
    )
    app.state.course_ids.append(item["id"])
    return item["id"]


async def unit(client, app, kind="modular"):
    item = await create(client, "/api/teaching/units", {"title": "Graphprüfung", "unit_type": kind})
    app.state.unit_ids.append(item["id"])
    return item["id"]


async def attach_and_enroll(client, app, course_id, unit_id):
    await create(client, f"/api/teaching/courses/{course_id}/modules", {"unit_id": unit_id})
    response = await client.post(
        f"/api/teaching/courses/{course_id}/members", json={"student_sub": app.state.student}
    )
    assert response.status_code in (201, 204)


def graph_path(course_id, unit_id):
    return f"/api/learning/courses/{course_id}/units/{unit_id}/modules/graph"


async def test_h5p_access_respects_reused_content_releases_and_membership(app):
    """Any accessible task permits reused content; removing all access denies it."""
    authenticate(app, "teacher")
    async with client_for(app) as client:
        course_id, unit_id = await course(client, app), await unit(client, app, kind="linear")
        module = await create(
            client, f"/api/teaching/courses/{course_id}/modules", {"unit_id": unit_id}
        )
        content_id = str(uuid4().int)
        sections = []
        for title in ("Erste H5P-Aufgabe", "Zweite H5P-Aufgabe"):
            section = await create(
                client, f"/api/teaching/units/{unit_id}/sections", {"title": title}
            )
            sections.append(section["id"])
            await create(
                client,
                f"/api/teaching/units/{unit_id}/sections/{section['id']}/tasks",
                {"instruction_md": title, "criteria": [], "h5p": {"content_id": content_id}},
            )
        await create(
            client, f"/api/teaching/courses/{course_id}/members", {"student_sub": app.state.student}
        )
        path = f"/api/learning/courses/{course_id}/h5p/contents/{content_id}/access"

        async def expect_access(status, target=path):
            authenticate(app, "student")
            response = await client.get(target)
            assert response.status_code == status
            assert response.headers["cache-control"] == "private, no-store"
            if status == 204:
                assert response.content == b""
            else:
                assert response.json() == {"error": "not_found"}

        async def release(section_id, visible):
            authenticate(app, "teacher")
            response = await client.patch(
                f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section_id}/visibility",
                json={"visible": visible},
            )
            assert response.status_code == 200

        await expect_access(404)
        for section_id in sections:
            await release(section_id, True)
        await expect_access(204)
        await expect_access(404, path.replace(content_id, str(uuid4().int)))
        await expect_access(404, path.replace(course_id, str(uuid4())))
        authenticate(app, "student", sub=f"outsider-{uuid4()}")
        assert (await client.get(path)).status_code == 404
        await release(sections[0], False)
        await expect_access(204)
        await release(sections[1], False)
        await expect_access(404)
        await release(sections[0], True)
        await expect_access(204)
        authenticate(app, "teacher")
        removed = await client.delete(
            f"/api/teaching/courses/{course_id}/members/{app.state.student}"
        )
        assert removed.status_code == 204
        await expect_access(404)


@pytest.mark.parametrize("unit_kind", ["linear", "modular"])
async def test_upload_intents_enforce_current_database_visibility(app, monkeypatch, unit_kind):
    """Sign only visible tasks; revoking access prevents any further signing."""
    calls = []

    def presign(**kwargs):
        calls.append(kwargs)
        return {"url": "https://storage.example/upload", "headers": kwargs["headers"]}

    routes = importlib.import_module("backend.web.routes.learning_upload_intents")
    monkeypatch.setattr(routes, "_current_storage_adapter", lambda: SimpleNamespace(presign_upload=presign))
    monkeypatch.setenv("LEARNING_STORAGE_BUCKET", "submissions")
    authenticate(app, "teacher")
    async with client_for(app) as client:
        course_id, unit_id = await course(client, app), await unit(client, app, kind=unit_kind)
        section = await create(client, f"/api/teaching/units/{unit_id}/sections", {"title": "Uploadprüfung"})
        task = await create(client, f"/api/teaching/units/{unit_id}/sections/{section['id']}/tasks", {"instruction_md": "Lade deine Lösung hoch.", "criteria": []})
        module = await create(client, f"/api/teaching/courses/{course_id}/modules", {"unit_id": unit_id})
        path = f"/api/learning/courses/{course_id}/tasks/{task['id']}/upload-intents"

        async def expect_intent(status, target=path):
            authenticate(app, "student")
            before = len(calls)
            response = await client.post(target, json={"kind": "image", "filename": "bild.png", "mime_type": "image/png", "size_bytes": 10})
            assert response.status_code == status, response.text
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["vary"] == "Origin"
            assert len(calls) == before + (1 if status == 200 else 0)
            if status == 404:
                assert response.json() == {"error": "not_found"}

        async def release(visible):
            authenticate(app, "teacher")
            response = await client.patch(f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section['id']}/visibility", json={"visible": visible})
            assert response.status_code == 200

        await expect_intent(404)
        authenticate(app, "teacher")
        await create(client, f"/api/teaching/courses/{course_id}/members", {"student_sub": app.state.student})
        if unit_kind == "linear":
            await expect_intent(404)
            await release(True)
        await expect_intent(200)
        await expect_intent(404, path.replace(task['id'], str(uuid4())))
        await expect_intent(404, path.replace(course_id, str(uuid4())))
        if unit_kind == "linear":
            await release(False)
            await expect_intent(404)
            await release(True)
            await expect_intent(200)
        authenticate(app, "teacher")
        removed = await client.delete(f"/api/teaching/courses/{course_id}/members/{app.state.student}")
        assert removed.status_code == 204
        await expect_intent(404)


async def test_linear_sections_projection_pagination_and_membership_revocation(app):
    authenticate(app, "teacher")
    async with client_for(app) as client:
        course_id, unit_id = await course(client, app), await unit(client, app, kind="linear")
        module = await create(
            client, f"/api/teaching/courses/{course_id}/modules", {"unit_id": unit_id}
        )
        sections = []
        for title in ("Erster Abschnitt", "Letzter Abschnitt"):
            section = await create(
                client, f"/api/teaching/units/{unit_id}/sections", {"title": title}
            )
            sections.append(section["id"])
            await create(
                client,
                f"/api/teaching/units/{unit_id}/sections/{section['id']}/materials",
                {"title": title, "body_md": "Sichtbarer Inhalt"},
            )
            await create(
                client,
                f"/api/teaching/units/{unit_id}/sections/{section['id']}/tasks",
                {
                    "instruction_md": "Lies den Abschnitt.",
                    "criteria": [],
                    "teacher_context_md": "Privater Abschnittskontext",
                    "model_solution_md": "Private Lösung",
                },
            )
        await create(
            client, f"/api/teaching/courses/{course_id}/members", {"student_sub": app.state.student}
        )
        paths = [
            f"/api/learning/courses/{course_id}/sections",
            f"/api/learning/courses/{course_id}/units/{unit_id}/sections",
        ]
        authenticate(app, "student")
        assert (await client.get(paths[0])).status_code == 404
        empty = await client.get(paths[1])
        assert empty.status_code == 200 and empty.json() == []
        authenticate(app, "teacher")
        for section_id in sections:
            response = await client.patch(
                f"/api/teaching/courses/{course_id}/modules/{module['id']}/sections/{section_id}/visibility",
                json={"visible": True},
            )
            assert response.status_code == 200
        authenticate(app, "student")
        repo = DBLearningRepo()
        for index, path in enumerate(paths):
            for include, materials, tasks in [
                (None, False, False),
                ("materials", True, False),
                ("tasks", False, True),
                ("materials,tasks", True, True),
            ]:
                query = (
                    repo.list_released_sections
                    if index == 0
                    else repo.list_released_sections_by_unit
                )
                expected = query(
                    student_sub=app.state.student,
                    course_id=course_id,
                    include_materials=materials,
                    include_tasks=tasks,
                    limit=50,
                    offset=0,
                    **({} if index == 0 else {"unit_id": unit_id}),
                )
                for row in expected:
                    for material in row.get("materials", []):
                        material.update(file_url=None, simulation_url=None)
                response = await client.get(
                    path, params={} if include is None else {"include": include}
                )
                assert response.status_code == 200
                assert response.json() == expected
                assert [item["section"]["id"] for item in response.json()] == sections
                assert "Privater Abschnittskontext" not in response.text
                assert "Private Lösung" not in response.text
            for offset, expected_section in enumerate(sections):
                response = await client.get(path, params={"limit": 1, "offset": offset})
                assert response.status_code == 200
                assert [item["section"]["id"] for item in response.json()] == [expected_section]
            beyond = await client.get(path, params={"limit": 1, "offset": 99})
            assert beyond.status_code == (404 if index == 0 else 200)
            if index == 1:
                assert beyond.json() == []
        authenticate(app, "teacher")
        removed = await client.delete(
            f"/api/teaching/courses/{course_id}/members/{app.state.student}"
        )
        assert removed.status_code == 204
        authenticate(app, "student")
        for path in paths:
            response = await client.get(path)
            assert response.status_code == 403
            assert response.headers["cache-control"] == "private, no-store"


async def test_module_content_projection_and_include_match_database(app):
    authenticate(app, "teacher")
    async with client_for(app) as client:
        course_id, unit_id = await course(client, app), await unit(client, app)
        phases = await client.get(f"/api/teaching/units/{unit_id}/phases")
        phase_id = phases.json()[0]["id"]
        modules = []
        for title in ("Offen", "Gesperrt"):
            modules.append(
                (
                    await create(
                        client,
                        f"/api/teaching/units/{unit_id}/modules",
                        {
                            "title": title,
                            "phase_id": phase_id,
                        },
                    )
                )["id"]
            )
        await create(
            client,
            f"/api/teaching/units/{unit_id}/modules/edges",
            {
                "from_module_id": modules[0],
                "to_module_id": modules[1],
            },
        )
        target = await client.get(
            f"/api/teaching/units/{unit_id}/modules/{modules[0]}/content-target"
        )
        section_id = target.json()["section_id"]
        await create(
            client,
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
            {
                "title": "Einstieg",
                "body_md": "Sichtbarer Inhalt",
            },
        )
        await create(
            client,
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            {
                "instruction_md": "Lies den Einstieg.",
                "criteria": [],
                "teacher_context_md": "Privater Modulkontext",
                "model_solution_md": "Private Modullösung",
            },
        )
        await attach_and_enroll(client, app, course_id, unit_id)
        authenticate(app, "student")
        base = f"/api/learning/courses/{course_id}/units/{unit_id}/modules"
        for include, materials, tasks in [
            (None, True, True),
            ("materials", True, False),
            ("tasks", False, True),
        ]:
            expected = DBLearningRepo().get_modular_module_content(
                student_sub=app.state.student,
                course_id=course_id,
                unit_id=unit_id,
                module_id=modules[0],
                include_materials=materials,
                include_tasks=tasks,
            )
            for material in expected["materials"]:
                material.update(file_url=None, simulation_url=None)
            response = await client.get(
                f"{base}/{modules[0]}", params={} if include is None else {"include": include}
            )
            assert response.status_code == 200
            assert response.json() == expected
            assert "Privater Modulkontext" not in response.text
            assert "Private Modullösung" not in response.text
        for module_id in (modules[1], str(uuid4())):
            response = await client.get(f"{base}/{module_id}")
            assert response.status_code == 404
            assert response.json() == {"error": "not_found"}
            assert response.headers["Cache-Control"] == "private, no-store"


async def test_empty_and_populated_graph_match_existing_database_projection(app):
    authenticate(app, "teacher")
    async with client_for(app) as client:
        course_id, unit_id = await course(client, app), await unit(client, app)
        await attach_and_enroll(client, app, course_id, unit_id)
        path = graph_path(course_id, unit_id)
        authenticate(app, "student")
        empty = await client.get(path)
        assert empty.status_code == 200, empty.text
        assert len(empty.json()["phases"]) == 1
        assert empty.json()["modules"] == empty.json()["edges"] == []

        authenticate(app, "teacher")
        phase_one = empty.json()["phases"][0]["id"]
        phase_two = (
            await create(client, f"/api/teaching/units/{unit_id}/phases", {"title": "Transfer"})
        )["id"]
        await create(client, f"/api/teaching/units/{unit_id}/phases", {"title": "Ausblick"})
        modules = []
        for title, phase_id, kind in [
            ("Start", phase_one, "learning"),
            ("Ziel", phase_two, "learning"),
            ("Üben", phase_two, "practice"),
        ]:
            modules.append(
                (
                    await create(
                        client,
                        f"/api/teaching/units/{unit_id}/modules",
                        {
                            "title": title,
                            "phase_id": phase_id,
                            "module_kind": kind,
                        },
                    )
                )["id"]
            )
        for source, target in zip(modules, modules[1:]):
            await create(
                client,
                f"/api/teaching/units/{unit_id}/modules/edges",
                {"from_module_id": source, "to_module_id": target},
            )
        for node in (modules[0], modules[-1]):
            target = await client.get(
                f"/api/teaching/units/{unit_id}/modules/{node}/content-target"
            )
            assert target.status_code == 200
            section_id = target.json()["section_id"]
            await create(
                client,
                f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
                {
                    "instruction_md": "Aufgabe",
                    "criteria": ["Korrektheit"],
                    "teacher_context_md": "Privater Graph-Kontext",
                    "model_solution_md": "Private Graph-Musterlösung",
                },
            )

        authenticate(app, "student")
        expected = DBLearningRepo().get_modular_unit_graph(
            student_sub=app.state.student,
            course_id=course_id,
            unit_id=unit_id,
        )
        for request_path in (path, graph_path(course_id.upper(), unit_id.upper()), path):
            response = await client.get(request_path)
            assert response.status_code == 200
            assert response.json() == expected
            assert response.headers["Cache-Control"] == "private, no-store"
            assert "Origin" in response.headers["Vary"]
            assert "Privater Graph-Kontext" not in response.text
            assert "Private Graph-Musterlösung" not in response.text
        assert [item["id"] for item in expected["modules"]] == modules
        assert [item["status"] for item in expected["modules"]] == ["open", "locked", "locked"]
        assert expected["modules"][-1]["module_kind"] == "practice"
        assert expected["modules"][0]["tasks_total"] == expected["modules"][-1]["tasks_total"] == 1
        assert len(expected["phases"]) == 3
        for node in expected["modules"]:
            assert (
                not {"section_id", "tasks", "materials", "teacher_context_md", "model_solution_md"}
                & node.keys()
            )
        locked = await client.get(
            f"/api/learning/courses/{course_id}/units/{unit_id}/modules/{modules[-1]}"
        )
        assert locked.status_code == 404


async def test_membership_unit_assignment_and_revocation_fail_closed(app):
    authenticate(app, "teacher")
    async with client_for(app) as client:
        course_id, unit_id = await course(client, app), await unit(client, app)
        other_course, unassigned = await course(client, app), await unit(client, app)
        linear = await unit(client, app, "linear")
        await attach_and_enroll(client, app, course_id, unit_id)
        await create(client, f"/api/teaching/courses/{course_id}/modules", {"unit_id": linear})
        enrolled_elsewhere = await client.post(
            f"/api/teaching/courses/{other_course}/members",
            json={"student_sub": app.state.student},
        )
        assert enrolled_elsewhere.status_code in (201, 204)
        authenticate(app, "student")
        for request_path in (
            graph_path(other_course, unit_id),
            graph_path(course_id, unassigned),
            graph_path(course_id, str(uuid4())),
            graph_path(str(uuid4()), unit_id),
        ):
            response = await client.get(request_path)
            assert response.status_code == 404
            assert response.json() == {"error": "not_found"}
            assert response.headers["Cache-Control"] == "private, no-store"
        invalid_type = await client.get(graph_path(course_id, linear))
        assert invalid_type.status_code == 400
        assert invalid_type.json() == {"error": "bad_request", "detail": "invalid_unit_type"}
        authenticate(app, "student", f"foreign-student-{uuid4()}")
        assert (await client.get(graph_path(course_id, unit_id))).status_code == 404
        authenticate(app, "teacher")
        removed = await client.delete(
            f"/api/teaching/courses/{course_id}/members/{app.state.student}"
        )
        assert removed.status_code == 204, removed.text
        authenticate(app, "student")
        after = await client.get(graph_path(course_id, unit_id))
        assert after.status_code == 404
        assert after.json() == {"error": "not_found"}
        assert after.headers["Cache-Control"] == "private, no-store"
