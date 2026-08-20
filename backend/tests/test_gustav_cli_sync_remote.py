from __future__ import annotations

from copy import deepcopy

from backend.tools.gustav_cli.config import GustavCLIConfig
from backend.tools.gustav_cli.sync_remote import GustavSyncClient

BASE_URL = "https://gustav.example"
TOKEN = "secret"


def test_remote_client_reads_owner_and_paginates_all_units(monkeypatch) -> None:
    calls: list[str] = []
    first_page = [
        {
            "id": f"unit-{index}",
            "unit_type": "linear",
            "title": f"Einheit {index}",
            "summary": None,
        }
        for index in range(50)
    ]

    def fake_json(method, url, *, headers=None, json_body=None):
        assert method == "GET"
        assert headers == {"Authorization": f"Bearer {TOKEN}"}
        calls.append(url)
        if url.endswith("/api/me"):
            return 200, {"sub": "teacher-1", "roles": ["teacher"], "name": "Lehrkraft"}
        if "offset=0" in url:
            return 200, first_page
        if "offset=50" in url:
            return 200, [
                {"id": "unit-last", "unit_type": "linear", "title": "Letzte", "summary": None}
            ]
        raise AssertionError(url)

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))

    assert client.read_owner_sub() == "teacher-1"
    units = client.list_units()

    assert len(units) == 51
    assert calls[-2].endswith("limit=50&offset=0")
    assert calls[-1].endswith("limit=50&offset=50")


def test_remote_client_normalizes_linear_unit_and_reuses_mapping(monkeypatch) -> None:
    responses = {
        f"{BASE_URL}/api/teaching/units?limit=50&offset=0": [
            {
                "id": "unit-1",
                "unit_type": "linear",
                "title": "Binärzahlen",
                "summary": "Eine Einführung",
            }
        ],
        f"{BASE_URL}/api/teaching/units/unit-1/sections": [
            {"id": "section-1", "title": "Einstieg", "position": 1}
        ],
        f"{BASE_URL}/api/teaching/units/unit-1/sections/section-1/materials": [
            {
                "id": "material-1",
                "kind": "markdown",
                "title": "Stellenwerte",
                "body_md": "Zweierpotenzen.",
                "position": 1,
            }
        ],
        f"{BASE_URL}/api/teaching/units/unit-1/sections/section-1/tasks": [
            {
                "id": "task-1",
                "kind": "native",
                "instruction_md": "Rechne 1010 um.",
                "criteria": ["korrektes Ergebnis"],
                "teacher_context_md": None,
                "model_solution_md": None,
                "due_at": None,
                "max_attempts": None,
                "position": 1,
            }
        ],
    }

    def fake_json(method, url, *, headers=None, json_body=None):
        assert method == "GET"
        return 200, responses[url]

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    mapping = {
        "units": {
            "binaerzahlen": {
                "remote_id": "unit-1",
                "containers": {"einstieg": "section-1"},
                "materials": {"einstieg/stellenwerte": "material-1"},
                "tasks": {"einstieg/umrechnen": "task-1"},
            }
        }
    }
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))

    snapshot, refreshed = client.fetch_snapshot(mapping)

    unit = snapshot["units"]["binaerzahlen"]
    assert unit["title"] == "Binärzahlen"
    assert unit["sections"][0]["key"] == "einstieg"
    assert unit["sections"][0]["materials"][0]["key"] == "stellenwerte"
    assert unit["sections"][0]["tasks"][0]["key"] == "umrechnen"
    assert refreshed["units"]["binaerzahlen"]["remote_id"] == "unit-1"


def test_remote_client_reads_modular_graph_with_backing_content(monkeypatch) -> None:
    responses = {
        f"{BASE_URL}/api/teaching/units?limit=50&offset=0": [
            {
                "id": "unit-modular",
                "unit_type": "modular",
                "title": "Netzwerke",
                "summary": None,
            }
        ],
        f"{BASE_URL}/api/teaching/units/unit-modular/modules/graph": {
            "phases": [{"id": "phase-1", "title": "Start", "position": 1}],
            "modules": [
                {
                    "id": "module-1",
                    "phase_id": "phase-1",
                    "title": "Knoten",
                    "module_kind": "learning",
                    "required_prereq_count": 0,
                    "position_in_phase": 1,
                }
            ],
            "edges": [{"from": "module-1", "to": "module-1"}],
        },
        f"{BASE_URL}/api/teaching/units/unit-modular/modules/module-1/content-target": {
            "section_id": "section-1"
        },
        f"{BASE_URL}/api/teaching/units/unit-modular/sections/section-1/materials": [],
        f"{BASE_URL}/api/teaching/units/unit-modular/modules/module-1/tasks": [],
    }

    def fake_json(method, url, *, headers=None, json_body=None):
        assert method == "GET"
        return 200, responses[url]

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))

    snapshot, mapping = client.fetch_snapshot({})

    unit = next(iter(snapshot["units"].values()))
    assert unit["phases"][0]["key"] == unit["modules"][0]["phase"]
    assert unit["edges"] == [{"from": unit["modules"][0]["key"], "to": unit["modules"][0]["key"]}]
    unit_key = unit["key"]
    assert mapping["units"][unit_key]["backing_sections"] == {
        unit["modules"][0]["key"]: "section-1"
    }


def test_remote_client_pushes_existing_unit_content_with_minimal_patches(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        if method == "PATCH":
            return 200, {"id": url.rsplit("/", 1)[-1]}
        return 200, []

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    remote = {
        "schema_version": 1,
        "units": {
            "binaerzahlen": {
                "key": "binaerzahlen",
                "unit_type": "linear",
                "title": "Alt",
                "summary": None,
                "sections": [
                    {
                        "key": "einstieg",
                        "title": "Einstieg",
                        "materials": [
                            {
                                "key": "text",
                                "kind": "markdown",
                                "title": "Text",
                                "body_md": "Alt",
                            }
                        ],
                        "tasks": [
                            {
                                "key": "aufgabe",
                                "kind": "native",
                                "instruction_md": "Alt",
                                "criteria": [],
                                "teacher_context_md": None,
                                "model_solution_md": None,
                                "due_at": None,
                                "max_attempts": None,
                            }
                        ],
                    }
                ],
            }
        },
    }
    local = deepcopy(remote)
    local["units"]["binaerzahlen"]["title"] = "Neu"
    local["units"]["binaerzahlen"]["sections"][0]["materials"][0]["body_md"] = "Neu"
    local["units"]["binaerzahlen"]["sections"][0]["tasks"][0]["instruction_md"] = "Neu"
    mapping = {
        "units": {
            "binaerzahlen": {
                "remote_id": "unit-1",
                "containers": {"einstieg": "section-1"},
                "materials": {"einstieg/text": "material-1"},
                "tasks": {"einstieg/aufgabe": {"remote_id": "task-1"}},
            }
        }
    }

    refreshed = client.push_snapshot(
        local,
        remote,
        mapping,
        prune=False,
        checkpoint=lambda value: None,
    )

    assert refreshed == mapping
    assert (
        "PATCH",
        f"{BASE_URL}/api/teaching/units/unit-1",
        {"title": "Neu"},
    ) in calls
    assert (
        "PATCH",
        f"{BASE_URL}/api/teaching/units/unit-1/sections/section-1/materials/material-1",
        {"body_md": "Neu"},
    ) in calls
    assert (
        "PATCH",
        f"{BASE_URL}/api/teaching/units/unit-1/sections/section-1/tasks/task-1",
        {"instruction_md": "Neu"},
    ) in calls


def test_remote_client_creates_new_linear_unit_in_dependency_order(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []
    identifiers = iter(["unit-1", "section-1", "material-1", "task-1"])

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        if method == "POST" and not url.endswith("/reorder"):
            return 201, {"id": next(identifiers)}
        return 200, []

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    local = {
        "schema_version": 1,
        "units": {
            "neu": {
                "key": "neu",
                "unit_type": "linear",
                "title": "Neue Einheit",
                "summary": None,
                "sections": [
                    {
                        "key": "start",
                        "title": "Start",
                        "materials": [
                            {
                                "key": "text",
                                "kind": "markdown",
                                "title": "Text",
                                "body_md": "Inhalt",
                            }
                        ],
                        "tasks": [
                            {
                                "key": "aufgabe",
                                "kind": "native",
                                "instruction_md": "Arbeite.",
                                "criteria": [],
                                "teacher_context_md": None,
                                "model_solution_md": None,
                                "due_at": None,
                                "max_attempts": None,
                            }
                        ],
                    }
                ],
            }
        },
    }

    mapping = client.push_snapshot(
        local,
        {"schema_version": 1, "units": {}},
        {},
        prune=False,
        checkpoint=lambda value: None,
    )

    assert [call[0] for call in calls[:4]] == ["POST", "POST", "POST", "POST"]
    assert calls[0][1].endswith("/api/teaching/units")
    assert calls[1][1].endswith("/api/teaching/units/unit-1/sections")
    assert mapping["units"]["neu"]["remote_id"] == "unit-1"
    assert mapping["units"]["neu"]["containers"]["start"] == "section-1"


def test_remote_client_creates_modular_structure_and_edge_in_dependency_order(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str, object]] = []

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        if method == "POST" and url.endswith("/phases"):
            return 201, {"id": "phase-1"}
        if method == "POST" and url.endswith("/modules"):
            return 201, {"id": "module-1"}
        if method == "GET" and url.endswith("/content-target"):
            return 200, {"section_id": "section-1"}
        return 200, {}

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    local = {
        "schema_version": 1,
        "units": {
            "netze": {
                "key": "netze",
                "unit_type": "modular",
                "title": "Netze",
                "summary": None,
                "phases": [{"key": "start", "title": "Start"}],
                "modules": [
                    {
                        "key": "knoten",
                        "phase": "start",
                        "title": "Knoten",
                        "module_kind": "learning",
                        "required_prereq_count": 0,
                        "materials": [],
                        "tasks": [],
                    }
                ],
                "edges": [{"from": "knoten", "to": "knoten"}],
            }
        },
    }
    remote = {
        "schema_version": 1,
        "units": {
            "netze": {
                "key": "netze",
                "unit_type": "modular",
                "title": "Netze",
                "summary": None,
                "phases": [],
                "modules": [],
                "edges": [],
            }
        },
    }
    mapping = {"units": {"netze": {"remote_id": "unit-1"}}}

    refreshed = client.push_snapshot(
        local,
        remote,
        mapping,
        prune=False,
        checkpoint=lambda current: None,
    )

    edge_call = next(call for call in calls if call[1].endswith("/modules/edges"))
    assert edge_call == (
        "POST",
        f"{BASE_URL}/api/teaching/units/unit-1/modules/edges",
        {"from_module_id": "module-1", "to_module_id": "module-1"},
    )
    assert refreshed["units"]["netze"]["backing_sections"] == {"knoten": "section-1"}
