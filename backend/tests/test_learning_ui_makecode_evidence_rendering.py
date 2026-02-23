from __future__ import annotations

import uuid

from backend.web.main import _render_submission_text_container


def _make_evidence(*, files_md: str) -> str:
    # Minimal makecode evidence wrapper; matches `makecode.evidence.v1` header.
    return "# makecode.evidence.v1\n\n## Files\n\n" + files_md


def test_makecode_evidence_renders_only_main_py_when_present() -> None:
    submission_id = str(uuid.uuid4())
    evidence = _make_evidence(
        files_md=(
            '### file: "pxt.json"\n'
            "```json\n{\"name\":\"p\"}\n```\n\n"
            '### file: "main.ts"\n'
            "```typescript\nlet a = 1\n```\n\n"
            '### file: "main.py"\n'
            "```python\nprint('hi')\n```\n\n"
        ),
    )
    record = {"text_body": evidence}

    html = _render_submission_text_container(record, submission_id=submission_id, has_artifact=False, oob=False)

    assert "print" in html
    assert "let a" not in html
    assert "pxt.json" not in html
    assert 'class="makecode-evidence"' in html


def test_makecode_evidence_falls_back_to_main_ts_when_no_python() -> None:
    submission_id = str(uuid.uuid4())
    evidence = _make_evidence(
        files_md=(
            '### file: "pxt.json"\n'
            "```json\n{\"name\":\"p\"}\n```\n\n"
            '### file: "main.ts"\n'
            "```typescript\nlet b = 2\n```\n\n"
        ),
    )
    record = {"text_body": evidence}

    html = _render_submission_text_container(record, submission_id=submission_id, has_artifact=False, oob=False)

    assert "let b" in html
    assert "pxt.json" not in html
    assert 'class="makecode-evidence"' in html


def test_makecode_evidence_hides_irrelevant_files_when_no_main_found() -> None:
    submission_id = str(uuid.uuid4())
    evidence = _make_evidence(
        files_md=(
            '### file: "pxt.json"\n'
            "```json\n{\"name\":\"p\"}\n```\n\n"
        ),
    )
    record = {"text_body": evidence}

    html = _render_submission_text_container(record, submission_id=submission_id, has_artifact=False, oob=False)

    assert "main.py" in html
    assert "main.ts" in html
    assert "pxt.json" not in html
    assert 'class="makecode-evidence"' in html


def test_makecode_marker_does_not_override_regular_markdown() -> None:
    """
    Defense-in-depth: Do not compact arbitrary user text just because it starts
    with the MakeCode evidence marker.
    """
    submission_id = str(uuid.uuid4())
    record = {"text_body": "# makecode.evidence.v1\n\nHallo Welt\n\nDas ist normaler Text."}

    html = _render_submission_text_container(record, submission_id=submission_id, has_artifact=False, oob=False)

    assert "Hallo Welt" in html
    assert "Kein" not in html
