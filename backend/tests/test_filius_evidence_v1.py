"""
Filius Evidence v1 -- deterministic Markdown report.

Intent:
    A Filius `.fls` archive should become bounded, human-readable Markdown for
    the feedback LLM. The report must not expose raw XML.
"""

from __future__ import annotations

import io
from pathlib import Path
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


def test_filius_clientserver_fixture_matches_topology_golden_file() -> None:
    """The real inf-schule fixture should render byte-stable topology evidence."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    fixture_dir = Path("backend/tests/fixtures/filius/inf-schule-clientserver")
    fls_bytes = (fixture_dir / "filius_ClientServer.fls").read_bytes()
    expected = (fixture_dir / "filius_ClientServer.evidence.md").read_text(encoding="utf-8")

    md = build_evidence_markdown_v1(fls_bytes)

    assert md == expected
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md
    assert "password" not in md.lower()


def test_filius_clientserver_fixture_keeps_source_attribution() -> None:
    """Committed OER fixtures must carry source and license metadata."""
    fixture_dir = Path("backend/tests/fixtures/filius/inf-schule-clientserver")
    attribution = (fixture_dir / "ATTRIBUTION.md").read_text(encoding="utf-8")

    assert "inf-schule" in attribution
    assert "CC BY-SA 4.0" in attribution
    assert "filius_ClientServer.fls" in attribution
