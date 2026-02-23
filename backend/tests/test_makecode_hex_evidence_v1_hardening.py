"""
MakeCode evidence rendering hardening.

Evidence is fed into LLM-based feedback. The renderer must treat all extracted
project metadata (including file names) as untrusted input and must not allow
Markdown structure injection via newlines.
"""

from backend.makecode.hex_evidence_v1 import build_evidence_markdown_v1
from backend.storage.makecode_hex_validation import MakeCodeProject


def test_makecode_evidence_v1_escapes_newlines_in_filenames():
    project = MakeCodeProject(
        files={
            # If rendered verbatim in a Markdown heading, this becomes a new heading.
            "main.ts\n# HACKED": "basic.showString('ok')",
        },
        meta={},
    )

    md = build_evidence_markdown_v1(project=project)

    # The injected heading must not appear as an actual heading line.
    assert "\n# HACKED" not in md
    # The string should still be visible, but escaped (JSON-style).
    assert "\\n# HACKED" in md
