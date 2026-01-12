"""
Privacy/logging contract tests (source-level).

Why:
    - Session IDs are bearer tokens and must not end up in CI/test logs.
    - `print()` statements in request code paths are hard to filter and can
      leak sensitive context to stdout.
    - Debug logs should not emit raw student pseudonyms (`student_sub`).

Note:
    These are cheap source-level guardrails; they do not execute the web app.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_ssr_does_not_log_raw_session_id_marker() -> None:
    src = (_repo_root() / "backend" / "web" / "main.py").read_text(encoding="utf-8")
    assert "__SSR_DEBUG_SID__" not in src


def test_teaching_delta_debug_has_no_print_and_no_raw_student_sub_in_logs() -> None:
    src = (_repo_root() / "backend" / "web" / "routes" / "teaching.py").read_text(encoding="utf-8")
    assert "print(" not in src

    start = src.find('"delta-cell"')
    assert start != -1, "Expected delta debug log marker 'delta-cell' in teaching routes"
    end = src.find("# Include changes after", start)
    assert end != -1, "Expected delta debug block terminator comment in teaching routes"

    block = src[start:end]
    assert '"student_sub": student_sub' not in block

