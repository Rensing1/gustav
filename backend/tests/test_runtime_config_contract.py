"""Contracts for small web runtime configuration helpers."""

from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_SOURCE = PROJECT_ROOT / "backend" / "web" / "main.py"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, 3),
        ("", 3),
        ("not-a-number", 3),
        ("0", 1),
        ("-5", 1),
        ("61", 60),
        ("15", 15),
    ],
)
def test_teaching_live_poll_interval_is_loaded_and_clamped(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str | None,
    expected: int,
) -> None:
    from backend.web.runtime_config import load_teaching_live_poll_interval_seconds

    if raw_value is None:
        monkeypatch.delenv("GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS", raising=False)
    else:
        monkeypatch.setenv("GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS", raw_value)

    assert load_teaching_live_poll_interval_seconds() == expected


def test_main_delegates_teaching_live_poll_interval_to_runtime_config() -> None:
    source = MAIN_SOURCE.read_text(encoding="utf-8")

    assert "load_teaching_live_poll_interval_seconds()" in source
    assert "def _load_poll_interval_from_env" not in source
    assert "GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS" not in source
