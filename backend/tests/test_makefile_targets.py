import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = PROJECT_ROOT / "Makefile"
FRONTEND_VITEST_CONFIG = PROJECT_ROOT / "frontend" / "vitest.config.ts"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
BACKEND_REQUIREMENTS = PROJECT_ROOT / "backend/web/requirements.txt"
BACKEND_HARNESS_REQUIREMENTS = PROJECT_ROOT / "backend/requirements-harness.txt"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    target_name = re.escape(target)
    match = re.search(
        rf"(?ms)^\.PHONY: {target_name}\n{target_name}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_reset_local_provisions_worker_login_before_recreating_worker() -> None:
    body = _target_body("reset-local")

    assert "$(MAKE) db-login-user" in body
    assert "$(MAKE) learning-worker-db-login-user" in body
    assert "docker compose up -d --build --force-recreate web learning-worker h5p" in body
    assert body.index("$(MAKE) db-login-user") < body.index(
        "$(MAKE) learning-worker-db-login-user"
    )
    assert body.index("$(MAKE) learning-worker-db-login-user") < body.index(
        "docker compose up -d --build --force-recreate web learning-worker h5p"
    )


def test_test_db_security_runs_csrf_and_session_baseline_regressions() -> None:
    """PR 2 makes CSRF/session regressions part of a named hard gate."""

    body = _target_body("test-db-security")

    for required_test in (
        "backend/tests/test_auth_cookie_policies.py",
        "backend/tests/test_session_sync_api.py",
        "backend/tests/test_learning_submissions_default_strict_csrf.py",
        "backend/tests/test_learning_submissions_prod_csrf.py",
        "backend/tests/test_learning_csrf_trust_proxy.py",
        "backend/tests/test_learning_csrf_diag_log_redaction.py",
        "backend/tests/test_teaching_csrf_other_writes.py",
    ):
        assert required_test in body


def test_test_db_security_runs_authz_and_rls_baseline_regressions() -> None:
    """PR 3 makes Authz/RLS regressions visible in the same security gate."""

    body = _target_body("test-db-security")

    assert "REQUIRE_DB_TESTS=1" in body
    assert (
        "backend/tests/test_teaching_live_detail_api.py::"
        "test_latest_detail_requires_owner_and_valid_ids"
    ) in body
    assert (
        "backend/tests/test_teaching_live_detail_api.py::"
        "test_latest_detail_hides_submission_after_membership_removal"
    ) in body
    assert (
        "backend/tests/test_teaching_live_detail_api.py::"
        "test_latest_detail_relation_mismatch_is_rejected_by_submission_projection"
    ) in body
    assert "backend/tests/test_teaching_live_detail_api.py \\" not in body

    for required_test in (
        "backend/tests/test_api_auth_unauthenticated.py",
        "backend/tests/test_bearer_jwt_auth_api.py",
        "backend/tests/test_bff_authorization_session_api.py",
        "backend/tests/test_session_bootstrap_api.py",
        "backend/tests/test_teaching_live_detail_relation_guard.py",
        "backend/tests/test_learning_student_rls_policies.py",
        "backend/tests/test_learning_rls_owners.py",
        "backend/tests/test_teaching_rls_policies_optional.py",
        "backend/tests/test_teaching_memberships_delete_rls_policy.py",
        "backend/tests/migration/test_course_memberships_rls_delete_policy.py",
        "backend/tests/migration/test_memberships_remove_definer_owner_binding.py",
        "backend/tests/migration/test_rls_exec_privileges.py",
    ):
        assert required_test in body


def test_db_security_rls_optional_policy_test_uses_strict_db_guard() -> None:
    """A file in the hard RLS gate must fail, not skip, when DB is required."""

    test_path = PROJECT_ROOT / "backend/tests/test_teaching_rls_policies_optional.py"
    text = test_path.read_text(encoding="utf-8")

    assert "require_db_or_skip" in text
    assert "RLS limited DSN not configured or DB unreachable" not in text


def test_upload_llm_boundaries_profile_runs_focused_security_contracts() -> None:
    """PR 4 makes upload and LLM data boundaries a named hard gate."""

    body = _target_body("test-upload-llm-boundaries")

    for required_test in (
        "backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_requires_authentication",
        "backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_forbidden_for_teacher",
        "backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_csrf_violation_sets_detail",
        "backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_requires_origin_or_referer_header",
        "backend/tests/test_learning_upload_intents_behavior.py::test_upload_intent_fail_closed_when_authorization_check_unavailable",
        "backend/tests/test_teaching_upload_intents_limits_and_keys.py",
        "backend/tests/test_learning_internal_proxy_security.py",
        "backend/tests/test_learning_internal_proxy_limit_config.py",
        "backend/tests/test_storage_config_limits.py",
        "backend/tests/test_storage_key_helpers.py",
        "backend/tests/test_storage_verification_helper.py",
        "backend/tests/test_storage_verification_streaming_security.py",
        "backend/tests/test_learning_upload_content_signature_validation.py",
        "backend/tests/test_submission_content_signatures.py",
        "backend/tests/test_learning_submission_kind_guard.py",
        "backend/tests/test_learning_submission_payload_mime_casing.py",
        "backend/tests/test_learning_worker_feedback_error_mapping.py",
        "backend/tests/learning_adapters/test_feedback_program_dspy_prompt.py",
        "backend/tests/learning_adapters/test_feedback_program_dspy_structured.py",
        "backend/tests/learning_adapters/test_visual_feedback_program_dspy_structured.py",
        "backend/tests/test_privacy_logging_contract.py",
    ):
        assert required_test in body


def test_verify_runs_frontend_h5p_profile() -> None:
    """PR 7 makes frontend type and unit checks part of the full verify path."""

    body = _target_body("verify")

    assert "$(MAKE) test-frontend-h5p" in body
    assert "$(MAKE) test-h5p" not in body


def test_frontend_hard_gate_builds_the_production_artifact() -> None:
    """Type and unit checks alone must not hide production bundler failures."""

    body = _target_body("test-frontend-h5p")

    assert "npm run build" in body
    assert body.index("npm run check") < body.index("npm run build")


def test_verify_keeps_external_smokes_out_of_default_gate() -> None:
    """`verify` should stay deterministic; external smokes live in full-prod-like."""

    body = _target_body("verify")

    assert "$(MAKE) test-docker-image-smoke" in body
    assert "$(MAKE) test-frontend-h5p" in body
    assert "$(MAKE) test-supabase" not in body
    assert "$(MAKE) test-openai" not in body
    assert "$(MAKE) test-e2e" not in body


def test_full_prod_like_runs_external_integration_smokes() -> None:
    """The opt-in prod-like profile owns expensive service and LLM checks."""

    body = _target_body("test-full-prod-like")

    assert "$(MAKE) verify-feature" in body
    assert "$(MAKE) test-supabase" in body
    assert "$(MAKE) test-openai" in body
    assert "$(MAKE) test-e2e" in body
    assert "$(MAKE) dependency-audit" in body


def test_quality_scorecard_runs_docker_image_smoke_by_default() -> None:
    """The monthly scorecard should not leave image parity as an unrun follow-up."""

    body = _target_body("quality-scorecard")

    assert "--run-docker-check" in body


def test_backend_lint_target_is_part_of_verify() -> None:
    """Closeout v1.1 makes the low-noise Ruff baseline a hard verify gate."""

    help_text = MAKEFILE.read_text(encoding="utf-8")
    lint_body = _target_body("lint-backend")
    verify_body = _target_body("verify")

    assert "lint-backend" in help_text
    assert "backend/requirements-harness.txt" in lint_body
    assert "python -m ruff check backend --select F" in lint_body
    assert "--exclude 'backend/tests/*'" not in lint_body
    assert "--exclude 'backend/tests_e2e/*'" not in lint_body
    assert "python -m ruff format --check backend" not in lint_body
    assert "$(MAKE) lint-backend" in verify_body


def test_supply_chain_check_is_part_of_verify() -> None:
    """Closeout v1.2 makes offline dependency/license inventory a hard gate."""

    help_text = MAKEFILE.read_text(encoding="utf-8")
    supply_body = _target_body("supply-chain-check")
    verify_body = _target_body("verify")

    assert "supply-chain-check" in help_text
    assert "backend.tools.supply_chain_check" in supply_body
    assert "--check" in supply_body
    assert "$(MAKE) supply-chain-check" in verify_body


def test_visual_smoke_target_is_full_prod_like_not_default_verify() -> None:
    """Visual smoke tests are valuable but should stay outside deterministic verify."""

    help_text = MAKEFILE.read_text(encoding="utf-8")
    visual_body = _target_body("test-visual-smoke")
    update_body = _target_body("update-visual-baselines")
    full_prod_body = _target_body("test-full-prod-like")
    verify_body = _target_body("verify")

    assert "test-visual-smoke" in help_text
    assert "update-visual-baselines" in help_text
    assert "npm run test:e2e" in visual_body
    assert "@design-system" in update_body
    assert "--update-snapshots" in update_body
    assert "$(MAKE) test-visual-smoke" in full_prod_body
    assert "$(MAKE) test-visual-smoke" not in verify_body


def test_backend_lint_target_uses_central_ruff_configuration() -> None:
    """Ruff should be configured centrally so agents do not invent local style."""

    config = PYPROJECT.read_text(encoding="utf-8")

    assert "[tool.ruff]" in config
    assert 'target-version = "py311"' in config
    assert 'line-length = 100' in config
    assert "[tool.ruff.lint]" in config
    assert '"E"' in config
    assert '"F"' in config
    assert '"I"' in config

    backend_requirements = BACKEND_REQUIREMENTS.read_text(encoding="utf-8")
    harness_requirements = BACKEND_HARNESS_REQUIREMENTS.read_text(encoding="utf-8")
    assert "ruff" not in backend_requirements
    assert "-r web/requirements.txt" in harness_requirements
    assert "ruff" in harness_requirements


def test_runtime_requirements_do_not_include_harness_only_tools() -> None:
    """The production image installs runtime dependencies, not local harness tools."""

    backend_requirements = BACKEND_REQUIREMENTS.read_text(encoding="utf-8")
    harness_requirements = BACKEND_HARNESS_REQUIREMENTS.read_text(encoding="utf-8")

    assert "ruff" not in backend_requirements
    assert "-r web/requirements.txt" in harness_requirements
    assert "ruff==" in harness_requirements


def test_frontend_vitest_uses_numeric_loopback_host() -> None:
    """Frontend unit tests should not depend on localhost DNS resolution."""

    config = FRONTEND_VITEST_CONFIG.read_text(encoding="utf-8")

    assert 'host: "127.0.0.1"' in config
