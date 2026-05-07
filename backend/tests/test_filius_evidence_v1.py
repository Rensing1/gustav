"""
Filius Evidence v1 -- deterministic Markdown report.

Intent:
    A Filius `.fls` archive should become bounded, human-readable Markdown for
    the feedback LLM. The report must not expose raw XML.
"""

from __future__ import annotations

import io
import zipfile


MINIMAL_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>2.5</string>
  <object class="filius.gui.netzwerksicht.GUIKnotenItem">
    <void property="name"><string>Client</string></void>
  </object>
</java>
"""


def _fls_with_config(config: bytes = MINIMAL_XML) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("projekt/konfiguration.xml", config)
    return buf.getvalue()


def test_filius_evidence_v1_renders_stable_sections_without_raw_xml() -> None:
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    md = build_evidence_markdown_v1(_fls_with_config())

    assert md.startswith("# filius.evidence.v1")
    for heading in (
        "## Project",
        "## Parser Notes",
        "## Nodes",
        "## Links",
        "## Routing",
        "## Firewall",
        "## DNS",
        "## Web",
        "## Email",
        "## Documentation",
        "## Custom Applications",
    ):
        assert heading in md
    assert 'filius_version: "2.5"' in md
    assert "GUIKnotenItem" in md
    assert "<java" not in md
    assert "<object" not in md
