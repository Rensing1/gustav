"""Static guardrails for DB-mutating tests.

Why:
    DB-backed tests may run against a shared real database.  Worker tests must
    not clear global queues; legacy migration tests are excluded here because
    they are being moved to explicit batch-scoped behaviour separately.
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
