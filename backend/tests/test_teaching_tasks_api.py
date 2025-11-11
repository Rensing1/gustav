"""Teaching API — Section Tasks (contract-first, Markdown-only MVP)

Warum:
    Definiert die erwartete Funktionalität der Aufgaben-Endpunkte in einer
    Lerneinheit. Die Tests folgen den BDD-Szenarien aus dem Plan und sollen
    zunächst scheitern, bis Implementierung und Migration fertig sind.

Scope:
    - Nur native Markdown-Aufgaben (kind == "native")
    - Teacher-only Endpunkte, authorOnly
    - CRUD + Reorder inkl. Validierungen und Fehlerfälle
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
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
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_unit(client: httpx.AsyncClient, title: str = "Physik") -> dict:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str = "Kapitel") -> dict:
    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections",
        json={"title": title},
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_task(
    client: httpx.AsyncClient,
    unit_id: str,
    section_id: str,
    *,
    instruction: str,
    criteria: Sequence[str] | None = None,
    hints: str | None = None,
    due_at: str | None = None,
    max_attempts: int | None = None,
) -> dict:
    payload: dict[str, object] = {"instruction_md": instruction}
    if criteria is not None:
        payload["criteria"] = list(criteria)
    if hints is not None:
        payload["hints_md"] = hints
    if due_at is not None:
        payload["due_at"] = due_at
    if max_attempts is not None:
        payload["max_attempts"] = max_attempts

    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json=payload,
    )
    assert resp.status_code == 201
    return resp.json()


async def _list_task_ids(client: httpx.AsyncClient, unit_id: str, section_id: str) -> list[str]:
    resp = await client.get(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks"
    )
    assert resp.status_code == 200
    return [item["id"] for item in resp.json()]


def _iso_in_future(minutes: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


@pytest.mark.anyio
async def test_tasks_require_auth_and_author_role():
    """Endpoints require authentication and teacher author role."""

    main.SESSION_STORE = SessionStore()

    async with (await _client()) as client:
        resp = await client.get(
            "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/"
            "00000000-0000-0000-0000-000000000000/tasks"
        )
        assert resp.status_code == 401

    student = main.SESSION_STORE.create(sub="student-tasks", name="Max", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        resp = await client.post(
            "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/"
            "00000000-0000-0000-0000-000000000000/tasks",
            json={"instruction_md": "Nope"},
        )
        assert resp.status_code == 403


@pytest.mark.anyio
async def test_author_can_crud_tasks_and_non_author_is_blocked():
    """Happy path for author + 403 for Lehrer ohne Autorenschaft."""

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    author = main.SESSION_STORE.create(sub="teacher-tasks-A", name="Autor", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-tasks-B", name="Fremd", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Photosynthese")
        section = await _create_section(client, unit["id"], title="Chloroplasten")

        lst = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks"
        )
        assert lst.status_code == 200
        assert lst.json() == []

        created = await _create_task(
            client,
            unit["id"],
            section["id"],
            instruction="### Analysiere das Experiment",
            criteria=["Beschreibung vollständig", "Grafik interpretiert"],
            hints="Denk an die Lichtreaktion",
            due_at=_iso_in_future(),
            max_attempts=3,
        )
        assert created["position"] == 1
        assert created["instruction_md"].startswith("### Analysiere")
        assert created["kind"] == "native"

        listed = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks"
        )
        assert listed.status_code == 200
        data = listed.json()
        assert len(data) == 1
        assert data[0]["id"] == created["id"]
        assert data[0]["kind"] == "native"

        patch_payload = {
            "instruction_md": "### Aktualisierte Aufgabe",
            "criteria": ["Hypothese", "Auswertung"],
            "hints_md": "Nutze Tabellen",
            "due_at": _iso_in_future(120),
            "max_attempts": 5,
        }
        updated = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{created['id']}",
            json=patch_payload,
        )
        assert updated.status_code == 200
        updated_payload = updated.json()
        assert updated_payload["instruction_md"].startswith("### Aktualisierte")
        assert updated_payload["criteria"] == patch_payload["criteria"]
        assert updated_payload["hints_md"] == patch_payload["hints_md"]
        assert updated_payload["max_attempts"] == 5
        assert updated_payload["kind"] == "native"

        # Non-author blocked on list and update
        async with (await _client()) as other_client:
            other_client.cookies.set("gustav_session", other.session_id)
            forbidden = await other_client.get(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks"
            )
            assert forbidden.status_code == 403

            forbidden_patch = await other_client.patch(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{created['id']}",
                json={"instruction_md": "Nope"},
            )
            assert forbidden_patch.status_code == 403

        deleted = await client.delete(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{created['id']}"
        )
        assert deleted.status_code == 204

        lst_after = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks"
        )
        assert lst_after.status_code == 200
        assert lst_after.json() == []


@pytest.mark.anyio
async def test_task_creation_validation_errors():
    """POST validations map to the documented detail codes."""

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    author = main.SESSION_STORE.create(sub="teacher-tasks-validation", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Chemie")
        section = await _create_section(client, unit["id"], title="Reaktionen")

        # invalid instruction (empty)
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "   "},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_instruction_md"

        # invalid criteria (not array)
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "A", "criteria": "not-an-array"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_criteria"

        # invalid criteria (too many)
        too_many = [f"Kriterium {i}" for i in range(12)]
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "A", "criteria": too_many},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_criteria"

        # invalid due_at
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "A", "due_at": "not-a-datetime"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_due_at"

        # invalid max_attempts
        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks",
            json={"instruction_md": "A", "max_attempts": 0},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_max_attempts"


@pytest.mark.anyio
async def test_tasks_invalid_uuid_path_params_return_400():
    """Invalid UUIDs in path must return 400 with specific detail codes."""

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    teacher = main.SESSION_STORE.create(sub="teacher-tasks-uuids", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)

        # invalid unit_id for list
        r1 = await client.get("/api/teaching/units/not-a-uuid/sections/00000000-0000-0000-0000-000000000000/tasks")
        assert r1.status_code == 400 and r1.json()["detail"] == "invalid_unit_id"

        # invalid section_id for list
        r2 = await client.get("/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/not-a-uuid/tasks")
        assert r2.status_code == 400 and r2.json()["detail"] == "invalid_section_id"

        # POST with invalid unit/section ids
        r3 = await client.post(
            "/api/teaching/units/not-a-uuid/sections/also-bad/tasks",
            json={"instruction_md": "A"},
        )
        assert r3.status_code == 400

        # PATCH/DELETE invalid task_id
        base = "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/00000000-0000-0000-0000-000000000000/tasks"
        p = await client.patch(f"{base}/not-a-uuid", json={"instruction_md": "X"})
        assert p.status_code == 400 and p.json()["detail"] == "invalid_task_id"
        d = await client.delete(f"{base}/not-a-uuid")
        assert d.status_code == 400 and d.json()["detail"] == "invalid_task_id"

        # Reorder invalid section id
        ro = await client.post(
            "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/not-a-uuid/tasks/reorder",
            json={"task_ids": ["00000000-0000-0000-0000-000000000111"]},
        )
        assert ro.status_code == 400 and ro.json()["detail"] == "invalid_section_id"


@pytest.mark.anyio
async def test_task_due_at_accepts_zulu():
    """Server accepts ISO timestamps with trailing 'Z' for UTC."""

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    teacher = main.SESSION_STORE.create(sub="teacher-tasks-zulu", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client, title="Informatik")
        section = await _create_section(client, unit["id"], title="Algorithmen")
        due_z = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        created = await _create_task(
            client,
            unit["id"],
            section["id"],
            instruction="Beschreibe den Sortieralgorithmus",
            due_at=due_z,
        )
        assert created["due_at"] is not None


@pytest.mark.anyio
async def test_task_update_validation_errors_and_empty_payload():
    """PATCH validations for empty payload and invalid fields."""

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    author = main.SESSION_STORE.create(sub="teacher-tasks-update", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Biologie")
        section = await _create_section(client, unit["id"], title="Genetik")
        created = await _create_task(
            client,
            unit["id"],
            section["id"],
            instruction="### Aufgabe",
        )

        resp = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{created['id']}",
            json={},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "empty_payload"

        invalid_cases = [
            ({"instruction_md": "   "}, "invalid_instruction_md"),
            ({"criteria": "nope"}, "invalid_criteria"),
            ({"criteria": ["", "ok"]}, "invalid_criteria"),
            ({"due_at": "not-a-datetime"}, "invalid_due_at"),
            ({"max_attempts": -1}, "invalid_max_attempts"),
        ]
        for payload, detail in invalid_cases:
            response = await client.patch(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{created['id']}",
                json=payload,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == detail


@pytest.mark.anyio
async def test_task_partial_patch_updates_only_sent_fields():
    """PATCH with subset of fields should succeed and keep other values."""

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    author = main.SESSION_STORE.create(sub="teacher-tasks-partial", name="Autor", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Mathematik")
        section = await _create_section(client, unit["id"], title="Quadratische Funktionen")
        created = await _create_task(
            client,
            unit["id"],
            section["id"],
            instruction="**Beschreibe den Graphen**",
            criteria=["Achsenabschnitt nennen"],
            hints="Nutze Scheitelpunktform",
            max_attempts=2,
        )

        patch_resp = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/{created['id']}",
            json={"criteria": ["Scheitelpunkt", "Nullstellen"]},
        )
        assert patch_resp.status_code == 200
        payload = patch_resp.json()
        assert payload["criteria"] == ["Scheitelpunkt", "Nullstellen"]
        assert payload["instruction_md"] == created["instruction_md"]
        assert payload["hints_md"] == created["hints_md"]
        assert payload["max_attempts"] == created["max_attempts"]


@pytest.mark.anyio
async def test_task_reorder_happy_and_error_cases():
    """Permutation validation for reorder endpoint (200 + 400 detail codes)."""

    main.SESSION_STORE = SessionStore()
    _require_db_or_skip()

    author = main.SESSION_STORE.create(sub="teacher-tasks-reorder", name="Autor", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="teacher-tasks-reorder-other", name="Fremd", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", author.session_id)
        unit = await _create_unit(client, title="Mathe")
        section = await _create_section(client, unit["id"], title="Funktionen")

        tasks = []
        for idx in range(3):
            task = await _create_task(
                client,
                unit["id"],
                section["id"],
                instruction=f"Aufgabe {idx+1}",
            )
            tasks.append(task)

        order = list(reversed([task["id"] for task in tasks]))
        reorder = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/reorder",
            json={"task_ids": order},
        )
        assert reorder.status_code == 200
        reordered = reorder.json()
        assert [item["id"] for item in reordered] == order
        assert [item["position"] for item in reordered] == [1, 2, 3]

        # Non-author cannot reorder
        async with (await _client()) as other_client:
            other_client.cookies.set("gustav_session", other.session_id)
            forbidden = await other_client.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/reorder",
                json={"task_ids": order},
            )
            assert forbidden.status_code == 403

        # invalid payloads
        base_url = f"/api/teaching/units/{unit['id']}/sections/{section['id']}/tasks/reorder"
        invalid_cases = [
            (42, "task_ids_must_be_array"),
            ([], "empty_task_ids"),
            ([tasks[0]["id"], tasks[0]["id"], tasks[1]["id"]], "duplicate_task_ids"),
            (["not-a-uuid", tasks[1]["id"], tasks[2]["id"]], "invalid_task_ids"),
            ([tasks[0]["id"], tasks[1]["id"]], "task_mismatch"),
        ]
        for payload, detail in invalid_cases:
            resp = await client.post(base_url, json={"task_ids": payload})
            assert resp.status_code == 400
            assert resp.json()["detail"] == detail

        # Unknown IDs (same length but foreign id) -> task_mismatch
        foreign_ids = await _list_task_ids(client, unit["id"], section["id"])
        foreign_ids[0] = "00000000-0000-0000-0000-000000000999"
        resp = await client.post(base_url, json={"task_ids": foreign_ids})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "task_mismatch"
