"""Real-DB graph parity and membership boundaries with run-owned cleanup."""

import os
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
