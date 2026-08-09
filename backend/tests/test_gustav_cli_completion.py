from __future__ import annotations

import io
import json

import pytest

from backend.tools.gustav_cli import cli, config


TOKEN = "gustav_cli_token_secret"
BASE_URL = "https://gustav.example"


def _configure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url=BASE_URL, token=TOKEN))


def _capture(monkeypatch, responses: list[tuple[int, object]]):
    calls: list[tuple[str, str, object | None]] = []
    queued = list(responses)

    def fake_request(method: str, url: str, *, headers=None, json_body=None):
        assert headers == {"Authorization": f"Bearer {TOKEN}"}
        calls.append((method, url, json_body))
        return queued.pop(0)

    monkeypatch.setattr(cli, "_http_json", fake_request)
    return calls


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.parametrize(
    ("extra", "expected_type"),
    [([], None), (["--unit-type", "modular"], "modular")],
)
def test_units_create_sends_explicit_unit_type(tmp_path, monkeypatch, extra, expected_type) -> None:
    _configure(tmp_path, monkeypatch)
    calls = _capture(monkeypatch, [(201, {"id": "unit-1", "title": "Demo"})])

    code, _, _ = _run(["units", "create", "--title", "Demo", *extra])

    assert code == 0
    expected = {"title": "Demo"}
    if expected_type is not None:
        expected["unit_type"] = expected_type
    assert calls[0][2] == expected


def _dialog_config() -> dict[str, object]:
    return {
        "partner_name": "Ada",
        "partner_description_md": "Eine Lernpartnerin",
        "role_md": "Ask precise questions.",
        "learning_goal_md": "Explain binary numbers.",
        "opening_message_md": "Wie kann ich helfen?",
        "response_mode": "hybrid",
        "max_rounds": 6,
        "closing_prompt_md": None,
    }


def test_tasks_create_dialog_loads_and_validates_json_file(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    dialog_file = tmp_path / "dialog.json"
    dialog_file.write_text(json.dumps(_dialog_config()), encoding="utf-8")
    calls = _capture(monkeypatch, [(201, {"id": "task-1"})])

    code, _, stderr = _run(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Führe ein Gespräch.",
            "--kind",
            "dialog",
            "--dialog-config",
            str(dialog_file),
        ]
    )

    assert code == 0, stderr
    assert calls[0][2] == {
        "instruction_md": "Führe ein Gespräch.",
        "dialog": _dialog_config(),
    }


@pytest.mark.parametrize(
    "content",
    ["not-json", "[]", '{"partner_name":"Ada","unknown":"secret"}'],
)
def test_invalid_dialog_config_fails_before_http_without_echoing_content(
    tmp_path, monkeypatch, content
) -> None:
    _configure(tmp_path, monkeypatch)
    dialog_file = tmp_path / "dialog.json"
    dialog_file.write_text(content, encoding="utf-8")
    calls: list[object] = []
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: calls.append(args))

    code, stdout, stderr = _run(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Dialog",
            "--kind",
            "dialog",
            "--dialog-config",
            str(dialog_file),
        ]
    )

    assert code == 1
    assert calls == []
    assert stdout == ""
    assert "secret" not in stderr


def test_dialog_kind_and_config_must_be_used_together(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    dialog_file = tmp_path / "dialog.json"
    dialog_file.write_text(json.dumps(_dialog_config()), encoding="utf-8")
    calls: list[object] = []
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: calls.append(args))

    without_file = _run(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Dialog",
            "--kind",
            "dialog",
        ]
    )
    wrong_kind = _run(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Dialog",
            "--kind",
            "native",
            "--dialog-config",
            str(dialog_file),
        ]
    )

    assert without_file[0] == 1
    assert wrong_kind[0] == 1
    assert calls == []


def test_missing_dialog_config_fails_before_http(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: calls.append(args))

    code, _, stderr = _run(
        [
            "tasks",
            "create",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--instruction-md",
            "Dialog",
            "--kind",
            "dialog",
            "--dialog-config",
            str(tmp_path / "missing.json"),
        ]
    )

    assert code == 1
    assert calls == []
    assert "existiert nicht" in stderr


def test_tasks_edit_clear_flags_send_explicit_empty_values(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    calls = _capture(monkeypatch, [(200, {"id": "task-1"})])

    code, _, stderr = _run(
        [
            "tasks",
            "edit",
            "task-1",
            "--unit-id",
            "unit-1",
            "--section-id",
            "section-1",
            "--clear-criteria",
            "--clear-teacher-context",
            "--clear-due-at",
            "--clear-max-attempts",
        ]
    )

    assert code == 0, stderr
    assert calls[0][2] == {
        "criteria": [],
        "teacher_context_md": None,
        "due_at": None,
        "max_attempts": None,
    }


@pytest.mark.parametrize(
    "conflicting_options",
    [
        ["--criterion", "Kriterium", "--clear-criteria"],
        ["--teacher-context-md", "Kontext", "--clear-teacher-context"],
        ["--due-at", "2026-09-01T08:00:00Z", "--clear-due-at"],
        ["--max-attempts", "3", "--clear-max-attempts"],
    ],
)
def test_tasks_edit_rejects_setter_and_clear_flag_together(conflicting_options) -> None:
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args(
            [
                "tasks",
                "edit",
                "task-1",
                "--unit-id",
                "unit-1",
                "--section-id",
                "section-1",
                *conflicting_options,
            ]
        )


def test_modules_list_renders_complete_graph_and_empty_state(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    graph = {
        "unit_id": "unit-1",
        "phases": [
            {"id": "p2", "title": "Ende", "position": 2},
            {"id": "p1", "title": "Start", "position": 1},
        ],
        "modules": [
            {
                "id": "m2",
                "phase_id": "p2",
                "title": "Transfer",
                "position": 1,
                "required_prereq_count": 1,
            },
            {
                "id": "m1",
                "phase_id": "p1",
                "title": "Grundlagen",
                "position": 1,
                "required_prereq_count": 0,
            },
        ],
        "edges": [{"from_module_id": "m1", "to_module_id": "m2"}],
    }
    _capture(
        monkeypatch,
        [(200, graph), (200, {"unit_id": "unit-1", "phases": [], "modules": [], "edges": []})],
    )

    code, stdout, _ = _run(["modules", "list", "--unit-id", "unit-1"])
    empty_code, empty_stdout, _ = _run(["modules", "list", "--unit-id", "unit-1"])

    assert code == 0
    assert stdout.splitlines() == [
        "PHASE\t1\tp1\tStart",
        "PHASE\t2\tp2\tEnde",
        "MODULE\t1\tm1\tp1\tGrundlagen\t0",
        "MODULE\t1\tm2\tp2\tTransfer\t1",
        "EDGE\tm1\tm2",
    ]
    assert empty_code == 0
    assert empty_stdout == "Keine Phasen, Module oder Kanten.\n"


def test_course_commands_use_existing_authoring_endpoints(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    calls = _capture(
        monkeypatch,
        [
            (200, []),
            (201, {"id": "course-1", "title": "Informatik"}),
            (200, {"id": "course-1", "title": "Informatik"}),
            (200, {"id": "course-1", "title": "Informatik 10"}),
            (200, {}),
            (200, {}),
            (200, []),
            (200, {"course_id": "course-1"}),
            (202, {"id": "job-1", "status": "pending"}),
        ],
    )

    commands = [
        ["courses", "list", "--json"],
        [
            "courses",
            "create",
            "--title",
            "Informatik",
            "--subject",
            "Informatik",
            "--grade-level",
            "10",
            "--school-year-start",
            "2026",
            "--term",
            "1",
            "--json",
        ],
        ["courses", "show", "course-1", "--json"],
        ["courses", "edit", "course-1", "--title", "Informatik 10", "--clear-term", "--json"],
        ["courses", "archive", "course-1", "--json"],
        ["courses", "restore", "course-1", "--json"],
        ["courses", "archive-batch", "--ids", "course-1", "course-2", "--json"],
        ["courses", "deletion-impact", "course-1", "--json"],
        [
            "courses",
            "delete",
            "course-1",
            "--confirmation-title",
            "Informatik",
            "--confirm-student-data-loss",
            "--yes",
            "--json",
        ],
    ]
    for command in commands:
        code, _, stderr = _run(command)
        assert code == 0, (command, stderr)

    assert calls == [
        ("GET", f"{BASE_URL}/api/teaching/courses?status=active&limit=10&offset=0", None),
        (
            "POST",
            f"{BASE_URL}/api/teaching/courses",
            {
                "title": "Informatik",
                "subject": "Informatik",
                "grade_level": "10",
                "school_year_start": 2026,
                "term": "1",
            },
        ),
        ("GET", f"{BASE_URL}/api/teaching/courses/course-1", None),
        (
            "PATCH",
            f"{BASE_URL}/api/teaching/courses/course-1",
            {"title": "Informatik 10", "term": None},
        ),
        ("POST", f"{BASE_URL}/api/teaching/courses/course-1/archive", None),
        ("POST", f"{BASE_URL}/api/teaching/courses/course-1/restore", None),
        (
            "POST",
            f"{BASE_URL}/api/teaching/courses/archive-batch",
            {"course_ids": ["course-1", "course-2"]},
        ),
        ("GET", f"{BASE_URL}/api/teaching/courses/course-1/deletion-impact", None),
        (
            "POST",
            f"{BASE_URL}/api/teaching/courses/course-1/deletion-jobs",
            {"confirmation_title": "Informatik", "confirm_student_data_loss": True},
        ),
    ]


def test_course_relation_and_student_search_commands_use_expected_endpoints(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    calls = _capture(
        monkeypatch,
        [(200, [])] * 4
        + [
            (201, {}),
            (204, None),
            (201, {}),
            (200, []),
            (204, None),
            (200, {}),
            (200, {}),
            (200, []),
        ],
    )

    commands = [
        ["course-deletion-jobs", "list", "--include-completed", "--json"],
        ["course-deletion-jobs", "show", "job-1", "--json"],
        ["course-members", "list", "--course-id", "course-1", "--json"],
        ["students", "search", "--query", "Ada", "--json"],
        [
            "course-members",
            "add",
            "--course-id",
            "course-1",
            "--student-sub",
            "student-1",
            "--json",
        ],
        [
            "course-members",
            "remove",
            "--course-id",
            "course-1",
            "--student-sub",
            "student-1",
            "--yes",
            "--json",
        ],
        [
            "course-modules",
            "add",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--context-notes",
            "Kontext",
            "--json",
        ],
        [
            "course-modules",
            "reorder",
            "--course-id",
            "course-1",
            "--ids",
            "module-2",
            "module-1",
            "--json",
        ],
        [
            "course-modules",
            "remove",
            "--course-id",
            "course-1",
            "--module-id",
            "module-1",
            "--yes",
            "--json",
        ],
        [
            "course-sections",
            "release",
            "--course-id",
            "course-1",
            "--module-id",
            "module-1",
            "--section-id",
            "section-1",
            "--json",
        ],
        [
            "course-sections",
            "hide",
            "--course-id",
            "course-1",
            "--module-id",
            "module-1",
            "--section-id",
            "section-1",
            "--json",
        ],
        ["course-sections", "list", "--course-id", "course-1", "--module-id", "module-1", "--json"],
    ]
    for command in commands:
        code, _, stderr = _run(command)
        assert code == 0, (command, stderr)

    assert calls == [
        (
            "GET",
            f"{BASE_URL}/api/teaching/course-deletion-jobs?include_completed=true&limit=50&offset=0",
            None,
        ),
        ("GET", f"{BASE_URL}/api/teaching/course-deletion-jobs/job-1", None),
        ("GET", f"{BASE_URL}/api/teaching/courses/course-1/members?limit=10&offset=0", None),
        ("GET", f"{BASE_URL}/api/users/search?q=Ada&role=student&limit=20", None),
        ("POST", f"{BASE_URL}/api/teaching/courses/course-1/members", {"student_sub": "student-1"}),
        ("DELETE", f"{BASE_URL}/api/teaching/courses/course-1/members/student-1", None),
        (
            "POST",
            f"{BASE_URL}/api/teaching/courses/course-1/modules",
            {"unit_id": "unit-1", "context_notes": "Kontext"},
        ),
        (
            "POST",
            f"{BASE_URL}/api/teaching/courses/course-1/modules/reorder",
            {"module_ids": ["module-2", "module-1"]},
        ),
        ("DELETE", f"{BASE_URL}/api/teaching/courses/course-1/modules/module-1", None),
        (
            "PATCH",
            f"{BASE_URL}/api/teaching/courses/course-1/modules/module-1/sections/section-1/visibility",
            {"visible": True},
        ),
        (
            "PATCH",
            f"{BASE_URL}/api/teaching/courses/course-1/modules/module-1/sections/section-1/visibility",
            {"visible": False},
        ),
        ("GET", f"{BASE_URL}/api/teaching/courses/course-1/modules/module-1/sections", None),
    ]


def test_course_remove_json_output_is_valid_json(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    _capture(monkeypatch, [(204, None)])

    code, stdout, stderr = _run(
        [
            "course-members",
            "remove",
            "--course-id",
            "course-1",
            "--student-sub",
            "student-1",
            "--yes",
            "--json",
        ]
    )

    assert code == 0, stderr
    assert json.loads(stdout) is None


def test_student_search_human_output_contains_stable_sub_and_name(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    _capture(monkeypatch, [(200, [{"sub": "student-1", "name": "Ada Lovelace"}])])

    code, stdout, stderr = _run(["students", "search", "--query", "Ada"])

    assert code == 0, stderr
    assert stdout == "student-1\tAda Lovelace\n"


def test_destructive_course_commands_require_yes_before_http(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: calls.append(args))

    for command in (
        [
            "courses",
            "delete",
            "course-1",
            "--confirmation-title",
            "Demo",
            "--confirm-student-data-loss",
        ],
        ["course-members", "remove", "--course-id", "course-1", "--student-sub", "student-1"],
        ["course-modules", "remove", "--course-id", "course-1", "--module-id", "module-1"],
    ):
        code, _, stderr = _run(command)
        assert code == 1
        assert "--yes" in stderr

    assert calls == []
