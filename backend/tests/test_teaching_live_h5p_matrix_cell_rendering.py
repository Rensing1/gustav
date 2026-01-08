"""
SSR — Teaching Live matrix cell rendering (H5P)

These unit tests validate the pure HTML rendering logic for the live matrix
cells without requiring a running DB.

Why:
    H5P tasks are auto-scorable and should be shown as a simple 3-state signal
    in the Live-Unterrichts-Matrix:
      - — no submission
      - • attempted/bearbeitet
      - ✓ completed/abgeschlossen (full score at least once)
"""
from __future__ import annotations

import os
from pathlib import Path


def _import_web_main():
    repo_root = Path(__file__).resolve().parents[2]
    web_dir = repo_root / "backend" / "web"
    if str(web_dir) not in os.sys.path:
        os.sys.path.insert(0, str(web_dir))
    # Avoid requiring a working DB DSN during import of the web app module.
    os.environ.setdefault("ALLOW_SERVICE_DSN_FOR_TESTING", "true")
    import main  # type: ignore

    return main


def test_h5p_cell_symbols():
    main = _import_web_main()

    # No submission
    assert (
        main._render_live_cell_content(  # type: ignore[attr-defined]
            task_kind="h5p",
            has_submission=False,
            average_score=None,
            h5p_completed=None,
        )
        == "—"
    )

    # Attempted
    attempted = main._render_live_cell_content(  # type: ignore[attr-defined]
        task_kind="h5p",
        has_submission=True,
        average_score=None,
        h5p_completed=False,
    )
    assert "•" in attempted

    # Completed
    completed = main._render_live_cell_content(  # type: ignore[attr-defined]
        task_kind="h5p",
        has_submission=True,
        average_score=None,
        h5p_completed=True,
    )
    assert "✓" in completed


def test_non_h5p_cells_keep_existing_badge_and_checkmark_behavior():
    main = _import_web_main()

    # Native/visual without analysis → ✅/—
    assert (
        main._render_live_cell_content(  # type: ignore[attr-defined]
            task_kind="native",
            has_submission=True,
            average_score=None,
            h5p_completed=None,
        )
        == "✅"
    )
    assert (
        main._render_live_cell_content(  # type: ignore[attr-defined]
            task_kind="native",
            has_submission=False,
            average_score=None,
            h5p_completed=None,
        )
        == "—"
    )

    # Native/visual with analysis score → badge
    badge = main._render_live_cell_content(  # type: ignore[attr-defined]
        task_kind="native",
        has_submission=True,
        average_score=8.0,
        h5p_completed=None,
    )
    assert "badge" in badge

