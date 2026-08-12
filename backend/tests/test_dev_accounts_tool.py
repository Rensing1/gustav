from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

from backend.tools import dev_accounts

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_local_url_guard_accepts_only_browser_local_hosts() -> None:
    for url in (
        "https://app.localhost",
        "https://id.localhost",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://[::1]:8000",
    ):
        dev_accounts.require_local_url(url)

    for url in (
        "https://gustav.example",
        "https://school.example",
        "http://keycloak:8080",
        "https://host.docker.internal",
    ):
        with pytest.raises(RuntimeError, match="local URL required"):
            dev_accounts.require_local_url(url)


def test_ai_url_guard_accepts_local_or_remote_https_providers() -> None:
    for url in (
        "http://127.0.0.1:8111/api/v1",
        "http://localhost:11434/v1",
        "https://api.mistral.ai/v1",
    ):
        dev_accounts.require_ai_url(url)

    for url in (
        "http://api.mistral.ai/v1",
        "ftp://api.mistral.ai/v1",
        "https://user:password@api.mistral.ai/v1",
    ):
        with pytest.raises(RuntimeError, match="secure AI URL required"):
            dev_accounts.require_ai_url(url)


def test_remote_ai_uses_public_ca_bundle_instead_of_local_caddy_ca() -> None:
    local_ca = "/tmp/caddy-root.crt"

    assert (
        dev_accounts.ai_verify_for_url("http://127.0.0.1:8111/api/v1", local_verify=local_ca)
        == local_ca
    )
    remote_verify = dev_accounts.ai_verify_for_url(
        "https://api.mistral.ai/v1", local_verify=local_ca
    )
    assert remote_verify != local_ca
    assert Path(str(remote_verify)).is_file()


def test_ensure_env_credentials_adds_missing_values_without_overwriting(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "WEB_BASE=https://app.localhost\n"
        "ALLOWED_REGISTRATION_DOMAINS=@school.example\n"
        "DEV_TEACHER_EMAIL=existing.teacher@school.example\n",
        encoding="utf-8",
    )

    values = dev_accounts.ensure_env_credentials(env_path)

    text = env_path.read_text(encoding="utf-8")
    assert values["DEV_TEACHER_EMAIL"] == "existing.teacher@school.example"
    assert text.count("DEV_TEACHER_EMAIL=") == 1
    assert values["DEV_STUDENT_EMAIL"].endswith("@school.example")
    assert len(values["DEV_TEACHER_PASSWORD"]) >= 20
    assert len(values["DEV_STUDENT_PASSWORD"]) >= 20
    assert "DEV_STUDENT_PASSWORD=" in text
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_ensure_env_credentials_fills_blank_values_but_preserves_unrelated_lines(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    original_comment = "# local operator settings"
    env_path.write_text(
        f"{original_comment}\n"
        "E2E_EMAIL_DOMAIN=example.test\n"
        "DEV_TEACHER_EMAIL=\n"
        "DEV_TEACHER_PASSWORD=chosen-Aa1!password\n"
        "DEV_STUDENT_EMAIL=\n"
        "DEV_STUDENT_PASSWORD=\n",
        encoding="utf-8",
    )

    values = dev_accounts.ensure_env_credentials(env_path)

    text = env_path.read_text(encoding="utf-8")
    assert original_comment in text
    assert values["DEV_TEACHER_EMAIL"] == "dev.teacher@example.test"
    assert values["DEV_STUDENT_EMAIL"] == "dev.student@example.test"
    assert values["DEV_TEACHER_PASSWORD"] == "chosen-Aa1!password"
    assert text.count("DEV_TEACHER_PASSWORD=") == 1


def test_ensure_env_credentials_removes_ambiguous_duplicate_persona_keys(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "E2E_EMAIL_DOMAIN=example.test\n"
        "DEV_TEACHER_EMAIL=first@example.test\n"
        "DEV_TEACHER_EMAIL=second@example.test\n",
        encoding="utf-8",
    )

    values = dev_accounts.ensure_env_credentials(env_path)

    assert values["DEV_TEACHER_EMAIL"] == "second@example.test"
    assert env_path.read_text(encoding="utf-8").count("DEV_TEACHER_EMAIL=") == 1


def test_fixture_spec_is_modular_diverse_and_has_two_of_three_convergence() -> None:
    spec = dev_accounts.FIXTURE_SPEC

    assert spec["unit_type"] == "modular"
    assert [phase["title"] for phase in spec["phases"]] == [
        "Orientierung",
        "Erarbeitung",
        "Transfer",
    ]
    modules = {module["key"]: module for phase in spec["phases"] for module in phase["modules"]}
    assert len(modules) == 8
    assert modules["transfer"]["required_prereq_count"] == 2
    assert modules["practice_native"]["module_kind"] == "practice"
    assert modules["practice_h5p"]["module_kind"] == "practice"
    assert modules["practice_native"]["materials"] == []
    assert modules["practice_h5p"]["materials"] == []
    native_practice = modules["practice_native"]["tasks"][0]
    assert native_practice["kind"] == "native"
    assert native_practice["model_solution_md"]
    assert set(dev_accounts.FIXTURE_EDGES) == {
        ("start", "analysis"),
        ("start", "programming"),
        ("start", "interactive"),
        ("analysis", "transfer"),
        ("programming", "transfer"),
        ("interactive", "transfer"),
        ("transfer", "finish"),
        ("start", "practice_native"),
        ("start", "practice_h5p"),
    }
    practice_keys = {"practice_native", "practice_h5p"}
    assert not any(source in practice_keys for source, _ in dev_accounts.FIXTURE_EDGES)

    kinds = {task["kind"] for module in modules.values() for task in module["tasks"]}
    assert kinds == {"native", "visual", "scratch", "calliope", "filius", "h5p", "dialog"}
    material_kinds = {
        material["kind"] for module in modules.values() for material in module["materials"]
    }
    assert material_kinds == {"markdown", "image", "pdf"}


def test_state_manifest_is_private_and_round_trips(tmp_path: Path) -> None:
    state_path = tmp_path / "dev-accounts-state.json"
    state = {
        "status": "complete",
        "course_id": "00000000-0000-0000-0000-000000000001",
        "unit_id": "00000000-0000-0000-0000-000000000002",
        "h5p_content_id": "123",
    }

    dev_accounts.write_state(state_path, state)

    assert dev_accounts.read_state(state_path) == state
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600


def test_h5p_cleanup_only_uses_content_id_recorded_by_tool() -> None:
    assert dev_accounts.h5p_content_id_for_cleanup({"h5p_content_id": "123"}) == "123"
    assert dev_accounts.h5p_content_id_for_cleanup({"h5p_content_id": "not-numeric"}) is None
    assert dev_accounts.h5p_content_id_for_cleanup({}) is None


def test_reset_deletes_only_resources_visible_to_the_authenticated_dev_teacher() -> None:
    class Response:
        def __init__(self, payload: object, status_code: int = 200) -> None:
            self._payload = payload
            self.status_code = status_code

        def json(self) -> object:
            return self._payload

    class TeacherSession:
        def __init__(self) -> None:
            self.session = self
            self.config = type(
                "Config", (), {"web_base": "https://app.localhost", "timeout_seconds": 1}
            )()
            self.mutations: list[tuple[str, str, tuple[int, ...]]] = []

        def request(self, method: str, path: str, **kwargs: object) -> Response:
            if method == "GET" and path == "/internal/health/learning-worker":
                return Response(
                    {
                        "status": "healthy",
                        "checks": [{"check": "lifecycle_commands", "status": "ok"}],
                    }
                )
            if method == "GET" and path == "/api/teaching/course-deletion-jobs":
                return Response([])
            if method == "GET" and path == "/api/teaching/courses":
                status = dict(kwargs.get("params", {})).get("status")  # type: ignore[arg-type]
                return Response([
                    {"id": "own-course", "title": "Eigener Testkurs"}
                ] if status == "active" else [])
            if method == "GET" and path == "/api/teaching/units":
                return Response([{"id": "own-unit"}])
            if method == "GET" and path == "/api/teaching/course-deletion-jobs/job-1":
                return Response({"id": "job-1", "status": "completed"})
            expected = tuple(kwargs.get("expected", ()))
            self.mutations.append((method, path, expected))
            if method == "POST" and path.endswith("/deletion-jobs"):
                return Response({"id": "job-1", "status": "pending"})
            return Response({})

    teacher = TeacherSession()

    dev_accounts._delete_owned_data(teacher, timeout_seconds=1)  # type: ignore[arg-type]

    assert teacher.mutations == [
        ("DELETE", "/api/teaching/units/own-unit", (204,)),
        (
            "POST",
            "/api/teaching/courses/own-course/deletion-jobs",
            (202,),
        ),
    ]


def test_reset_waits_for_a_previous_course_deletion_before_deleting_its_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __init__(self, payload: object, status_code: int = 200) -> None:
            self._payload = payload
            self.status_code = status_code

        def json(self) -> object:
            return self._payload

    class TeacherSession:
        def __init__(self) -> None:
            self.session = self
            self.config = type(
                "Config", (), {"web_base": "https://app.localhost", "timeout_seconds": 1}
            )()
            self.mutations: list[tuple[str, str]] = []

        def request(self, method: str, path: str, **_kwargs: object) -> Response:
            if method == "GET" and path == "/internal/health/learning-worker":
                return Response(
                    {
                        "status": "healthy",
                        "checks": [{"check": "lifecycle_commands", "status": "ok"}],
                    }
                )
            if method == "GET" and path == "/api/teaching/course-deletion-jobs":
                return Response(
                    [
                        {
                            "id": "interrupted-job",
                            "course_id": "interrupted-course",
                            "course_title": "Unterbrochener Kurs",
                            "status": "pending",
                        }
                    ]
                )
            if method == "GET" and path == "/api/teaching/course-deletion-jobs/interrupted-job":
                return Response({"id": "interrupted-job", "status": "completed"})
            if method == "GET" and path == "/api/teaching/courses":
                return Response([])
            if method == "GET" and path == "/api/teaching/units":
                return Response([{"id": "interrupted-unit"}])
            self.mutations.append((method, path))
            return Response({})

    monkeypatch.setattr(dev_accounts.time, "sleep", lambda _seconds: None)
    teacher = TeacherSession()

    dev_accounts._delete_owned_data(
        teacher,  # type: ignore[arg-type]
        timeout_seconds=1,
        prior_state={"course_id": "interrupted-course"},
    )

    assert teacher.mutations == [("DELETE", "/api/teaching/units/interrupted-unit")]


def test_reset_retries_failed_jobs_restores_archived_courses_and_records_recovery(
    tmp_path: Path,
) -> None:
    class Response:
        def __init__(self, payload: object) -> None:
            self._payload = payload
            self.status_code = 200

        def json(self) -> object:
            return self._payload

    class TeacherSession:
        def __init__(self) -> None:
            self.session = self
            self.config = type(
                "Config", (), {"web_base": "https://app.localhost", "timeout_seconds": 1}
            )()
            self.calls: list[tuple[str, str]] = []

        def request(self, method: str, path: str, **kwargs: object) -> Response:
            self.calls.append((method, path))
            if method in {"POST", "DELETE"}:
                manifest = dev_accounts.read_state(state_path)
                assert manifest is not None
                assert manifest["status"] == "resetting"
            if method == "GET" and path == "/internal/health/learning-worker":
                return Response(
                    {
                        "status": "healthy",
                        "checks": [{"check": "lifecycle_commands", "status": "ok"}],
                    }
                )
            if method == "GET" and path == "/api/teaching/course-deletion-jobs":
                return Response(
                    [
                        {
                            "id": "failed-job",
                            "course_id": "failed-course",
                            "course_title": "Fehlgeschlagener Kurs",
                            "status": "failed",
                        }
                    ]
                )
            if method == "POST" and path.endswith("failed-course/deletion-jobs"):
                return Response({"id": "retried-job", "status": "pending"})
            if method == "GET" and path.endswith("/retried-job"):
                return Response({"id": "retried-job", "status": "completed"})
            if method == "GET" and path == "/api/teaching/courses":
                status = dict(kwargs.get("params", {})).get("status")  # type: ignore[arg-type]
                return Response([
                    {"id": "archived-course", "title": "Archivierter Kurs"}
                ] if status == "archived" else [])
            if method == "GET" and path == "/api/teaching/units":
                return Response([{"id": "owned-unit"}])
            if method == "POST" and path.endswith("archived-course/deletion-jobs"):
                return Response({"id": "new-job", "status": "pending"})
            if method == "GET" and path.endswith("/new-job"):
                return Response({"id": "new-job", "status": "completed"})
            return Response({})

    state_path = tmp_path / "dev-accounts-state.json"
    teacher = TeacherSession()

    dev_accounts._delete_owned_data(
        teacher,  # type: ignore[arg-type]
        timeout_seconds=1,
        prior_state={"h5p_content_id": "123"},
        state_path=state_path,
    )

    assert ("POST", "/api/teaching/courses/failed-course/deletion-jobs") in teacher.calls
    assert ("POST", "/api/teaching/courses/archived-course/restore") in teacher.calls
    assert ("DELETE", "/api/teaching/units/owned-unit") in teacher.calls
    recovery = dev_accounts.read_state(state_path)
    assert recovery is not None
    assert recovery["status"] == "resetting"
    assert recovery["h5p_content_id"] == "123"
    courses = {item["id"]: item for item in recovery["reset_targets"]["courses"]}
    assert courses["failed-course"]["job_id"] == "retried-job"
    assert courses["archived-course"]["job_id"] == "new-job"
    first_mutation = next(
        call for call in teacher.calls if call[0] in {"POST", "DELETE"}
    )
    assert first_mutation == ("POST", "/api/teaching/courses/failed-course/deletion-jobs")


def test_worker_preflight_rejects_missing_lifecycle_commands() -> None:
    class Session:
        def request(self, _method: str, _path: str, **_kwargs: object):
            return type(
                "Response",
                (),
                {
                    "json": lambda _self: {
                        "status": "healthy",
                        "checks": [{"check": "queue_visibility", "status": "ok"}],
                    }
                },
            )()

    with pytest.raises(RuntimeError, match="lifecycle_commands"):
        dev_accounts.run_product_worker_preflight(Session())  # type: ignore[arg-type]


def test_course_catalog_paginates_at_the_public_endpoint_limit() -> None:
    class Response:
        def __init__(self, payload: object) -> None:
            self._payload = payload

        def json(self) -> object:
            return self._payload

    class Session:
        def __init__(self) -> None:
            self.offsets: list[int] = []

        def request(self, method: str, path: str, **kwargs: object) -> Response:
            assert method == "GET"
            assert path == "/api/teaching/courses"
            params = dict(kwargs.get("params", {}))  # type: ignore[arg-type]
            assert params["limit"] == 50
            offset = int(params["offset"])
            self.offsets.append(offset)
            if offset == 0:
                return Response([{"id": f"course-{index}"} for index in range(50)])
            return Response([{"id": "course-50"}])

    session = Session()

    courses = dev_accounts._list_course_catalog(  # type: ignore[arg-type]
        session,
        status="active",
    )

    assert len(courses) == 51
    assert session.offsets == [0, 50]


def test_product_storage_preflight_warms_adapter_without_creating_an_intent() -> None:
    class Response:
        def __init__(self, payload: object) -> None:
            self._payload = payload

        def json(self) -> object:
            return self._payload

    class TeacherSession:
        def __init__(self) -> None:
            self.probe: tuple[str, dict[str, object], tuple[int, ...]] | None = None

        def request(self, method: str, path: str, **kwargs: object) -> Response:
            if method == "GET" and path == "/api/teaching/units":
                return Response([{"id": "unit-1"}])
            if method == "GET" and path == "/api/teaching/units/unit-1/sections":
                return Response([{"id": "section-1"}])
            self.probe = (
                path,
                dict(kwargs.get("json_body", {})),  # type: ignore[arg-type]
                tuple(kwargs.get("expected", ())),
            )
            return Response({"error": "bad_request", "detail": "mime_not_allowed"})

    teacher = TeacherSession()

    dev_accounts.run_product_storage_preflight(teacher)  # type: ignore[arg-type]

    assert teacher.probe == (
        "/api/teaching/units/unit-1/sections/section-1/materials/upload-intents",
        {
            "filename": "dev-accounts-storage-preflight.invalid",
            "mime_type": "application/x-gustav-storage-preflight",
            "size_bytes": 1,
        },
        (400,),
    )


def _complete_state() -> dict[str, object]:
    modules = [
        module for phase in dev_accounts.FIXTURE_SPEC["phases"] for module in phase["modules"]
    ]
    module_ids = {module["key"]: f"module-{index}" for index, module in enumerate(modules)}
    task_keys = [task["key"] for module in modules for task in module["tasks"]]
    return {
        "status": "complete",
        "course_id": "course-1",
        "unit_id": "unit-1",
        "h5p_content_id": "123",
        "dialog_session_id": "dialog-1",
        "module_ids": module_ids,
        "section_ids": {key: f"section-{index}" for index, key in enumerate(module_ids)},
        "task_ids": {key: f"task-{index}" for index, key in enumerate(task_keys)},
    }


def _legacy_complete_state() -> dict[str, object]:
    state = _complete_state()
    for key in dev_accounts.PRACTICE_MODULE_KEYS:
        state["module_ids"].pop(key)  # type: ignore[union-attr]
        state["section_ids"].pop(key)  # type: ignore[union-attr]
    state["task_ids"].pop("practice_native_task")  # type: ignore[union-attr]
    state["task_ids"].pop("practice_h5p_task")  # type: ignore[union-attr]
    state["version"] = 2
    return state


@pytest.mark.parametrize(
    ("state", "course_count", "expected"),
    [
        (_complete_state(), 1, "ready"),
        (_legacy_complete_state(), 1, "upgrade"),
        ({**_legacy_complete_state(), "status": "upgrading"}, 1, "upgrade"),
        (_complete_state(), 0, "rebuild"),
        ({"status": "complete"}, 1, "rebuild"),
        ({"status": "building"}, 0, "rebuild"),
        ({"status": "building"}, 1, "rebuild"),
        (None, 0, "create"),
        (None, 1, "explicit_reset"),
        (_complete_state(), 2, "explicit_reset"),
    ],
)
def test_fixture_decision_is_idempotent_and_fail_closed(
    state: dict[str, object] | None, course_count: int, expected: str
) -> None:
    assert dev_accounts.fixture_decision(state, course_count=course_count) == expected


def test_generated_pdf_contains_a_real_page_and_cross_reference_table() -> None:
    payload = dev_accounts._pdf_bytes()

    assert payload.startswith(b"%PDF-1.4")
    assert b"/Type /Page" in payload
    assert b"xref\n0 6" in payload
    assert b"startxref" in payload
    assert payload.rstrip().endswith(b"%%EOF")


def test_make_targets_keep_provision_reset_and_browser_smoke_explicit() -> None:
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

    def body(target: str) -> str:
        match = re.search(
            rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n"
            rf"(?P<body>.*?)(?=^\.PHONY: |\Z)",
            makefile,
        )
        assert match is not None, f"missing Make target {target}"
        return match.group("body")

    assert "backend.tools.dev_accounts ensure" in body("dev-accounts")
    assert "backend.tools.dev_accounts reset" in body("reset-dev-accounts")
    smoke = body("test-dev-accounts")
    assert "RUN_DEV_ACCOUNTS=1" in smoke
    assert "@dev-accounts" in smoke
    assert "NODE_EXTRA_CA_CERTS=../.tmp/caddy-root.crt" in smoke
    acceptance = body("test-feature-acceptance")
    assert "NODE_EXTRA_CA_CERTS=../.tmp/caddy-root.crt" in acceptance
    assert "test-dev-accounts" not in body("verify")


def test_public_env_template_names_personas_without_shipping_credentials() -> None:
    template = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    for key in dev_accounts.DEV_CREDENTIAL_KEYS:
        assert re.search(rf"(?m)^{key}=\s*$", template)


def test_playwright_dev_account_smoke_is_opt_in() -> None:
    smoke = (PROJECT_ROOT / "frontend/e2e/dev-accounts.spec.ts").read_text(encoding="utf-8")
    assert "@dev-accounts" in smoke
    assert "RUN_DEV_ACCOUNTS" in smoke
    assert "DEV_TEACHER_EMAIL" in smoke
    assert "DEV_STUDENT_EMAIL" in smoke
    assert "h5p-player" in smoke
    assert "KI-Dialog" in smoke


def test_cli_reports_preflight_errors_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("WEB_BASE=https://app.localhost\n", encoding="utf-8")

    def fail(_config: dev_accounts.DevConfig) -> None:
        raise RuntimeError("local URL required, got host='remote.example'")

    monkeypatch.setattr(dev_accounts, "ensure_command", fail)

    assert dev_accounts.main(["ensure", "--env-file", str(env_path)]) == 1
    captured = capsys.readouterr()
    assert "Fehler: local URL required" in captured.err
    assert "Traceback" not in captured.err
