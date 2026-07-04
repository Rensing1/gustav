"""Contracts for retired Teaching-Live SSR matrix cell rendering.

The old FastAPI HTML matrix routes are retired. H5P score fields are now
protected by the Live API/OpenAPI contracts and rendered in the Svelte surface,
so the backend entrypoint must not keep an unused HTML cell renderer.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_main_does_not_keep_retired_live_matrix_cell_renderers() -> None:
    """Retired Teaching-Live SSR matrix helpers must not remain in main.py."""

    source = (REPO_ROOT / "backend/web/main.py").read_text(encoding="utf-8")

    assert "def _live_score_badge_variant" not in source
    assert "def _render_live_average_score_badge" not in source
    assert "def _render_live_cell_content" not in source


def test_active_live_surfaces_still_expose_h5p_score_fields() -> None:
    """The active Live API and Svelte surface still carry H5P score fields."""

    app_route = (REPO_ROOT / "backend/web/routes/app.py").read_text(encoding="utf-8")
    live_page = (REPO_ROOT / "frontend/src/routes/live/+page.svelte").read_text(encoding="utf-8")

    for field in ("score_raw", "score_max", "h5p_completed"):
        assert field in app_route
    assert "score_raw" in live_page
    assert "score_max" in live_page
