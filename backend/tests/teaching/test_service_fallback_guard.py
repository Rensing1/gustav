"""
Unit tests for the service-DSN fallback guard.

Why:
    The membership removal contains a guarded fallback to a service-role DSN
    for developer convenience in tests/dev. This test verifies the guard's
    environment logic without touching the database.
"""
from __future__ import annotations

import os
import pytest


@pytest.mark.parametrize(
    "env,flag,pytest_flag,expected",
    [
        ("", "", "", False),
        ("prod", "true", "", False),
        ("production", "true", "", False),
        ("dev", "true", "", True),
        ("test", "true", "", True),
        ("local", "true", "", True),
        ("", "true", "yes", True),  # heuristically allow when running under pytest
    ],
)
def test_service_fallback_allowed_matrix(monkeypatch: pytest.MonkeyPatch, env: str, flag: str, pytest_flag: str, expected: bool) -> None:
    # Late import to avoid affecting global state outside test
    from backend.teaching.repo_db import DBTeachingRepo  # type: ignore

    monkeypatch.setenv("GUSTAV_ENV", env)
    if flag:
        monkeypatch.setenv("ALLOW_SERVICE_DSN_FOR_TESTING", flag)
    else:
        try:
            monkeypatch.delenv("ALLOW_SERVICE_DSN_FOR_TESTING")
        except Exception:
            pass
    if pytest_flag:
        monkeypatch.setenv("PYTEST_CURRENT_TEST", pytest_flag)
    else:
        try:
            monkeypatch.delenv("PYTEST_CURRENT_TEST")
        except Exception:
            pass

    assert DBTeachingRepo._service_fallback_allowed() is expected
