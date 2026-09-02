from __future__ import annotations

import io
import json
import stat
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend.tools.gustav_cli import cli, config

TOKEN = "gustav_cli_token_secret"
BASE_URL = "https://gustav.example"


def _configure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GUSTAV_CONFIG_HOME", str(tmp_path))
    config.save_config(config.GustavCLIConfig(base_url=BASE_URL, token=TOKEN))


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _course_page(rows: list[dict]) -> dict:
    return {
        "user": {"sub": "teacher-1", "name": "Ada", "role": "teacher", "roles": ["teacher"]},
        "course": {
            "id": "course-1",
            "title": "Informatik",
            "href": "/diagnostics/courses/course-1",
        },
        "units": [
            {"id": "unit-1", "title": "Netzwerke", "position": 1, "href": "/live/unit-1"}
        ],
        "rows": rows,
    }


def test_diagnostics_course_loads_every_page_before_printing_json(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    first_rows = [
        {
            "student": {"sub": f"student-{index}", "name": f"Lernende {index}", "href": "/"},
            "cells": [
                {
                    "unit_id": "unit-1",
                    "submitted_tasks": 1,
                    "total_tasks": 2,
                    "href": "/live/unit-1",
                }
            ],
        }
        for index in range(50)
    ]
    calls: list[str] = []

    def fake_request(method: str, url: str, *, headers=None, json_body=None):
        assert method == "GET"
        assert headers == {"Authorization": f"Bearer {TOKEN}"}
        calls.append(url)
        offset = int(parse_qs(urlparse(url).query)["offset"][0])
        return (200, _course_page(first_rows if offset == 0 else []))

    monkeypatch.setattr(cli, "_http_json", fake_request)

    code, stdout, stderr = _run(
        ["diagnostics", "course", "--course-id", "course-1", "--json"]
    )

    assert code == 0, stderr
    assert len(json.loads(stdout)["rows"]) == 50
    assert [parse_qs(urlparse(url).query) for url in calls] == [
        {"limit": ["50"], "offset": ["0"]},
        {"limit": ["50"], "offset": ["50"]},
    ]


def test_diagnostics_course_does_not_print_partial_pages_after_error(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    first_rows = [
        {"student": {"sub": f"s-{index}", "name": "Lena", "href": "/"}, "cells": []}
        for index in range(50)
    ]
    responses = iter([(200, _course_page(first_rows)), (503, {"error": "service_unavailable"})])
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: next(responses))

    code, stdout, stderr = _run(["diagnostics", "course", "--course-id", "course-1"])

    assert code == 1
    assert stdout == ""
    assert "503" in stderr


def test_diagnostics_course_rejects_repeated_pages_without_partial_output(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    rows = [
        {"student": {"sub": f"s-{index}", "name": "Lena", "href": "/"}, "cells": []}
        for index in range(50)
    ]
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, _course_page(rows)))

    code, stdout, stderr = _run(
        ["diagnostics", "course", "--course-id", "course-1"]
    )

    assert code == 1
    assert stdout == ""
    assert "keinen Fortschritt" in stderr


def test_diagnostics_course_human_output_is_labelled_and_preserves_unicode(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    body = _course_page(
        [
            {
                "student": {"sub": "student-1", "name": "Ömer Şahin", "href": "/"},
                "cells": [
                    {
                        "unit_id": "unit-1",
                        "submitted_tasks": 1,
                        "total_tasks": 2,
                        "href": "/live/unit-1",
                    }
                ],
            }
        ]
    )
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        ["diagnostics", "course", "--course-id", "course-1"]
    )

    assert code == 0, stderr
    assert stdout.splitlines()[0] == (
        "student_sub\tstudent_name\tunit_id\tunit_name\tstatus\tsubmitted_tasks\ttotal_tasks"
    )
    assert "Ömer Şahin" in stdout


def test_diagnostics_course_human_output_neutralizes_terminal_controls(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    body = _course_page(
        [
            {
                "student": {
                    "sub": "student-1\x1b]52;c;secret\x07",
                    "name": "Lena\nforged\tcolumn\x9b31m",
                    "href": "/",
                },
                "cells": [
                    {
                        "unit_id": "unit-1",
                        "submitted_tasks": 1,
                        "total_tasks": 2,
                        "href": "/live/unit-1",
                    }
                ],
            }
        ]
    )
    body["units"][0]["title"] = "Netzwerke\r\ngefälscht"
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        ["diagnostics", "course", "--course-id", "course-1"]
    )

    assert code == 0, stderr
    assert len(stdout.splitlines()) == 2
    assert "\x1b" not in stdout
    assert "\x07" not in stdout
    assert "\x9b" not in stdout
    assert all(character in "\n\t" or ord(character) >= 32 for character in stdout)


def test_diagnostics_json_preserves_content_controls_as_json_data(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    name = "Lena\n\x1b[31m"
    body = _course_page(
        [{"student": {"sub": "student-1", "name": name, "href": "/"}, "cells": []}]
    )
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        ["diagnostics", "course", "--course-id", "course-1", "--json"]
    )

    assert code == 0, stderr
    assert json.loads(stdout)["rows"][0]["student"]["name"] == name


def test_diagnostics_api_error_hides_untrusted_error_details(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda *args, **kwargs: (
            503,
            {
                "error": "service_unavailable",
                "detail": "student-secret\x1b]52;c;clipboard\x07",
            },
        ),
    )

    code, stdout, stderr = _run(
        ["diagnostics", "course", "--course-id", "course-1"]
    )

    assert code == 1
    assert stdout == ""
    assert "service_unavailable" in stderr
    assert "student-secret" not in stderr
    assert "\x1b" not in stderr


def test_diagnostics_unit_task_filter_keeps_students_without_submission(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    body = {
        "cursor": "2026-09-01T08:00:00+00:00",
        "tasks": [
            {"id": "task-1", "instruction_md": "Erkläre DNS.", "position": 1, "kind": "native"},
            {"id": "task-2", "instruction_md": "Prüfe DHCP.", "position": 2, "kind": "h5p"},
        ],
        "rows": [
            {
                "student": {"sub": "student-1", "name": "Lena"},
                "tasks": [
                    {"task_id": "task-1", "has_submission": True, "average_score": 8.5},
                    {"task_id": "task-2", "has_submission": False, "average_score": None},
                ],
            },
            {
                "student": {"sub": "student-2", "name": "Ömer"},
                "tasks": [
                    {"task_id": "task-1", "has_submission": False, "average_score": None},
                    {"task_id": "task-2", "has_submission": True, "average_score": 7.0},
                ],
            },
        ],
    }
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        [
            "diagnostics",
            "unit",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--json",
        ]
    )

    assert code == 0, stderr
    result = json.loads(stdout)
    assert [task["id"] for task in result["tasks"]] == ["task-1"]
    assert [row["student"]["name"] for row in result["rows"]] == ["Lena", "Ömer"]
    assert all([cell["task_id"] for cell in row["tasks"]] == ["task-1"] for row in result["rows"])


def test_diagnostics_student_encodes_subject_and_rejects_units_without_course(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        cli,
        "_http_json",
        lambda method, url, **kwargs: (
            calls.append(url) or 200,
            {"student": {"sub": "school/student", "name": "Lena"}, "units": []},
        ),
    )

    code, _, stderr = _run(
        [
            "diagnostics",
            "student",
            "--student-sub",
            "school/student",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--json",
        ]
    )
    invalid, _, invalid_stderr = _run(
        ["diagnostics", "student", "--student-sub", "student-1", "--unit-id", "unit-1"]
    )

    assert code == 0, stderr
    assert "/students/school%2Fstudent/submissions/overview" in calls[0]
    assert parse_qs(urlparse(calls[0]).query) == {"unit_ids": ["unit-1"]}
    assert invalid == 2
    assert "--course-id" in invalid_stderr


def test_diagnostics_student_profile_loads_more_than_one_page(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    courses = [
        {
            "id": f"course-{index}",
            "title": f"Kurs {index}",
            "submitted_tasks": 0,
            "total_tasks": 0,
            "units": [],
        }
        for index in range(51)
    ]
    calls: list[int] = []

    def fake_request(method: str, url: str, **kwargs):
        offset = int(parse_qs(urlparse(url).query)["offset"][0])
        calls.append(offset)
        return 200, {
            "learner": {"sub": "student-1", "name": "Lena"},
            "summary": {},
            "courses": courses[offset : offset + 50],
        }

    monkeypatch.setattr(cli, "_http_json", fake_request)

    code, stdout, stderr = _run(
        ["diagnostics", "student", "--student-sub", "student-1", "--json"]
    )

    assert code == 0, stderr
    assert calls == [0, 50]
    assert len(json.loads(stdout)["courses"]) == 51


def test_diagnostics_student_profile_treats_later_404_as_error_without_partial_output(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    first_page = [
        {
            "id": f"course-{index}",
            "title": f"Kurs {index}",
            "submitted_tasks": 0,
            "total_tasks": 0,
            "units": [],
        }
        for index in range(50)
    ]
    responses = iter(
        [
            (
                200,
                {
                    "learner": {"sub": "student-1", "name": "Lena"},
                    "summary": {},
                    "courses": first_page,
                },
            ),
            (404, {"error": "not_found"}),
        ]
    )
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: next(responses))

    code, stdout, stderr = _run(
        ["diagnostics", "student", "--student-sub", "student-1"]
    )

    assert code == 1
    assert stdout == ""
    assert "404" in stderr


def test_diagnostics_student_course_labels_latest_h5p_points(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    body = {
        "student": {"sub": "student-1", "name": "Lena"},
        "units": [
            {
                "id": "unit-1",
                "title": "Quiz",
                "tasks": [
                    {
                        "id": "task-1",
                        "position": 1,
                        "kind": "h5p",
                        "has_submission": True,
                        "average_score": None,
                        "score_raw": 0,
                        "score_max": 0,
                        "h5p_completed": True,
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        [
            "diagnostics",
            "student",
            "--student-sub",
            "student-1",
            "--course-id",
            "course-1",
        ]
    )

    assert code == 0, stderr
    assert "h5p_punkte" in stdout.splitlines()[0]
    assert "\t0/0\tja" in stdout


def test_diagnostics_submission_json_combines_latest_dialog_transcript(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    latest = {
        "id": "submission-1",
        "task_id": "task-1",
        "student_sub": "school/student",
        "created_at": "2026-09-01T08:00:00+00:00",
        "kind": "dialog",
        "instruction_md": "Erkläre Routing.",
        "analysis_json": {
            "schema": "criteria.v2",
            "score": 4,
            "criteria_results": [
                {
                    "criterion": "Begründung",
                    "score": 8,
                    "max_score": 10,
                    "explanation_md": "Nachvollziehbar.",
                }
            ],
        },
        "feedback_md": "Baue als Nächstes ein Gegenbeispiel ein.",
    }
    transcript = {
        "id": "dialog-1",
        "course_id": "course-1",
        "task_id": "task-1",
        "status": "completed",
        "round_count": 1,
        "dialog": {
            "partner_name": "Ada",
            "partner_description_md": "Lernpartnerin",
            "role_md": "CONFIDENTIAL_ROLE_MARKER",
            "learning_goal_md": "CONFIDENTIAL_GOAL_MARKER",
            "teacher_context_md": "CONFIDENTIAL_TEACHER_MARKER",
            "opening_message_md": "Hallo",
            "response_mode": "free_text",
            "max_rounds": 4,
            "closing_prompt_md": None,
        },
        "initial_sentence_starters": [],
        "initial_starters_status": "not_required",
        "turns": [
            {
                "id": "turn-1",
                "round_nr": 1,
                "student_message_md": "Ein Router verbindet Netze.",
                "status": "completed",
                "assistant_reply_md": "Woran entscheidet er den nächsten Hop?",
                "sentence_starters": [],
                "generation_attempts": 1,
                "created_at": "2026-09-01T08:00:00+00:00",
            }
        ],
        "created_at": "2026-09-01T08:00:00+00:00",
        "updated_at": "2026-09-01T08:01:00+00:00",
        "completed_at": "2026-09-01T08:01:00+00:00",
    }
    calls: list[str] = []

    def fake_request(method: str, url: str, **kwargs):
        calls.append(url)
        if url.endswith("/submissions/submission-1/dialog"):
            return 200, transcript
        return 200, latest

    monkeypatch.setattr(cli, "_http_json", fake_request)

    code, stdout, stderr = _run(
        [
            "diagnostics",
            "submission",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "school/student",
            "--json",
        ]
    )

    assert code == 0, stderr
    result = json.loads(stdout)
    assert result["submission"] == latest
    assert result["dialog"]["turns"] == transcript["turns"]
    assert result["dialog"]["dialog"] == {
        "partner_name": "Ada",
        "partner_description_md": "Lernpartnerin",
        "opening_message_md": "Hallo",
        "response_mode": "free_text",
        "max_rounds": 4,
        "closing_prompt_md": None,
    }
    assert "/students/school%2Fstudent/submissions/submission-1/dialog" in calls[1]
    assert "role_md" not in stdout
    assert "learning_goal_md" not in stdout
    assert "CONFIDENTIAL" not in stdout


def test_diagnostics_submission_human_output_labels_formative_values(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    body = {
        "id": "submission-1",
        "task_id": "task-1",
        "student_sub": "student-1",
        "created_at": "2026-09-01T08:00:00+00:00",
        "kind": "text",
        "instruction_md": "Erkläre DNS.",
        "text_body": "DNS löst Namen auf.",
        "analysis_json": {
            "schema": "criteria.v1",
            "score": 4,
            "criteria_results": [
                {"criterion": "Funktion", "score": 8, "explanation_md": "Korrekt beschrieben."}
            ],
        },
        "feedback_md": "Ergänze den rekursiven Resolver.",
    }
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        [
            "diagnostics",
            "submission",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "student-1",
        ]
    )

    assert code == 0, stderr
    assert "Formativer Gesamtscore: 4/5" in stdout
    assert "Funktion: 8/10" in stdout
    assert "Rückmeldung" in stdout
    assert "Note" not in stdout


def test_diagnostics_submission_human_output_neutralizes_content_controls(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    body = {
        "id": "submission-1\x1b[31m",
        "task_id": "task-1",
        "student_sub": "student-1",
        "created_at": "2026-09-01T08:00:00+00:00",
        "kind": "text",
        "instruction_md": "Zeile 1\nZeile 2\x1b]0;Titel\x07",
        "text_body": "Antwort\tmit Tab\nzweite Zeile",
        "analysis_json": {
            "schema": "criteria.v2",
            "criteria_results": [
                {
                    "criterion": "Kriterium\ngefälscht",
                    "score": 2,
                    "max_score": "3\x1b]0;Maximalwert\x07",
                    "explanation_md": "Erklärung\x9b31m",
                }
            ],
        },
        "feedback_md": "Weiter so\x1b[2J",
    }
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        [
            "diagnostics",
            "submission",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "student-1",
        ]
    )

    assert code == 0, stderr
    assert "Zeile 1\nZeile 2" in stdout
    assert "Antwort mit Tab\nzweite Zeile" in stdout
    assert "\x1b" not in stdout
    assert "\x07" not in stdout
    assert "\x9b" not in stdout


def test_diagnostics_submission_human_output_labels_h5p_points(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    body = {
        "id": "submission-h5p",
        "task_id": "task-1",
        "student_sub": "student-1",
        "created_at": "2026-09-01T08:00:00+00:00",
        "kind": "h5p",
        "instruction_md": "Bearbeite das Quiz.",
        "score_raw": 2,
        "score_max": 3,
        "h5p": {"content_id": "42"},
    }
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (200, body))

    code, stdout, stderr = _run(
        [
            "diagnostics",
            "submission",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "student-1",
        ]
    )

    assert code == 0, stderr
    assert "H5P-Punkte: 2/3" in stdout
    assert "H5P-Abschluss: nein" in stdout
    assert "Note" not in stdout


def test_diagnostics_submission_no_content_is_a_successful_empty_state(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "_http_json", lambda *args, **kwargs: (204, None))

    human = _run(
        [
            "diagnostics",
            "submission",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "student-1",
        ]
    )
    machine = _run(
        [
            "diagnostics",
            "submission",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "student-1",
            "--json",
        ]
    )

    assert human[:2] == (0, "Keine Abgabe vorhanden.\n")
    assert json.loads(machine[1]) == {"submission": None, "dialog": None}


def test_diagnostics_download_is_binary_exact_private_and_requires_force(
    tmp_path, monkeypatch
) -> None:
    _configure(tmp_path, monkeypatch)
    target = tmp_path / "abgabe.bin"
    calls: list[str] = []

    payloads = iter([b"\x00GUSTAV\xff", b"replacement"])

    def fake_bytes(method: str, url: str, **kwargs):
        calls.append(url)
        return 200, next(payloads)

    monkeypatch.setattr(cli, "_http_bytes", fake_bytes)
    argv = [
        "diagnostics",
        "download",
        "--course-id",
        "course-1",
        "--unit-id",
        "unit-1",
        "--task-id",
        "task-1",
        "--student-sub",
        "school/student",
        "--output",
        str(target),
    ]

    first = _run(argv)
    assert target.read_bytes() == b"\x00GUSTAV\xff"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    refused = _run(argv)
    replaced = _run([*argv, "--force"])

    assert first[0] == 0, first[2]
    assert refused[0] == 1
    assert "--force" in refused[2]
    assert replaced[0] == 0, replaced[2]
    assert target.read_bytes() == b"replacement"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert len(calls) == 2
    assert "/students/school%2Fstudent/submissions/latest/file?disposition=attachment" in calls[0]


def test_diagnostics_download_error_leaves_no_partial_file(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    target = tmp_path / "abgabe.bin"
    monkeypatch.setattr(cli, "_http_bytes", lambda *args, **kwargs: (503, b"service unavailable"))

    code, _, stderr = _run(
        [
            "diagnostics",
            "download",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "student-1",
            "--output",
            str(target),
        ]
    )

    assert code == 1
    assert "503" in stderr
    assert not target.exists()


def test_diagnostics_download_size_limit_leaves_no_partial_file(tmp_path, monkeypatch) -> None:
    _configure(tmp_path, monkeypatch)
    target = tmp_path / "zu-gross.bin"

    def oversized(*args, **kwargs):
        assert kwargs["max_bytes"] == 10 * 1024 * 1024
        raise ValueError("response_too_large")

    monkeypatch.setattr(cli, "_http_bytes", oversized)
    code, _, stderr = _run(
        [
            "diagnostics",
            "download",
            "--course-id",
            "course-1",
            "--unit-id",
            "unit-1",
            "--task-id",
            "task-1",
            "--student-sub",
            "student-1",
            "--output",
            str(target),
        ]
    )

    assert code == 1
    assert "Größenlimit" in stderr
    assert not target.exists()
