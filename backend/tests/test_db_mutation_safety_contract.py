"""Static guardrails for DB-mutating tests.

Why:
    DB-backed tests may run against a shared real database.  Default pytest
    runs must never clear shared application tables.  One-off legacy import
    tests are allowed to keep their historical cleanup SQL only when they are
    explicitly marked and gated out of the default suite.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_worker_tests_do_not_delete_the_global_learning_queue() -> None:
    offenders: list[str] = []
    global_queue_delete = re.compile(
        r"delete\s+from\s+public\.learning_submission_jobs\s*(?:;|\"\"\"|'''|\"|')",
        re.IGNORECASE,
    )
    for path in (ROOT / "backend" / "tests").rglob("test_learning_worker*.py"):
        text = path.read_text(encoding="utf-8")
        if global_queue_delete.search(text):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_global_public_table_truncates_are_legacy_migration_only() -> None:
    offenders: list[str] = []
    destructive_public_truncate = re.compile(
        r"truncate\s+table\s+public\.",
        re.IGNORECASE,
    )

    for path in (ROOT / "backend" / "tests").rglob("test*.py"):
        text = path.read_text(encoding="utf-8")
        if not destructive_public_truncate.search(text):
            continue
        if "pytest.mark.legacy_migration" in text:
            continue
        offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_historical_legacy_import_tests_are_marked_legacy_migration() -> None:
    offenders: list[str] = []
    migration_dir = ROOT / "backend" / "tests" / "migration"
    candidates = [
        *migration_dir.glob("test_legacy_migration_*.py"),
        *migration_dir.glob("test_sub_mapping_sync*.py"),
    ]

    for path in sorted(candidates):
        text = path.read_text(encoding="utf-8")
        if "pytest.mark.legacy_migration" not in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
