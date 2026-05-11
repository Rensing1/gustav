from __future__ import annotations

import io
import json
import stat

from backend.tools.gustav_cli import cli, config


def _configure_test_cli(tmp_path, monkeypatch, token: str = "gustav_cli_token_secret") -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token=token))


def _capture_http(monkeypatch, responses: list[tuple[int, object]] | None = None):
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    queued = list(responses or [(200, {})])

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return queued.pop(0) if queued else (200, {})

    monkeypatch.setattr(cli, "_http_json", fake_request)
    return calls


def test_auth_configure_reads_token_from_stdin_and_writes_0600_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))

    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.main(
        ["auth", "configure", "--base-url", "https://gustav.example", "--token-stdin"],
        stdin=io.StringIO("gustav_cli_token_secret\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 0
    assert "konfiguriert" in stdout.getvalue()
    assert "gustav_cli_token_secret" not in stdout.getvalue()

    path = config.default_config_path()
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == {
        "base_url": "https://gustav.example",
        "token": "gustav_cli_token_secret",
    }


def test_auth_status_redacts_configured_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))

    stdout = io.StringIO()
    code = cli.main(["auth", "status"], stdout=stdout, stderr=io.StringIO())

    assert code == 0
    text = stdout.getvalue()
    assert "https://gustav.example" in text
    assert "gustav_cli_token_secret" not in text
    assert "gustav…" in text


def test_units_list_json_uses_configured_bearer_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return 200, [{"id": "unit-1", "title": "Demo", "summary": ""}]

    monkeypatch.setattr(cli, "_http_json", fake_request)

    stdout = io.StringIO()
    code = cli.main(["units", "list", "--json"], stdout=stdout, stderr=io.StringIO())

    assert code == 0
    assert json.loads(stdout.getvalue()) == [{"id": "unit-1", "title": "Demo", "summary": ""}]
    assert calls == [
        (
            "GET",
            "https://gustav.example/api/teaching/units",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        )
    ]


def test_units_create_sends_json_body(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return 201, {"id": "unit-1", "title": "Demo", "summary": "Kurz"}

    monkeypatch.setattr(cli, "_http_json", fake_request)

    stdout = io.StringIO()
    code = cli.main(
        ["units", "create", "--title", "Demo", "--description", "Kurz", "--json"],
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(stdout.getvalue())["title"] == "Demo"
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Demo", "summary": "Kurz"},
        )
    ]


def test_units_delete_requires_yes_before_http_call(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[object] = []
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: calls.append((args, kwargs)))

    stderr = io.StringIO()
    code = cli.main(["units", "delete", "unit-1"], stdout=io.StringIO(), stderr=stderr)

    assert code == 1
    assert "--yes" in stderr.getvalue()
    assert calls == []


def test_sections_reorder_sends_section_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        return 200, []

    monkeypatch.setattr(cli, "_http_json", fake_request)

    code = cli.main(
        ["sections", "reorder", "--unit-id", "unit-1", "--ids", "s1", "s2"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections/reorder",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"section_ids": ["s1", "s2"]},
        )
    ]


def test_sections_list_table_prints_items(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (200, [{"id": "s1", "title": "Abschnitt 1"}]),
    )

    stdout = io.StringIO()
    code = cli.main(
        ["sections", "list", "--unit-id", "unit-1"],
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == "s1\tAbschnitt 1\n"


def test_phases_create_sends_title(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        ["phases", "create", "--unit-id", "unit-1", "--title", "Start"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/phases",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"title": "Start"},
    )


def test_modules_edge_create_uses_unit_scoped_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        ["module-edges", "create", "--unit-id", "unit-1", "--from", "m1", "--to", "m2"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/modules/edges",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"from_module_id": "m1", "to_module_id": "m2"},
    )


def test_modules_create_sends_phase_and_title(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        ["modules", "create", "--unit-id", "unit-1", "--phase-id", "phase-1", "--title", "Modul A"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/modules",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"phase_id": "phase-1", "title": "Modul A"},
    )


def test_modules_reorder_sends_module_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (200, [])),
    )

    code = cli.main(
        ["modules", "reorder", "--unit-id", "unit-1", "--phase-id", "phase-1", "--ids", "m1", "m2"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/phases/phase-1/modules/reorder",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"module_ids": ["m1", "m2"]},
    )


def test_materials_create_with_module_id_resolves_section_target(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []

    def fake_request(method: str, url: str, *, headers: dict[str, str] | None = None, json_body=None):
        calls.append((method, url, headers, json_body))
        if url.endswith("/modules/module-1/content-target"):
            return 200, {"module_id": "module-1", "section_id": "section-hidden"}
        return 201, {"id": "material-1", "title": "Hinweis"}

    monkeypatch.setattr(cli, "_http_json", fake_request)

    code = cli.main(
        [
            "materials",
            "create",
            "--unit-id",
            "unit-1",
            "--module-id",
            "module-1",
            "--title",
            "Hinweis",
            "--body-md",
            "Text",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "GET",
            "https://gustav.example/api/teaching/units/unit-1/modules/module-1/content-target",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        ),
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-hidden/materials",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Hinweis", "body_md": "Text"},
        ),
    ]


def test_tasks_create_sends_instruction_and_criteria(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url="https://gustav.example", token="gustav_cli_token_secret"))
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, *, headers=None, json_body=None: (calls.append((method, url, headers, json_body)) or (201, {})),
    )

    code = cli.main(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Erkläre den Algorithmus.",
            "--criterion",
            "nennt Eingabe",
            "--criterion",
            "nennt Ausgabe",
        ],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == (
        "POST",
        "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks",
        {"Authorization": "Bearer gustav_cli_token_secret"},
        {"instruction_md": "Erkläre den Algorithmus.", "criteria": ["nennt Eingabe", "nennt Ausgabe"]},
    )


def test_units_edit_sends_only_changed_fields(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, {"id": "unit-1", "title": "Neu"})])

    code = cli.main(
        ["units", "edit", "unit-1", "--title", "Neu"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    assert calls == [
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "Neu"},
        )
    ]


def test_sections_create_edit_and_delete_use_expected_endpoints(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(201, {}), (200, {}), (204, None)])

    assert cli.main(["sections", "create", "--unit-id", "unit-1", "--title", "A"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["sections", "edit", "section-1", "--unit-id", "unit-1", "--title", "B"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["sections", "delete", "section-1", "--unit-id", "unit-1", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        (
            "POST",
            "https://gustav.example/api/teaching/units/unit-1/sections",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "A"},
        ),
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"title": "B"},
        ),
        (
            "DELETE",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            None,
        ),
    ]


def test_phases_list_edit_delete_and_reorder_use_expected_endpoints(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, []), (200, {}), (204, None), (200, [])])

    assert cli.main(["phases", "list", "--unit-id", "unit-1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["phases", "edit", "phase-1", "--unit-id", "unit-1", "--title", "B"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["phases", "delete", "phase-1", "--unit-id", "unit-1", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["phases", "reorder", "--unit-id", "unit-1", "--ids", "phase-2", "phase-1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/phases", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("PATCH", "https://gustav.example/api/teaching/units/unit-1/phases/phase-1", {"Authorization": "Bearer gustav_cli_token_secret"}, {"title": "B"}),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/phases/phase-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("POST", "https://gustav.example/api/teaching/units/unit-1/phases/reorder", {"Authorization": "Bearer gustav_cli_token_secret"}, {"phase_ids": ["phase-2", "phase-1"]}),
    ]


def test_modules_list_edit_delete_and_edge_delete_use_expected_endpoints(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, {"modules": []}), (200, {}), (204, None), (204, None)])

    assert cli.main(["modules", "list", "--unit-id", "unit-1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["modules", "edit", "module-1", "--unit-id", "unit-1", "--title", "B", "--required-prereq-count", "1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["modules", "delete", "module-1", "--unit-id", "unit-1", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["module-edges", "delete", "--unit-id", "unit-1", "--from", "m1", "--to", "m2", "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/modules/graph", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("PATCH", "https://gustav.example/api/teaching/units/unit-1/modules/module-1", {"Authorization": "Bearer gustav_cli_token_secret"}, {"title": "B", "required_prereq_count": 1}),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/modules/module-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/modules/m1/edges/m2", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
    ]


def test_materials_list_edit_delete_and_reorder_use_section_endpoint(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, []), (200, {}), (204, None), (200, [])])

    target = ["--unit-id", "unit-1", "--section-id", "section-1"]
    assert cli.main(["materials", "list", *target], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["materials", "edit", "material-1", *target, "--title", "B", "--body-md", "Text", "--alt-text", "Alt"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["materials", "delete", "material-1", *target, "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["materials", "reorder", *target, "--ids", "m2", "m1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("PATCH", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/material-1", {"Authorization": "Bearer gustav_cli_token_secret"}, {"title": "B", "body_md": "Text", "alt_text": "Alt"}),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/material-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("POST", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/materials/reorder", {"Authorization": "Bearer gustav_cli_token_secret"}, {"material_ids": ["m2", "m1"]}),
    ]


def test_tasks_list_edit_delete_and_reorder_use_section_endpoint(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(200, []), (200, {}), (204, None), (200, [])])

    target = ["--unit-id", "unit-1", "--section-id", "section-1"]
    assert cli.main(["tasks", "list", *target], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["tasks", "edit", "task-1", *target, "--instruction-md", "Neu", "--criterion", "A", "--teacher-context-md", "privat", "--due-at", "2026-05-12T08:00:00Z", "--max-attempts", "2"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["tasks", "delete", "task-1", *target, "--yes"], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert cli.main(["tasks", "reorder", *target, "--ids", "t2", "t1"], stdout=io.StringIO(), stderr=io.StringIO()) == 0

    assert calls == [
        ("GET", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        (
            "PATCH",
            "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks/task-1",
            {"Authorization": "Bearer gustav_cli_token_secret"},
            {"instruction_md": "Neu", "criteria": ["A"], "teacher_context_md": "privat", "due_at": "2026-05-12T08:00:00Z", "max_attempts": 2},
        ),
        ("DELETE", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks/task-1", {"Authorization": "Bearer gustav_cli_token_secret"}, None),
        ("POST", "https://gustav.example/api/teaching/units/unit-1/sections/section-1/tasks/reorder", {"Authorization": "Bearer gustav_cli_token_secret"}, {"task_ids": ["t2", "t1"]}),
    ]


def test_delete_commands_require_yes_before_http_call(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch)

    cases = [
        ["sections", "delete", "section-1", "--unit-id", "unit-1"],
        ["phases", "delete", "phase-1", "--unit-id", "unit-1"],
        ["modules", "delete", "module-1", "--unit-id", "unit-1"],
        ["module-edges", "delete", "--unit-id", "unit-1", "--from", "m1", "--to", "m2"],
        ["materials", "delete", "material-1", "--unit-id", "unit-1", "--section-id", "section-1"],
        ["tasks", "delete", "task-1", "--unit-id", "unit-1", "--section-id", "section-1"],
    ]
    for argv in cases:
        stderr = io.StringIO()
        assert cli.main(argv, stdout=io.StringIO(), stderr=stderr) == 1
        assert "--yes" in stderr.getvalue()

    assert calls == []


def test_module_target_failure_stops_material_create_before_write(tmp_path, monkeypatch) -> None:
    _configure_test_cli(tmp_path, monkeypatch)
    calls = _capture_http(monkeypatch, [(404, {"error": "not_found"})])

    stderr = io.StringIO()
    code = cli.main(
        ["materials", "create", "--unit-id", "unit-1", "--module-id", "missing", "--title", "A", "--body-md", "Text"],
        stdout=io.StringIO(),
        stderr=stderr,
    )

    assert code == 1
    assert "API-Fehler (404)" in stderr.getvalue()
    assert len(calls) == 1
    assert calls[0][0] == "GET"


def test_api_errors_do_not_leak_configured_token(tmp_path, monkeypatch) -> None:
    token = "gustav_cli_very_secret_token"
    _configure_test_cli(tmp_path, monkeypatch, token=token)
    _capture_http(monkeypatch, [(403, {"error": "forbidden"})])

    stderr = io.StringIO()
    code = cli.main(["units", "list"], stdout=io.StringIO(), stderr=stderr)

    assert code == 1
    assert "API-Fehler (403)" in stderr.getvalue()
    assert token not in stderr.getvalue()
