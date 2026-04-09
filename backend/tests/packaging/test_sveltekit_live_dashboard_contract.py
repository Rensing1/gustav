"""Contract tests for the canonical SvelteKit live dashboard page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_live_page_uses_dashboard_read_model() -> None:
    live_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.server.ts"
    live_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.svelte"

    for path in (live_loader_path, live_page_path):
        assert path.is_file(), f"Missing live dashboard page: {path}"

    loader_source = live_loader_path.read_text(encoding="utf-8")
    page_source = live_page_path.read_text(encoding="utf-8")

    assert "/api/live/views/courses/" in loader_source
    assert "/units" in loader_source
    assert "/dashboard" in loader_source
    assert "/api/teaching/views/courses/" not in loader_source
    assert "course_id" in loader_source
    assert "unit_id" in loader_source
    assert "task_id" in loader_source
    assert "wideWorkspaceShell: true" in loader_source
    assert "selected_student_panel" in page_source
    assert "live-kpi-section" in page_source
    assert "workspace-data-table" in page_source
    assert "workspace-section-header" in page_source
    assert "workspace-label" in page_source
    assert "workspace-tab" in page_source
    assert "goto(" in page_source
    assert 'onchange={(event)' in page_source
    assert 'type="submit"' not in page_source
    assert "live-selection__stack" in page_source
    assert '<section class="workspace-panel workspace-section">\n    {#if data.courses.length}' not in page_source
    assert "workspace-panel workspace-panel--plain workspace-section live-selection-bar" in page_source
    assert 'name="unit_id"' in page_source
    assert "live-selection__unit-chip" not in page_source
    assert "LearningSubmissionArtifactView" in page_source
    assert "renderMarkdown" in page_source
    assert 'role="tablist"' in page_source
    assert "selected_task_detail" in page_source
    assert "selected_task_id" in page_source
    assert "score-zero" in page_source
    assert "submitted-unscored" in page_source
    assert "<pre>{data.dashboard.selected_student_panel" not in page_source
