"""Contracts for small SSR helper functions."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from backend.web.ssr_helpers import (
    build_url_with_query,
    clamp_pagination,
    generate_task_submit_idempotency_key,
    hx_vals_attr_payload,
    is_analysis_in_progress,
    normalize_changed_at_to_utc,
    normalize_open_attempt_id_uuid,
    normalize_task_submit_idempotency_key,
    quote_url_path_value,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_url_helpers_quote_path_segments_and_query_values() -> None:
    """SSR-generated links must not leak raw user-controlled values."""

    assert quote_url_path_value("a/b c") == "a%2Fb%20c"
    assert build_url_with_query("/path", {"q": "a b", "empty": None, "page": 2}) == "/path?q=a+b&page=2"
    assert build_url_with_query("/path", {"empty": None}) == "/path"


def test_normalize_changed_at_accepts_z_offsets_and_naive_utc() -> None:
    """Delta polling cursors are normalized to timezone-aware UTC datetimes."""

    zulu = normalize_changed_at_to_utc("2025-01-02T03:04:05.123456Z")
    explicit = normalize_changed_at_to_utc("2025-01-02T03:04:05.123456+00:00")
    naive = normalize_changed_at_to_utc(datetime(2025, 1, 2, 3, 4, 5, 123456).isoformat())

    assert zulu is not None and zulu.tzinfo == timezone.utc
    assert explicit is not None and explicit.hour == 3 and explicit.tzinfo == timezone.utc
    assert naive is not None and naive.tzinfo == timezone.utc
    assert normalize_changed_at_to_utc("not-a-timestamp") is None


def test_pagination_and_open_attempt_helpers_are_defensive() -> None:
    """Client-controlled pagination and IDs are clamped or dropped."""

    assert clamp_pagination(None, None) == (20, 0)
    assert clamp_pagination("999", "-5") == (50, 0)
    assert clamp_pagination("bad", "bad") == (20, 0)

    valid_uuid = "11111111-1111-1111-1111-111111111111"
    assert normalize_open_attempt_id_uuid(f" {valid_uuid} ") == valid_uuid
    assert normalize_open_attempt_id_uuid("not-a-uuid") == ""


def test_hx_and_submission_helpers_preserve_existing_contracts() -> None:
    """HTMX payloads and idempotency keys stay HTML-safe and bounded."""

    assert hx_vals_attr_payload({"text": "<tag>&"}) == "{&quot;text&quot;:&quot;&lt;tag&gt;&amp;&quot;}"
    assert is_analysis_in_progress("pending")
    assert is_analysis_in_progress("EXTRACTED")
    assert not is_analysis_in_progress("completed")

    generated = generate_task_submit_idempotency_key()
    assert re.fullmatch(r"ui-[0-9a-f]{16}", generated)
    assert normalize_task_submit_idempotency_key("abc_123-OK") == "abc_123-OK"
    assert re.fullmatch(r"ui-[0-9a-f]{16}", normalize_task_submit_idempotency_key("../bad value"))


def test_main_delegates_small_ssr_helpers_to_dedicated_module() -> None:
    """The app entry module should not own generic SSR utility helpers."""

    main_source = (REPO_ROOT / "backend/web/main.py").read_text(encoding="utf-8")
    rendering_source = (REPO_ROOT / "backend/web/submission_history_rendering.py").read_text(encoding="utf-8")

    for retired_helper in (
        "def _quote_url_path_value",
        "def _build_url_with_query",
        "def _normalize_changed_at_to_utc",
        "def _clamp_pagination",
        "def _is_uuid_like",
        "def _normalize_open_attempt_id_uuid",
        "def _hx_vals_attr_payload",
        "def _is_analysis_in_progress",
        "def _generate_task_submit_idempotency_key",
        "def _normalize_task_submit_idempotency_key",
    ):
        assert retired_helper not in main_source

    assert "from backend.web.ssr_helpers import" not in main_source
    assert "is_analysis_in_progress(" not in main_source
    assert "from backend.web.ssr_helpers import is_analysis_in_progress" in rendering_source
    assert "is_analysis_in_progress(" in rendering_source
