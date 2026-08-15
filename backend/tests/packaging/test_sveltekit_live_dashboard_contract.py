"""Contract tests for the canonical SvelteKit live dashboard page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_live_page_uses_summary_and_detail_read_models() -> None:
    live_loader_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.server.ts"
    live_page_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "+page.svelte"
    live_state_path = REPO_ROOT / "frontend" / "src" / "routes" / "live" / "page-state.ts"

    for path in (live_loader_path, live_page_path, live_state_path):
        assert path.is_file(), f"Missing live dashboard page: {path}"

    loader_source = live_loader_path.read_text(encoding="utf-8")
    page_source = live_page_path.read_text(encoding="utf-8")
    helper_source = live_state_path.read_text(encoding="utf-8")

    assert "/api/live/views/courses/" in loader_source
    assert "/units" in loader_source
    assert "/detail-sheet" in loader_source
    assert "/api/teaching/courses/" in loader_source
    assert "/submissions/summary" in loader_source
    assert "/dashboard" not in loader_source
    assert "/api/teaching/views/courses/" not in loader_source
    assert "course_id" in loader_source
    assert "unit_id" in loader_source
    assert "task_id" in loader_source
    assert 'workspaceLayout: "canvas"' in loader_source
    assert "wideWorkspaceShell" not in loader_source
    assert "liveWideWorkspaceShell" not in loader_source
    assert "selected_student_panel" in page_source
    assert "live-kpi-section" in page_source
    assert "live-workspace" in page_source
    assert "live-page__intro" in page_source
    assert "live-page__workspace" in page_source
    assert "live-table-panel" in page_source
    assert "workspace-data-table" in page_source
    assert "workspace-section-header" in page_source
    assert "workspace-label" in page_source
    assert "workspace-tab" in page_source
    assert 'aria-sort=' in page_source
    assert "toggleSort(" in page_source
    assert "sortedRows" in page_source
    assert "goto(" in page_source
    assert 'onchange={(event)' in page_source
    assert 'type="submit"' not in page_source
    assert "window.history.replaceState" in page_source
    assert "livePollIntervalSeconds" in page_source
    assert "liveCursorSeed" in page_source
    assert "setInterval(" in page_source or "window.setInterval(" in page_source
    assert "clearInterval(" in page_source or "window.clearInterval(" in page_source
    assert "preventDefault" in page_source
    assert "/live/courses/" in helper_source
    assert "/summary" in helper_source
    assert "/detail-sheet" in helper_source
    assert "/submissions/delta" in helper_source
    assert "/api/live/views/courses/" not in helper_source
    assert "live-selection__stack" in page_source
    assert '<section class="workspace-panel workspace-section">\n    {#if data.courses.length}' not in page_source
    assert "live-workspace-breakout" not in page_source
    assert "live-workspace-section" not in page_source
    assert "workspace-panel workspace-panel--plain workspace-section live-selection-bar" in page_source
    assert 'name="unit_id"' in page_source
    assert "live-selection__unit-chip" not in page_source
    assert "LearningSubmissionArtifactView" in page_source
    assert "buildSubmissionArtifactView" in page_source
    assert "renderMarkdown" in page_source
    assert 'role="tablist"' in page_source
    assert "selected_task_detail" in page_source
    assert "selectedTaskIdState" in page_source
    assert "score-zero" in page_source
    assert "submitted-unscored" in page_source
    assert "<pre>{data.dashboard.selected_student_panel" not in page_source
    assert "Detailpanel" not in page_source
    assert "Aufgabe wählen, dann zwischen Abgabe, Bewertung und Rückmeldung wechseln." not in page_source
    assert "Ausgewählte Aufgabe" not in page_source
    assert "Aufgabe als Referenz" not in page_source
    assert "formatSubmissionTimestamp" in page_source
    assert "stripSubmissionSchemaHeader" in page_source
    assert "isSubmissionSchemaPayload" in page_source
    assert "ab " in page_source
    assert "Uhr" in page_source
    assert ".live-panel {\n    display: grid;\n    gap: var(--space-4);\n    min-width: 0;" in page_source
    assert ".live-panel-summary__panel {\n    display: grid;\n    gap: var(--space-4);\n    min-width: 0;" in page_source
    assert ".live-panel-block,\n  .live-panel-summary,\n  .live-panel-summary__panel {\n    min-width: 0;" in page_source
    assert page_source.index("live-panel-summary__meta") < page_source.index("live-panel-summary__instruction")
    assert page_source.index("live-panel-summary__instruction") < page_source.index('role="tablist"')
    assert page_source.index("Abgabe\n                  </button>") < page_source.index("Rückmeldung\n                  </button>")
    assert page_source.index("Rückmeldung\n                  </button>") < page_source.index("Auswertung\n                  </button>")
    assert "formatSubmissionDate" in page_source
    assert "live-latest-link__date" in page_source
    assert "live-latest-link__score" in page_source
    assert ".live-page__intro,\n  .live-page__workspace {\n    width: 100%;\n    margin-inline: auto;" in page_source
    assert ".live-page__intro {\n    max-width: 112rem;" in page_source
    assert ".live-page__workspace {\n    max-width: 132rem;" in page_source
    assert "100vw" not in page_source
    assert "50vw" not in page_source
    assert "task_label" not in page_source[page_source.index('<table class="workspace-data-table">'):page_source.index("</table>")]
    assert "Keine Vorschau" in page_source
    assert 'artifactSubmission.text_body && (artifactSubmission.text_body.startsWith("# makecode.evidence.v1")' not in page_source
    assert 'artifactSubmission.text_body.startsWith("# scratch.evidence.v2")' not in page_source
    assert "@html renderMarkdown(stripSubmissionSchemaHeader(selectedSubmission.text_body))" in page_source
    assert '<pre class="learning-task-submission-summary__plain">{stripSubmissionSchemaHeader(selectedSubmission.text_body)}</pre>' in page_source
