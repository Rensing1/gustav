from __future__ import annotations

from copy import deepcopy

import pytest

from backend.tools.gustav_cli.config import GustavCLIConfig
from backend.tools.gustav_cli.sync_manifest import MAX_H5P_PACKAGE_BYTES
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


def test_remote_client_preserves_h5p_draft_without_downloading_package(monkeypatch) -> None:
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    monkeypatch.setattr(
        client,
        "_bytes",
        lambda *args, **kwargs: pytest.fail("draft must not download an H5P package"),
    )

    task = client._task(
        {
            "id": "task-1",
            "kind": "h5p",
            "instruction_md": "Entwurf",
            "criteria": [],
            "h5p": {"content_id": None, "display_options": {"frame": True}},
        },
        unit_id="unit-1",
        section_id="section-1",
        task_mapping={},
        include_assets=True,
    )

    assert task["h5p_sha256"] is None
    assert "_h5p_bytes" not in task


def test_remote_client_limits_h5p_package_download(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_bytes(method, url, *, headers=None, data=None, max_bytes=None):
        captured["max_bytes"] = max_bytes
        return 200, b"not-a-zip"

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_bytes", fake_bytes)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))

    with pytest.raises(ValueError, match="invalid_h5p_package"):
        client._task(
            {
                "id": "task-1",
                "kind": "h5p",
                "instruction_md": "Quiz",
                "criteria": [],
                "h5p": {"content_id": "12", "display_options": {}},
            },
            unit_id="unit-1",
            section_id="section-1",
            task_mapping={},
            include_assets=True,
        )

    assert captured["max_bytes"] == MAX_H5P_PACKAGE_BYTES


def test_remote_client_creates_h5p_draft_without_importing_package(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        if method == "POST" and url.endswith("/tasks"):
            return 201, {"id": "task-1"}
        return 200, []

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    monkeypatch.setattr(
        "backend.tools.gustav_cli.sync_remote._http_multipart",
        lambda *args, **kwargs: pytest.fail("draft must not import an H5P package"),
    )
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    draft = {
        "key": "quiz",
        "kind": "h5p",
        "instruction_md": "Entwurf",
        "criteria": [],
        "teacher_context_md": None,
        "model_solution_md": None,
        "due_at": None,
        "max_attempts": None,
        "display_options": {},
        "h5p_sha256": None,
    }

    client._push_content(
        unit_id="unit-1",
        container_key="start",
        section_id="section-1",
        local={"materials": [], "tasks": [draft]},
        remote={"materials": [], "tasks": []},
        unit_mapping={},
        prune=False,
        checkpoint=lambda mapping: None,
        complete_mapping={},
    )

    assert any(method == "POST" and url.endswith("/tasks") for method, url, _ in calls)


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
    module_ids = iter(["module-1", "module-2"])

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        if method == "POST" and url.endswith("/phases"):
            return 201, {"id": "phase-1"}
        if method == "POST" and url.endswith("/modules"):
            return 201, {"id": next(module_ids)}
        if method == "GET" and url.endswith("/content-target"):
            return 200, {"section_id": f"section-{url.split('/')[-2][-1]}"}
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
                            "key": "quelle",
                            "phase": "start",
                            "title": "Quelle",
                            "module_kind": "learning",
                            "required_prereq_count": 0,
                            "materials": [],
                            "tasks": [],
                        },
                        {
                            "key": "ziel",
                            "phase": "start",
                            "title": "Ziel",
                            "module_kind": "learning",
                            "required_prereq_count": 1,
                            "materials": [],
                            "tasks": [],
                        },
                    ],
                    "edges": [{"from": "quelle", "to": "ziel"}],
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
        {"from_module_id": "module-1", "to_module_id": "module-2"},
    )
    assert refreshed["units"]["netze"]["backing_sections"] == {
        "quelle": "section-1",
        "ziel": "section-2",
    }


def test_remote_client_sets_new_module_prerequisite_count_after_creating_edges(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str, object]] = []
    module_ids = iter(["module-a", "module-b"])

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        if method == "POST" and url.endswith("/modules"):
            return 201, {"id": next(module_ids)}
        if method == "GET" and url.endswith("/content-target"):
            return 200, {"section_id": f"section-{url.split('/')[-2][-1]}"}
        return 200, {}

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    module = lambda key, required: {
        "key": key,
        "phase": "start",
        "title": key.upper(),
        "module_kind": "learning",
        "required_prereq_count": required,
        "materials": [],
        "tasks": [],
    }
    local = {
        "schema_version": 1,
        "units": {
            "netze": {
                "key": "netze",
                "unit_type": "modular",
                "title": "Netze",
                "summary": None,
                "phases": [{"key": "start", "title": "Start"}],
                "modules": [module("a", 0), module("b", 1)],
                "edges": [{"from": "a", "to": "b"}],
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
                "phases": [{"key": "start", "title": "Start"}],
                "modules": [],
                "edges": [],
            }
        },
    }
    mapping = {
        "units": {
            "netze": {
                "remote_id": "unit-1",
                "phases": {"start": "phase-1"},
            }
        }
    }

    client.push_snapshot(local, remote, mapping, prune=False, checkpoint=lambda current: None)

    edge_index = next(index for index, call in enumerate(calls) if call[1].endswith("/modules/edges"))
    count_index = next(
        index
        for index, call in enumerate(calls)
        if call == (
            "PATCH",
            f"{BASE_URL}/api/teaching/units/unit-1/modules/module-b",
            {"required_prereq_count": 1},
        )
    )
    assert edge_index < count_index


def test_remote_client_updates_existing_prerequisite_count_after_new_edge(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        return 200, {}

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    base_unit = {
        "key": "netze",
        "unit_type": "modular",
        "title": "Netze",
        "summary": None,
        "phases": [{"key": "start", "title": "Start"}],
        "modules": [
            {
                "key": key,
                "phase": "start",
                "title": key.upper(),
                "module_kind": "learning",
                "required_prereq_count": required,
                "materials": [],
                "tasks": [],
            }
            for key, required in (("a", 0), ("b", 0))
        ],
        "edges": [],
    }
    remote = {"schema_version": 1, "units": {"netze": deepcopy(base_unit)}}
    local = deepcopy(remote)
    local["units"]["netze"]["edges"] = [{"from": "a", "to": "b"}]
    local["units"]["netze"]["modules"][1]["required_prereq_count"] = 1
    mapping = {
        "units": {
            "netze": {
                "remote_id": "unit-1",
                "phases": {"start": "phase-1"},
                "containers": {"a": "module-a", "b": "module-b"},
                "backing_sections": {"a": "section-a", "b": "section-b"},
            }
        }
    }

    client.push_snapshot(local, remote, mapping, prune=False, checkpoint=lambda current: None)

    edge_index = next(index for index, call in enumerate(calls) if call[1].endswith("/modules/edges"))
    count_index = next(
        index
        for index, call in enumerate(calls)
        if call[0] == "PATCH" and call[1].endswith("/modules/module-b")
    )
    assert edge_index < count_index


def test_remote_client_deletes_removed_phase_before_reordering_remaining_phases(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str, object]] = []

    def fake_json(method, url, *, headers=None, json_body=None):
        calls.append((method, url, json_body))
        return 200, {}

    monkeypatch.setattr("backend.tools.gustav_cli.sync_remote._http_json", fake_json)
    client = GustavSyncClient(GustavCLIConfig(BASE_URL, TOKEN))
    local_unit = {
        "key": "netze",
        "unit_type": "modular",
        "title": "Netze",
        "summary": None,
        "phases": [{"key": "start", "title": "Start"}],
        "modules": [],
        "edges": [],
    }
    remote_unit = deepcopy(local_unit)
    remote_unit["phases"].append({"key": "alt", "title": "Alt"})
    local = {"schema_version": 1, "units": {"netze": local_unit}}
    remote = {"schema_version": 1, "units": {"netze": remote_unit}}
    mapping = {
        "units": {
            "netze": {
                "remote_id": "unit-1",
                "phases": {"start": "phase-start", "alt": "phase-alt"},
            }
        }
    }

    client.push_snapshot(local, remote, mapping, prune=True, checkpoint=lambda current: None)

    delete_index = next(
        index
        for index, call in enumerate(calls)
        if call[0] == "DELETE" and call[1].endswith("/phases/phase-alt")
    )
    reorder_index = next(
        index for index, call in enumerate(calls) if call[1].endswith("/phases/reorder")
    )
    assert delete_index < reorder_index


def test_remote_client_checks_each_unit_immediately_before_its_first_mutation(
    monkeypatch,
) -> None:
    events: list[str] = []

    def fake_json(method, url, *, headers=None, json_body=None):
        if method != "GET":
            events.append("mutation")
        return 200, {"id": "unit-1"} if method == "PATCH" else []

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
                "sections": [],
            }
        },
    }
    local = deepcopy(remote)
    local["units"]["binaerzahlen"]["title"] = "Neu"

    client.push_snapshot(
        local,
        remote,
        {"units": {"binaerzahlen": {"remote_id": "unit-1"}}},
        prune=False,
        checkpoint=lambda current: None,
        before_unit=lambda key, current: events.append(f"check:{key}"),
    )

    assert events[:2] == ["check:binaerzahlen", "mutation"]


def test_remote_client_checkpoints_patch_before_a_later_failure(monkeypatch) -> None:
    checkpoints: list[dict[str, object]] = []

    def fake_json(method, url, *, headers=None, json_body=None):
        if method == "POST" and url.endswith("/sections/reorder"):
            raise RuntimeError("remote_api_error:503")
        return 200, {"id": "unit-1"} if method == "PATCH" else []

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
                    {"key": "start", "title": "Start", "materials": [], "tasks": []}
                ],
            }
        },
    }
    local = deepcopy(remote)
    local["units"]["binaerzahlen"]["title"] = "Neu"
    mapping = {
        "units": {
            "binaerzahlen": {
                "remote_id": "unit-1",
                "containers": {"start": "section-1"},
            }
        }
    }

    with pytest.raises(RuntimeError, match="503"):
        client.push_snapshot(
            local,
            remote,
            mapping,
            prune=False,
            checkpoint=lambda current: checkpoints.append(deepcopy(current)),
        )

    assert checkpoints, "the successful PATCH must be journaled before the next request"
