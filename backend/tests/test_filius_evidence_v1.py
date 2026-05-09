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


def test_filius_mehrere_netze_fixture_matches_routing_golden_file() -> None:
    """The real inf-schule routing fixture should render byte-stable routing evidence."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    fixture_dir = Path("backend/tests/fixtures/filius/inf-schule-mehrere-netze")
    fls_bytes = (fixture_dir / "filius_mehrere_netze.fls").read_bytes()
    expected = (fixture_dir / "filius_mehrere_netze.evidence.md").read_text(encoding="utf-8")

    md = build_evidence_markdown_v1(fls_bytes)

    assert md == expected
    assert 'ip: "3.0.0.1"' in md
    assert 'ip: "192.168.0.100"' in md
    assert 'cidr: "3.0.0.0/24"' in md
    assert "- manual_routes:" in md
    assert 'destination: "192.168.1.0/24"' in md
    assert 'next_hop_ip: "1.0.0.2"' in md
    assert 'via_interface: "n2-if1"' in md
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md
    assert "password" not in md.lower()


def test_filius_mehrere_netze_fixture_keeps_source_attribution() -> None:
    """Committed OER routing fixtures must carry source and license metadata."""
    fixture_dir = Path("backend/tests/fixtures/filius/inf-schule-mehrere-netze")
    attribution = (fixture_dir / "ATTRIBUTION.md").read_text(encoding="utf-8")

    assert "inf-schule" in attribution
    assert "NM" in attribution
    assert "CC BY-SA 4.0" in attribution
    assert "filius_mehrere_netze.fls" in attribution


def test_filius_synthetic_dns_web_fixture_renders_safe_dns_and_web_evidence() -> None:
    """DNS/Web evidence should include allowlisted files and hide unrelated paths."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    fixture_dir = Path("backend/tests/fixtures/filius/synthetic-dns-web")
    xml = (fixture_dir / "configuration.xml").read_bytes()
    expected = (fixture_dir / "dns_web.evidence.md").read_text(encoding="utf-8")

    md = build_evidence_markdown_v1(_fls_with_config(xml))

    assert md == expected
    assert "## DNS" in md
    assert 'class: "filius.software.dns.DNSServer"' in md
    assert 'path: "/dns/hosts"' in md
    assert "example.test 192.168.0.10" in md
    assert "## Web" in md
    assert 'class: "filius.software.www.WebServer"' in md
    assert 'path: "/webserver/index.html"' in md
    assert "&lt;html&gt;&lt;body&gt;\\\"Hallo\\\" & willkommen&lt;/body&gt;&lt;/html&gt;" in md
    assert 'path: "/webserver/logo.png"' in md
    assert 'content: "' not in md.split('path: "/webserver/logo.png"', maxsplit=1)[1].split("\n", maxsplit=1)[0]
    assert "must not leak" not in md
    assert "/peer2peer" not in md
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md
    assert "password" not in md.lower()


def test_filius_official_firewall_fixture_renders_real_rules() -> None:
    """The official Filius firewall fixture should render real rule evidence."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    fixture_dir = Path("backend/tests/fixtures/filius/filius-official-firewall")
    fls_bytes = (
        fixture_dir / "Internet_Komplett_mit_eMail_Webserver_Intranet_Portforwarding_Firewall_DHCP_DE.fls"
    ).read_bytes()
    expected = (fixture_dir / "firewall.evidence.md").read_text(encoding="utf-8")

    md = build_evidence_markdown_v1(fls_bytes)

    assert md == expected
    assert "## Firewall" in md
    assert "- firewalls:" in md
    assert 'node: "n' in md
    assert 'activated: "true"' in md
    assert 'protocol: "*"' in md
    assert 'action: "ACCEPT"' in md
    assert 'action: "DROP"' in md
    assert 'source: "10.10.20.0/24"' in md
    assert 'destination: "42.0.0.10/32"' in md
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md
    assert "password" not in md.lower()
    assert "passwort" not in md.lower()


def test_filius_official_firewall_fixture_keeps_source_attribution() -> None:
    """Committed upstream fixtures must carry source and license metadata."""
    fixture_dir = Path("backend/tests/fixtures/filius/filius-official-firewall")
    attribution = (fixture_dir / "ATTRIBUTION.md").read_text(encoding="utf-8")

    assert "Filius upstream repository" in attribution
    assert "GPL-3.0" in attribution
    assert "dcd965f6139baef4c27cc6d3cc34106f6bebda40" in attribution
    assert "Internet_Komplett_mit_eMail_Webserver_Intranet_Portforwarding_Firewall_DHCP_DE.fls" in attribution
