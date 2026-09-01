from __future__ import annotations

from pathlib import Path

import pytest

from backend.tools.feature_acceptance import (
    FeatureAcceptanceConfig,
    _assert_runtime_stack_safe,
    _bff_session_ids_for_subjects,
    _jwt_subject,
    _revoke_cli_tokens,
    build_playwright_command,
    cleanup_manifest,
    run_acceptance,
    validate_feature_name,
)


def _config(**overrides: str) -> FeatureAcceptanceConfig:
    values = {
        "web_base": "https://app.localhost",
        "kc_base": "https://id.localhost",
        "storage_base": "http://127.0.0.1:54321",
        "database_url": "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        "environment": "test",
        "mutation_allowed": "1",
    }
    values.update(overrides)
    return FeatureAcceptanceConfig(**values)


@pytest.mark.parametrize(
    "value",
    ["", "../learner-navigation", "learner_navigation", "Learner-Navigation", "a/b"],
)
def test_feature_name_rejects_missing_or_unsafe_values(tmp_path: Path, value: str) -> None:
    with pytest.raises(RuntimeError, match="FEATURE"):
        validate_feature_name(value, e2e_dir=tmp_path)


def test_feature_name_rejects_unknown_spec(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="unknown FEATURE"):
        validate_feature_name("missing-feature", e2e_dir=tmp_path)


def test_feature_name_resolves_one_known_spec(tmp_path: Path) -> None:
    spec = tmp_path / "learner-navigation.spec.ts"
    spec.write_text('test("@feature-acceptance journey", () => {});', encoding="utf-8")

    assert validate_feature_name("learner-navigation", e2e_dir=tmp_path) == spec


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("web_base", "https://school.example"),
        ("kc_base", "https://login.school.example"),
        ("storage_base", "https://storage.school.example"),
        ("database_url", "postgresql://postgres:secret@db.school.example:5432/postgres"),
        ("environment", "production"),
        ("mutation_allowed", "0"),
    ],
)
def test_preflight_rejects_remote_or_unapproved_mutation(field: str, value: str) -> None:
    config = _config(**{field: value})

    with pytest.raises(RuntimeError):
        config.assert_safe()


def test_preflight_accepts_the_normalized_local_supabase_service_name() -> None:
    config = _config(
        database_url="postgresql://postgres:postgres@supabase_db_gustav-alpha2:5432/postgres"
    )

    config.assert_safe()


@pytest.mark.parametrize(
    ("container", "variable"),
    [
        ("gustav-alpha2", "TEACHING_DATABASE_URL"),
        ("gustav-alpha2", "LEARNING_DATABASE_URL"),
        ("gustav-alpha2", "SESSION_DATABASE_URL"),
        ("gustav-learning-worker", "LEARNING_WORKER_DATABASE_URL"),
    ],
)
def test_runtime_preflight_rejects_remote_database_used_by_a_running_container(
    container: str, variable: str
) -> None:
    environments = {
        "gustav-alpha2": {
            "GUSTAV_ENV": "test",
            "WEB_BASE": "https://app.localhost",
            "KC_PUBLIC_BASE_URL": "https://id.localhost",
            "DATABASE_URL": "postgresql://app:secret@supabase_db_gustav-alpha2:5432/postgres",
            "TEACHING_DATABASE_URL": "postgresql://app:secret@supabase_db_gustav-alpha2:5432/postgres",
            "LEARNING_DATABASE_URL": "postgresql://app:secret@supabase_db_gustav-alpha2:5432/postgres",
            "LEARNING_WORKER_DATABASE_URL": "postgresql://worker:secret@supabase_db_gustav-alpha2:5432/postgres",
            "SESSION_DATABASE_URL": "postgresql://postgres:secret@supabase_db_gustav-alpha2:5432/postgres",
            "SERVICE_ROLE_DSN": "postgresql://postgres:secret@supabase_db_gustav-alpha2:5432/postgres",
        },
        "gustav-frontend": {
            "GUSTAV_ENV": "test",
            "ORIGIN": "https://app.localhost",
            "KC_PUBLIC_BASE_URL": "https://id.localhost",
        },
        "gustav-h5p": {"GUSTAV_ENV": "test"},
        "gustav-learning-worker": {
            "GUSTAV_ENV": "test",
            "WEB_BASE": "https://app.localhost",
            "LEARNING_WORKER_DATABASE_URL": "postgresql://worker:secret@supabase_db_gustav-alpha2:5432/postgres",
            "LEARNING_DATABASE_URL": "postgresql://worker:secret@supabase_db_gustav-alpha2:5432/postgres",
        },
    }
    environments[container][variable] = "postgresql://app:secret@db.school.example:5432/postgres"

    with pytest.raises(RuntimeError, match=rf"{container}.*{variable}"):
        _assert_runtime_stack_safe(environments)


def test_runtime_preflight_accepts_the_running_local_compose_stack() -> None:
    _assert_runtime_stack_safe(
        {
            "gustav-alpha2": {
                "GUSTAV_ENV": "test",
                "WEB_BASE": "https://app.localhost",
                "KC_PUBLIC_BASE_URL": "https://id.localhost",
                "DATABASE_URL": "postgresql://app:secret@supabase_db_gustav-alpha2:5432/postgres",
                "TEACHING_DATABASE_URL": "postgresql://app:secret@supabase_db_gustav-alpha2:5432/postgres",
                "LEARNING_DATABASE_URL": "postgresql://app:secret@supabase_db_gustav-alpha2:5432/postgres",
                "LEARNING_WORKER_DATABASE_URL": "postgresql://worker:secret@supabase_db_gustav-alpha2:5432/postgres",
                "SESSION_DATABASE_URL": "postgresql://postgres:secret@supabase_db_gustav-alpha2:5432/postgres",
                "SERVICE_ROLE_DSN": "postgresql://postgres:secret@supabase_db_gustav-alpha2:5432/postgres",
            },
            "gustav-frontend": {
                "GUSTAV_ENV": "test",
                "ORIGIN": "https://app.localhost",
                "KC_PUBLIC_BASE_URL": "https://id.localhost",
            },
            "gustav-h5p": {"GUSTAV_ENV": "test"},
            "gustav-learning-worker": {
                "GUSTAV_ENV": "test",
                "WEB_BASE": "https://app.localhost",
                "LEARNING_WORKER_DATABASE_URL": "postgresql://worker:secret@supabase_db_gustav-alpha2:5432/postgres",
                "LEARNING_DATABASE_URL": "postgresql://worker:secret@supabase_db_gustav-alpha2:5432/postgres",
            },
        }
    )


def test_jwt_subject_is_decoded_without_exposing_or_accepting_malformed_tokens() -> None:
    import base64
    import json

    payload = (
        base64.urlsafe_b64encode(json.dumps({"sub": "e2e-user-id"}).encode()).decode().rstrip("=")
    )
    token = f"header.{payload}.signature"

    assert _jwt_subject(token) == "e2e-user-id"
    assert _jwt_subject("not-a-jwt") is None
    assert _jwt_subject("header.%%%25.signature") is None


def test_bff_session_matching_keeps_foreign_sessions_outside_cleanup() -> None:
    import base64
    import json

    def token(subject: str) -> str:
        payload = (
            base64.urlsafe_b64encode(json.dumps({"sub": subject}).encode()).decode().rstrip("=")
        )
        return f"header.{payload}.signature"

    rows = [
        ("owned-session", token("owned-user"), token("owned-user")),
        ("foreign-session", token("foreign-user"), token("foreign-user")),
        ("malformed-session", "not-a-token", "not-a-token"),
    ]

    assert _bff_session_ids_for_subjects(rows, {"owned-user"}) == ["owned-session"]


def test_targeted_command_selects_only_the_requested_marked_spec(tmp_path: Path) -> None:
    spec = tmp_path / "learner-navigation.spec.ts"
    spec.write_text('test("@feature-acceptance journey", () => {});', encoding="utf-8")

    command = build_playwright_command(
        feature="learner-navigation", all_features=False, e2e_dir=tmp_path
    )

    assert command[-3:] == [str(spec), "--grep", "@feature-acceptance"]


def test_targeted_detail_command_selects_only_the_requested_detail_spec(tmp_path: Path) -> None:
    spec = tmp_path / "course-archive.spec.ts"
    spec.write_text('test("@feature-detail permanent deletion", () => {});', encoding="utf-8")

    command = build_playwright_command(
        feature="course-archive", all_features=False, profile="detail", e2e_dir=tmp_path
    )

    assert command[-3:] == [str(spec), "--grep", "@feature-detail"]


def test_regression_command_selects_all_marked_specs(tmp_path: Path) -> None:
    command = build_playwright_command(feature=None, all_features=True, e2e_dir=tmp_path)

    assert command[-2:] == ["--grep", "@feature-acceptance"]


def test_cli_token_cleanup_uses_the_authenticated_profile_action() -> None:
    """Cleanup must use the Browser-BFF product path, not a direct API call."""

    class Response:
        status_code = 200
        url = "https://app.localhost/profile"
        text = (
            '<form method="POST" action="?/revokeCliToken">'
            '<input type="hidden" name="token_id" '
            'value="11111111-1111-4111-8111-111111111111" />'
            "</form>"
        )

    class HTTP:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict[str, str]]] = []

        def get(self, url: str, **kwargs: object) -> Response:
            assert url == "https://app.localhost/profile"
            return Response()

        def post(self, url: str, *, data: dict[str, str], **kwargs: object) -> Response:
            self.calls.append(("POST", url, data))
            return Response()

    class Session:
        config = type(
            "Config",
            (),
            {"web_base": "https://app.localhost", "timeout_seconds": 30},
        )()
        session = HTTP()

    session = Session()
    _revoke_cli_tokens(session)  # type: ignore[arg-type]

    assert session.session.calls == [
        (
            "POST",
            "https://app.localhost/profile?/revokeCliToken",
            {"token_id": "11111111-1111-4111-8111-111111111111"},
        )
    ]


def test_cleanup_refuses_a_foreign_identity_before_network_access(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"version":1,"run_id":"0123456789ab","users":'
        '[{"email":"real.teacher@example.com","role":"teacher"}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="foreign identity"):
        cleanup_manifest(_config(), path=state_path)


def test_cleanup_refuses_an_invalid_registered_h5p_id_before_network_access(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"version":1,"run_id":"0123456789ab","users":[],"h5p_content_ids":["../foreign"]}\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="H5P"):
        cleanup_manifest(_config(), path=state_path)


def test_cleanup_refuses_h5p_content_bound_to_an_unregistered_owner(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"version":2,"run_id":"0123456789ab","users":[],"h5p_contents":'
        '[{"content_id":"42","owner_email":"foreign@example.com"}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="H5P ownership"):
        cleanup_manifest(_config(), path=state_path)


def test_cleanup_routes_each_h5p_content_to_its_exact_teacher(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json

    import backend.tools.feature_acceptance as tool

    state_path = tmp_path / "state.json"
    teachers = [
        {"email": "one.e2e-0123456789ab@example.test", "role": "teacher"},
        {"email": "two.e2e-0123456789ab@example.test", "role": "teacher"},
    ]
    state_path.write_text(
        json.dumps(
            {
                "version": 2,
                "run_id": "0123456789ab",
                "users": teachers,
                "h5p_contents": [
                    {"content_id": "41", "owner_email": teachers[0]["email"]},
                    {"content_id": "42", "owner_email": teachers[1]["email"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("E2E_TEST_PASSWORD", "synthetic-secret")
    monkeypatch.setattr(tool.KeycloakAdmin, "token", lambda self: "admin-token")
    monkeypatch.setattr(
        tool, "_keycloak_user_id", lambda admin, token, email: f"id-{email.split('.', 1)[0]}"
    )
    monkeypatch.setattr(tool, "_reset_password", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tool.BrowserSession,
        "login",
        lambda self, *, email, password: setattr(self, "test_email", email),
    )
    monkeypatch.setattr(tool, "_revoke_cli_tokens", lambda *args: None)
    monkeypatch.setattr(tool, "_delete_owned_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool, "_assert_owned_product_data_empty", lambda *args: None)
    monkeypatch.setattr(tool, "_delete_run_sessions", lambda *args, **kwargs: None)
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        tool,
        "_delete_registered_h5p_contents",
        lambda session, ids: calls.append((session.test_email, ids)),
    )

    cleanup_manifest(_config(), keep_manifest=True, path=state_path)

    assert calls == [(teachers[0]["email"], ["41"]), (teachers[1]["email"], ["42"])]


def test_cleanup_recovers_worker_and_smtp_state_before_preserving_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json

    import backend.tools.feature_acceptance as tool

    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "version": 2,
                "run_id": "0123456789ab",
                "users": [],
                "h5p_contents": [],
                "worker_pause_requested": True,
                "keycloak_smtp_restore": {"host": "smtp.local", "port": "2525"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(tool.KeycloakAdmin, "token", lambda self: "admin-token")
    recovered: list[object] = []
    monkeypatch.setattr(
        tool,
        "_set_worker_paused",
        lambda paused, **kwargs: recovered.append(("worker", paused)),
    )
    monkeypatch.setattr(
        tool,
        "_restore_realm_smtp",
        lambda admin, token, smtp: recovered.append(("smtp", smtp)),
    )

    cleanup_manifest(_config(), keep_manifest=True, path=state_path)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert recovered == [("worker", False), ("smtp", {"host": "smtp.local", "port": "2525"})]
    assert state["worker_pause_requested"] is False
    assert "keycloak_smtp_restore" not in state


def test_per_test_cleanup_preserves_run_identities_for_the_final_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json

    import backend.tools.feature_acceptance as tool

    state_path = tmp_path / "state.json"
    teacher = {
        "email": "teacher.e2e-0123456789ab@example.test",
        "role": "teacher",
    }
    state_path.write_text(
        json.dumps({"version": 1, "run_id": "0123456789ab", "users": [teacher]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("E2E_TEST_PASSWORD", "synthetic-secret")
    monkeypatch.setattr(tool.KeycloakAdmin, "token", lambda self: "admin-token")
    monkeypatch.setattr(tool, "_keycloak_user_id", lambda *args, **kwargs: "teacher-id")
    monkeypatch.setattr(tool, "_reset_password", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool.BrowserSession, "login", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool, "_revoke_cli_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool, "_delete_owned_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool, "_assert_owned_product_data_empty", lambda *args: None)
    monkeypatch.setattr(tool, "_delete_run_sessions", lambda *args, **kwargs: None)
    deleted: list[str] = []
    monkeypatch.setattr(
        tool,
        "_delete_user",
        lambda *args, user_id, **kwargs: deleted.append(user_id),
    )

    cleanup_manifest(_config(), keep_manifest=True, path=state_path)

    assert deleted == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["users"] == [teacher]


def test_failed_playwright_run_still_removes_the_private_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import backend.tools.feature_acceptance as tool

    e2e_dir = tmp_path / "frontend" / "e2e"
    e2e_dir.mkdir(parents=True)
    (e2e_dir / "learner-navigation.spec.ts").write_text(
        'test("@feature-acceptance journey", () => {});', encoding="utf-8"
    )
    monkeypatch.setattr(tool, "E2E_DIR", e2e_dir)
    monkeypatch.setattr(tool, "FRONTEND_ROOT", e2e_dir.parent)
    monkeypatch.setattr(tool, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(tool, "LOCK_PATH", tmp_path / "run.lock")
    monkeypatch.setattr(tool, "_load_dotenv", lambda path: None)
    monkeypatch.setattr(
        tool,
        "_inspect_runtime_environments",
        lambda: {container: {} for container in tool.RUNTIME_CONTAINERS},
    )
    monkeypatch.setattr(tool, "_assert_runtime_stack_safe", lambda environments: None)
    monkeypatch.setenv("WEB_BASE", "https://app.localhost")
    monkeypatch.setenv("KC_BASE", "https://id.localhost")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv(
        "E2E_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )
    monkeypatch.setenv("GUSTAV_ENV", "test")
    monkeypatch.setenv("E2E_LOCAL_MUTATION_ALLOWED", "1")
    monkeypatch.setenv("E2E_TEST_PASSWORD", "synthetic-secret")

    results = iter([0, 7])

    class Result:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode

    monkeypatch.setattr(
        tool.subprocess,
        "run",
        lambda *args, **kwargs: Result(next(results)),
    )

    assert run_acceptance(feature="learner-navigation", all_features=False) == 7
    assert not tool.STATE_PATH.exists()
