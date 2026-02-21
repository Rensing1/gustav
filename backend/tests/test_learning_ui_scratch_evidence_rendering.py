from __future__ import annotations

import uuid

from backend.web.main import _render_submission_text_container


def test_scratch_evidence_is_wrapped_for_scoped_css() -> None:
    """Scratch evidence should be wrapped so we can style it without affecting other markdown."""
    submission_id = str(uuid.uuid4())
    record = {
        "analysis_json": {
            "text": "# scratch.evidence.v2\n\n## Summary\n- stage_present: true\n",
        }
    }
    html = _render_submission_text_container(record, submission_id=submission_id, has_artifact=False, oob=False)
    assert 'class="scratch-evidence' in html


def test_non_scratch_markdown_is_not_wrapped() -> None:
    """Regular markdown (student text) should not receive scratch-specific wrappers."""
    submission_id = str(uuid.uuid4())
    record = {"text_body": "## Hello\n\n- A\n"}
    html = _render_submission_text_container(record, submission_id=submission_id, has_artifact=False, oob=False)
    assert "scratch-evidence" not in html
