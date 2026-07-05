"""Contracts for the DB/RLS test inventory.

Why:
    The harness plan asks for a direct DB-access inventory before `db_read`
    and `db_write` become hard policy markers. This contract keeps that
    inventory generated and reviewable without silently turning marker cleanup
    into a broad test-suite rewrite.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
INVENTORY = REPO_ROOT / "docs" / "harness" / "DB_TEST_INVENTORY.md"
TOOL = REPO_ROOT / "backend" / "tools" / "db_test_inventory.py"


def _target_body(target: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^\.PHONY: {re.escape(target)}\n{re.escape(target)}:\n(?P<body>.*?)(?=^\.PHONY: |\Z)",
        text,
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group("body")


def test_makefile_exposes_db_test_inventory_gate() -> None:
    body = _target_body("test-db-inventory")

    assert "python -m backend.tools.db_test_inventory" in body
    assert "--check docs/harness/DB_TEST_INVENTORY.md" in body


def test_verify_runs_db_test_inventory_gate() -> None:
    body = _target_body("verify")

    assert "$(MAKE) test-db-inventory" in body


def test_db_test_inventory_classifies_real_db_candidates(tmp_path: Path) -> None:
    from backend.tools import db_test_inventory

    db_test = tmp_path / "test_learning_rls_policy.py"
    db_test.write_text(
        "\n".join(
            [
                "import os",
                "import pytest",
                "pytest.importorskip('psycopg')",
                "",
                "def test_student_rls_policy():",
                "    dsn = os.getenv('RLS_TEST_DSN')",
                "    import psycopg",
                "    with psycopg.connect(dsn):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )
    fake_storage_test = tmp_path / "test_supabase_storage_adapter.py"
    fake_storage_test.write_text(
        "\n".join(
            [
                "def test_fake_supabase_storage(monkeypatch):",
                "    monkeypatch.setenv('SUPABASE_URL', 'https://supabase.local')",
                "    assert True",
            ]
        ),
        encoding="utf-8",
    )
    opt_in_db_test = tmp_path / "test_legacy_migration_import.py"
    opt_in_db_test.write_text(
        "\n".join(
            [
                "import pytest",
                "pytestmark = pytest.mark.legacy_migration",
                "",
                "def test_legacy_import_uses_real_db():",
                "    import psycopg",
                "    with psycopg.connect('postgresql://example.invalid/postgres'):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )

    records = db_test_inventory.scan_tests(tmp_path, repo_root=tmp_path)
    rows = {record.path: record for record in records}

    assert rows["test_learning_rls_policy.py"].classification == "real-db"
    assert "missing-db-marker" in rows["test_learning_rls_policy.py"].marker_status
    assert "rls" in rows["test_learning_rls_policy.py"].signals
    assert "psycopg-connect" in rows["test_learning_rls_policy.py"].signals
    assert rows["test_supabase_storage_adapter.py"].classification == "storage-or-config"
    assert rows["test_supabase_storage_adapter.py"].marker_status == "no-db-marker-needed"
    assert rows["test_legacy_migration_import.py"].classification == "real-db"
    assert rows["test_legacy_migration_import.py"].marker_status == "covered-by-opt-in-marker"
    assert rows["test_legacy_migration_import.py"].recommended_action == "Keep existing opt-in gate"


def test_db_test_inventory_ignores_embedded_fixture_source_strings(tmp_path: Path) -> None:
    from backend.tools import db_test_inventory

    scanner_contract = tmp_path / "test_scanner_contract.py"
    scanner_contract.write_text(
        "\n".join(
            [
                "def test_scanner_fixture(tmp_path):",
                "    fake_test = tmp_path / 'test_fake.py'",
                "    fake_test.write_text(\"pytestmark = pytest.mark.legacy_migration\")",
                "    fake_test.write_text(\"with psycopg.connect('postgresql://example.invalid/postgres'): pass\")",
                "    fake_test.write_text(\"os.getenv('RLS_TEST_DSN')\")",
            ]
        ),
        encoding="utf-8",
    )

    records = db_test_inventory.scan_tests(tmp_path, repo_root=tmp_path)

    assert [record.path for record in records] == []


def test_db_test_inventory_does_not_treat_rls_name_as_real_db_alone(tmp_path: Path) -> None:
    from backend.tools import db_test_inventory

    docs_only_test = tmp_path / "test_rls_docs_contract.py"
    docs_only_test.write_text(
        "\n".join(
            [
                "def test_rls_policy_is_documented():",
                "    assert 'RLS' == 'RLS'",
            ]
        ),
        encoding="utf-8",
    )

    records = db_test_inventory.scan_tests(tmp_path, repo_root=tmp_path)

    assert records == []


def test_db_test_inventory_ignores_monkeypatch_env_only_contracts(tmp_path: Path) -> None:
    from backend.tools import db_test_inventory

    fake_contract = tmp_path / "test_verify_db_preflight.py"
    fake_contract.write_text(
        "\n".join(
            [
                "def test_build_dsn_prefers_database_url(monkeypatch):",
                "    monkeypatch.setenv('DATABASE_URL', 'postgresql://x:y@db.local:5432/app')",
                "    assert True",
            ]
        ),
        encoding="utf-8",
    )

    records = db_test_inventory.scan_tests(tmp_path, repo_root=tmp_path)

    assert records == []


def test_db_test_inventory_does_not_treat_psycopg_dependency_as_real_db_alone(tmp_path: Path) -> None:
    from backend.tools import db_test_inventory

    dependency_only_test = tmp_path / "test_local_vision.py"
    dependency_only_test.write_text(
        "\n".join(
            [
                "import pytest",
                "pytest.importorskip('psycopg')",
                "",
                "def test_uses_adapter_with_fake_storage():",
                "    assert True",
            ]
        ),
        encoding="utf-8",
    )

    records = db_test_inventory.scan_tests(tmp_path, repo_root=tmp_path)

    assert records == []


def test_db_test_inventory_document_has_required_columns() -> None:
    assert TOOL.exists(), "Missing DB test inventory tool"
    assert INVENTORY.exists(), "Missing DB test inventory document"
    text = INVENTORY.read_text(encoding="utf-8")

    for column in (
        "Test file",
        "Classification",
        "Markers",
        "Marker status",
        "Signals",
        "Recommended action",
    ):
        assert column in text

    assert "db_read" in text
    assert "db_write" in text


def test_db_security_rls_files_are_marked_as_db_write() -> None:
    from backend.tools import db_test_inventory

    records = {
        record.path: record
        for record in db_test_inventory.scan_tests(REPO_ROOT / "backend" / "tests", repo_root=REPO_ROOT)
    }

    for path in (
        "backend/tests/test_learning_student_rls_policies.py",
        "backend/tests/test_learning_rls_owners.py",
        "backend/tests/test_teaching_rls_policies_optional.py",
        "backend/tests/test_teaching_memberships_delete_rls_policy.py",
        "backend/tests/migration/test_course_memberships_rls_delete_policy.py",
        "backend/tests/migration/test_memberships_remove_definer_owner_binding.py",
        "backend/tests/migration/test_rls_exec_privileges.py",
    ):
        assert records[path].marker_status == "marked-db"
        assert "db_write" in records[path].markers


def test_migration_metadata_contracts_are_marked_as_db_read() -> None:
    from backend.tools import db_test_inventory

    records = {
        record.path: record
        for record in db_test_inventory.scan_tests(REPO_ROOT / "backend" / "tests", repo_root=REPO_ROOT)
    }

    for path in (
        "backend/tests/migration/test_ai_usage_events_security.py",
        "backend/tests/migration/test_concern_box_entries_rls.py",
        "backend/tests/migration/test_learning_material_visibility_batch_helper_contract.py",
        "backend/tests/migration/test_modular_edge_validator_exec_privileges.py",
        "backend/tests/migration/test_modular_unlock_helper_no_edge_n_plus_one.py",
        "backend/tests/migration/test_unit_module_edges_update_hardening.py",
    ):
        assert records[path].marker_status == "marked-db"
        assert "db_read" in records[path].markers


def test_security_definer_helper_hardening_contracts_are_marked_as_db_read() -> None:
    from backend.tools import db_test_inventory

    records = {
        record.path: record
        for record in db_test_inventory.scan_tests(REPO_ROOT / "backend" / "tests", repo_root=REPO_ROOT)
    }

    for path in (
        "backend/tests/migration/test_teaching_latest_submission_owner_helper_hardening.py",
        "backend/tests/migration/test_teaching_live_unit_summary_helper_hardening.py",
    ):
        assert records[path].marker_status == "marked-db"
        assert "db_read" in records[path].markers


def test_learning_worker_db_integration_files_are_marked_as_db_write() -> None:
    from backend.tools import db_test_inventory

    records = {
        record.path: record
        for record in db_test_inventory.scan_tests(REPO_ROOT / "backend" / "tests", repo_root=REPO_ROOT)
    }

    for path in (
        "backend/tests/learning_adapters/test_learning_worker_dspy_only_placeholder.py",
        "backend/tests/test_learning_worker_e2e_local.py",
        "backend/tests/test_learning_worker_error_codes.py",
        "backend/tests/test_learning_worker_jobs.py",
        "backend/tests/test_learning_worker_pdf_extracted_flow.py",
        "backend/tests/test_learning_worker_privacy_logs.py",
        "backend/tests/test_learning_worker_security.py",
        "backend/tests/test_learning_worker_task_context.py",
        "backend/tests/test_learning_worker_text_bypass_vision.py",
        "backend/tests/test_learning_worker_transaction_boundaries.py",
        "backend/tests/test_learning_worker_visual_dspy_pipeline.py",
    ):
        assert records[path].marker_status == "marked-db"
        assert "db_write" in records[path].markers


def test_db_test_inventory_is_synchronized_with_generator() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.tools.db_test_inventory",
            "--check",
            "docs/harness/DB_TEST_INVENTORY.md",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "db-test-inventory-ok" in result.stdout
    assert result.stderr == ""
