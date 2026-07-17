from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = PROJECT_ROOT / "Makefile"
SMOKE_SCRIPT = PROJECT_ROOT / "backend/tools/docker_image_smoke.py"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_makefile_exposes_docker_image_only_smoke_target() -> None:
    """PR 5 needs a stable local entry point for image-only packaging checks."""

    body = _target_body("test-docker-image-smoke")

    assert "python -m backend.tools.docker_image_smoke" in body
    assert "docker compose up" not in body


def test_harness_signals_runs_image_only_smoke_as_warning_signal() -> None:
    """Image-only packaging failures should be visible before they become hard."""

    body = _target_body("harness-signals")

    assert "docker_image_smoke" in body
    assert "test-docker-image-smoke" not in body


def test_docker_image_smoke_script_checks_imports_without_volume_mounts() -> None:
    """The smoke must prove the image itself contains required modules."""

    assert SMOKE_SCRIPT.exists(), "Missing Docker image smoke script"
    text = SMOKE_SCRIPT.read_text(encoding="utf-8")

    for required_import in (
        "backend.web.main",
        "backend.learning",
        "backend.vision",
        "backend.storage",
        "backend.scratch",
        "backend.makecode",
        "backend.filius",
    ):
        assert required_import in text

    assert '"docker", "build"' in text
    assert '"docker", "run"' in text
    assert "/health" in text
    assert "/app/identity_access" in text
    assert "/app/teaching" in text
    assert "--volume" not in text
    assert " -v " not in text


def test_docker_image_smoke_no_longer_imports_flat_main() -> None:
    """PR 8 makes the package-oriented app module the image-smoke entry point."""

    text = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert '"main"' not in text
    assert "backend.web.main" in text


def test_docker_image_smoke_uses_prod_like_runtime_configuration() -> None:
    """The image smoke should exercise the same startup guard path as production."""

    text = SMOKE_SCRIPT.read_text(encoding="utf-8")

    for required in (
        "GUSTAV_ENABLE_DOTENV=false",
        "GUSTAV_ENV=prod",
        "SESSIONS_BACKEND=db",
        "CLI_TOKENS_BACKEND=db",
        "SUPABASE_SERVICE_ROLE_KEY=REAL_NON_DUMMY",
        "KC_ADMIN_CLIENT_SECRET=REAL_ADMIN_SECRET",
        "BFF_INTERNAL_SHARED_SECRET=real-bff-secret",
        "H5P_REVIEW_TOKEN_SECRET=real-h5p-review-secret",
        "H5P_INTERNAL_SHARED_SECRET=real-h5p-internal-secret",
        "APP_CSRF_TOKEN_SECRET=real-csrf-secret",
        "REQUIRE_STORAGE_VERIFY=true",
        "ENABLE_DEV_UPLOAD_STUB=false",
        "ENABLE_STORAGE_UPLOAD_PROXY=false",
        "AUTO_CREATE_STORAGE_BUCKETS=false",
        "KC_PUBLIC_BASE_URL=https://id.example.com",
        "DATABASE_URL=postgresql://gustav_app_login:",
        "TEACHING_DATABASE_URL=postgresql://gustav_app_login:",
        "LEARNING_DATABASE_URL=postgresql://gustav_app_login:",
        "SESSION_DATABASE_URL=postgresql://gustav_session_login:",
        "sslmode=require",
    ):
        assert required in text

    assert "GUSTAV_ENV=dev" not in text
    assert "SESSIONS_BACKEND=memory" not in text


def test_docker_image_smoke_expects_fail_closed_readiness_without_database() -> None:
    """The isolated image has an unreachable DSN and must therefore report 503."""

    text = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "HTTPError" in text
    assert "response.status == 503" in text
    assert "readiness-unavailable-ok" in text


def test_docker_image_smoke_rejects_runtime_test_and_tooling_leaks() -> None:
    """Runtime images must not ship tests, harness tooling, or Ruff."""

    text = SMOKE_SCRIPT.read_text(encoding="utf-8")

    for forbidden_path in (
        "/app/backend/tests",
        "/app/backend/tests_e2e",
        "/app/backend/tools",
    ):
        assert forbidden_path in text

    assert "find_spec('ruff')" in text or 'find_spec("ruff")' in text
    assert "runtime-deps-ok" in text


def test_verify_runs_docker_image_only_smoke_as_hard_gate() -> None:
    """PR 8 makes image-only packaging parity part of full verification."""

    body = _target_body("verify")

    assert "$(MAKE) test-docker-image-smoke" in body
