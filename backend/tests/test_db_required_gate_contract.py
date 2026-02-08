"""
DB gate contract for DB-backed tests.

Why:
    DB-backed suites currently use `require_db_or_skip()`. For release gates we
    must be able to fail hard instead of silently skipping when the DB is down.
"""

from __future__ import annotations

import sys
import types

import pytest

from backend.tests.utils import db as db_utils


class _FailingPsycopg(types.SimpleNamespace):
    def connect(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("db_unreachable")


def test_require_db_or_skip_can_fail_hard_when_release_gate_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_DB_TESTS", "1")
    monkeypatch.setitem(sys.modules, "psycopg", _FailingPsycopg())

    with pytest.raises(pytest.fail.Exception):
        db_utils.require_db_or_skip()


def test_require_db_or_skip_still_skips_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REQUIRE_DB_TESTS", raising=False)
    monkeypatch.setitem(sys.modules, "psycopg", _FailingPsycopg())

    with pytest.raises(pytest.skip.Exception):
        db_utils.require_db_or_skip()
