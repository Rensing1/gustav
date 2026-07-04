"""Unit-level tests for Teaching Live delta helpers.

These tests focus on the timestamp normalisation helper used by the
SSR delta fragment to derive a monotonic polling cursor.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.web.ssr_helpers import normalize_changed_at_to_utc


def test_normalize_changed_at_accepts_z_suffix():
    raw = "2025-01-02T03:04:05.123456Z"
    dt = normalize_changed_at_to_utc(raw)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2025 and dt.minute == 4


def test_normalize_changed_at_accepts_explicit_utc_offset():
    raw = "2025-01-02T03:04:05.123456+00:00"
    dt = normalize_changed_at_to_utc(raw)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    # Same instant as the input; we only care that it stays in UTC.
    assert dt.hour == 3 and dt.second == 5


def test_normalize_changed_at_assumes_utc_for_naive_timestamps():
    naive = datetime(2025, 1, 2, 3, 4, 5, 123456)
    raw = naive.isoformat()
    dt = normalize_changed_at_to_utc(raw)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == naive.year and dt.month == naive.month


def test_normalize_changed_at_returns_none_for_invalid_input():
    assert normalize_changed_at_to_utc("not-a-timestamp") is None
    assert normalize_changed_at_to_utc("") is None
