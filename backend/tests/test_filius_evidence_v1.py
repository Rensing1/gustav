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

LEGACY_EMAIL_CLIENT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>1.12.4</string>
  <object class="filius.gui.netzwerksicht.GUIKnotenItem" id="GUIKnotenItem0">
    <void property="imageLabel">
      <object class="filius.gui.netzwerksicht.JSidebarButton">
        <void property="text"><string>Alice</string></void>
        <void property="toolTipText">
          <string>&lt;html&gt;&lt;pre&gt;IP-Adresse(n)/Netzmaske (MAC):
 172.16.1.10 / 255.255.255.0 (AA:BB:CC:DD:EE:01)
Gateway:
DNS-Server: 172.16.1.1&lt;/pre&gt;&lt;/html&gt;</string>
        </void>
        <void property="typ"><string>Notebook</string></void>
      </object>
    </void>
    <void property="knoten">
      <object class="filius.hardware.knoten.Notebook" id="Notebook0">
        <void property="name"><string>Alice</string></void>
        <void property="netzwerkInterfaces">
          <void id="NetzwerkInterface0" index="0">
            <void property="ip"><string>172.16.1.10</string></void>
            <void property="mac"><string>AA:BB:CC:DD:EE:01</string></void>
          </void>
        </void>
        <void property="systemSoftware">
          <void property="dateisystem">
            <void property="arbeitsVerzeichnis">
              <void method="add">
                <object class="javax.swing.tree.DefaultMutableTreeNode">
                  <void property="userObject">
                    <object class="filius.software.system.Datei">
                      <void property="dateiInhalt">
                        <string>example.com;example.com;110;25;Alice;alice-secret;;Alice;Alice@example.com</string>
                      </void>
                      <void property="dateiTyp"><string>text/txt</string></void>
                      <void property="name"><string>konten.txt</string></void>
                    </object>
                  </void>
                </object>
              </void>
              <void method="add">
                <object class="javax.swing.tree.DefaultMutableTreeNode">
                  <void property="userObject"><string>mailserver</string></void>
                  <void method="add">
                    <object class="javax.swing.tree.DefaultMutableTreeNode">
                      <void property="userObject">
                        <object class="filius.software.system.Datei">
                          <void property="dateiInhalt">
                            <string>Mallory;example.com;mallory-secret;Nachname;Vorname;</string>
                          </void>
                          <void property="dateiTyp"><string>txt</string></void>
                          <void property="name"><string>konten.txt</string></void>
                        </object>
                      </void>
                    </object>
                  </void>
                </object>
              </void>
            </void>
          </void>
          <void property="installierteAnwendungen">
            <void method="put">
              <string>filius.software.email.EmailAnwendung</string>
              <object class="filius.software.email.EmailAnwendung">
                <void property="name"><string>Mail</string></void>
              </object>
            </void>
          </void>
        </void>
      </object>
    </void>
  </object>
</java>
"""

ENRICHED_APPLICATIONS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>2.5</string>
  <object class="filius.gui.netzwerksicht.GUIKnotenItem" id="GUIKnotenItem0">
    <void property="imageLabel">
      <object class="filius.gui.netzwerksicht.JSidebarButton">
        <void property="text"><string>WLAN-Switch</string></void>
        <void property="typ"><string>Switch / WLAN</string></void>
      </object>
    </void>
    <void property="knoten">
      <object class="filius.hardware.knoten.Switch" id="Switch0">
        <void property="systemSoftware">
          <void property="SSID"><string>classroom-wifi</string></void>
        </void>
      </object>
    </void>
  </object>
  <object class="filius.gui.netzwerksicht.GUIKnotenItem" id="GUIKnotenItem1">
    <void property="imageLabel">
      <object class="filius.gui.netzwerksicht.JSidebarButton">
        <void property="text"><string>Router</string></void>
        <void property="typ"><string>Vermittlungsrechner</string></void>
      </object>
    </void>
    <void property="knoten">
      <object class="filius.hardware.knoten.Vermittlungsrechner" id="Router0">
        <void property="systemSoftware">
          <void property="installierteAnwendungen">
            <void method="put">
              <string>filius.software.www.WebServer</string>
              <object class="filius.software.www.WebServer">
                <void property="aktiv"><boolean>true</boolean></void>
                <void property="name"><string>ClassWeb</string></void>
                <void property="port"><int>8080</int></void>
              </object>
            </void>
          </void>
          <void property="ripEnabled"><boolean>true</boolean></void>
        </void>
      </object>
    </void>
  </object>
  <object class="filius.gui.netzwerksicht.GUIKnotenItem" id="GUIKnotenItem2">
    <void property="imageLabel">
      <object class="filius.gui.netzwerksicht.JSidebarButton">
        <void property="text"><string>Client</string></void>
        <void property="typ"><string>Rechner</string></void>
      </object>
    </void>
    <void property="knoten">
      <object class="filius.hardware.knoten.Rechner" id="Rechner0">
        <void property="systemSoftware">
          <void property="installierteAnwendungen">
            <void method="put">
              <string>filius.software.clientserver.ClientBaustein</string>
              <object class="filius.software.clientserver.ClientBaustein">
                <void property="name"><string>Client-App</string></void>
                <void property="zielIPAdresse"><string>192.168.1.4</string></void>
              </object>
            </void>
          </void>
        </void>
      </object>
    </void>
  </object>
  <object class="filius.gui.netzwerksicht.GUIKnotenItem" id="GUIKnotenItem3">
    <void property="imageLabel">
      <object class="filius.gui.netzwerksicht.JSidebarButton">
        <void property="text"><string>Server</string></void>
        <void property="typ"><string>Rechner</string></void>
      </object>
    </void>
    <void property="knoten">
      <object class="filius.hardware.knoten.Rechner" id="Rechner1">
        <void property="systemSoftware">
          <void property="installierteAnwendungen">
            <void method="put">
              <string>filius.software.clientserver.ServerBaustein</string>
              <object class="filius.software.clientserver.ServerBaustein">
                <void property="aktiv"><boolean>true</boolean></void>
                <void property="name"><string>Server-App</string></void>
              </object>
            </void>
          </void>
        </void>
      </object>
    </void>
  </object>
  <object class="filius.gui.netzwerksicht.GUIDocuItem">
    <void property="text"><string>Verwaltung</string></void>
    <void property="type"><int>2</int></void>
    <void property="x"><int>751</int></void>
    <void property="y"><int>247</int></void>
    <void property="width"><int>120</int></void>
    <void property="height"><int>40</int></void>
  </object>
</java>
"""

PEER2PEER_FILE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>2.5</string>
  <object class="filius.gui.netzwerksicht.GUIKnotenItem" id="GUIKnotenItem0">
    <void property="imageLabel">
      <object class="filius.gui.netzwerksicht.JSidebarButton">
        <void property="text"><string>Alice</string></void>
        <void property="typ"><string>Rechner</string></void>
      </object>
    </void>
    <void property="knoten">
      <object class="filius.hardware.knoten.Rechner" id="Rechner0">
        <void property="systemSoftware">
          <void property="dateisystem">
            <void property="arbeitsVerzeichnis">
              <void method="add">
                <object class="javax.swing.tree.DefaultMutableTreeNode">
                  <void property="userObject"><string>peer2peer</string></void>
                  <void method="add">
                    <object class="javax.swing.tree.DefaultMutableTreeNode">
                      <void property="userObject">
                        <object class="filius.software.system.Datei">
                          <void property="dateiInhalt">
                            <string>Private Aufgabenbeschreibung mit Namen</string>
                          </void>
                          <void property="dateiTyp"><string>text</string></void>
                          <void property="name"><string>Nachricht.txt</string></void>
                        </object>
                      </void>
                    </object>
                  </void>
                </object>
              </void>
            </void>
          </void>
        </void>
      </object>
    </void>
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
    """DNS/Web evidence should include safe files and hide unrelated file contents."""
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
    assert 'path: "/peer2peer/Nachricht.txt"' in md
    assert 'content: "' not in md.split('path: "/peer2peer/Nachricht.txt"', maxsplit=1)[1].split("\n", maxsplit=1)[0]
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md
    assert "password" not in md.lower()


def test_filius_legacy_email_client_konten_file_renders_metadata_without_secrets() -> None:
    """Older Filius clients store account metadata in root `konten.txt`."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    md = build_evidence_markdown_v1(_fls_with_config(LEGACY_EMAIL_CLIENT_XML))

    assert "- email_clients:" in md
    assert 'accounts: "1"' in md
    assert 'username: "Alice"' in md
    assert 'email: "Alice@example.com"' in md
    assert 'pop3_server: "example.com"' in md
    assert 'pop3_port: "110"' in md
    assert 'smtp_server: "example.com"' in md
    assert 'smtp_port: "25"' in md
    assert "email_clients_without_accounts: 0" in md
    assert "alice-secret" not in md
    assert "mallory" not in md.lower()
    assert "passwort" not in md.lower()
    assert "password" not in md.lower()
    assert "vorname" not in md.lower()
    assert "nachname" not in md.lower()
    assert "konten.txt" not in md
    assert "<java" not in md
    assert "<object" not in md


def test_filius_evidence_renders_app_ports_client_server_apps_node_flags_and_documentation() -> None:
    """Core Filius simulation facts should survive extraction into evidence."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    md = build_evidence_markdown_v1(_fls_with_config(ENRICHED_APPLICATIONS_XML))

    assert 'ssid: "classroom-wifi"' in md
    assert 'rip_enabled: "true"' in md
    assert 'class: "filius.software.www.WebServer"' in md
    assert 'port: "8080"' in md
    assert 'class: "filius.software.clientserver.ClientBaustein"' in md
    assert 'target_ip: "192.168.1.4"' in md
    assert 'class: "filius.software.clientserver.ServerBaustein"' in md
    assert 'text: "Verwaltung"' in md
    assert 'type: "2"' in md
    assert 'x: "751"' in md
    assert 'y: "247"' in md
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md


def test_filius_evidence_renders_peer2peer_file_metadata_without_content() -> None:
    """Peer-to-peer text files may be relevant, but contents stay out of evidence."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    md = build_evidence_markdown_v1(_fls_with_config(PEER2PEER_FILE_XML))

    assert 'path: "/peer2peer/Nachricht.txt"' in md
    assert 'content_kind: "text"' in md
    assert 'sha256: "' in md
    assert "Private Aufgabenbeschreibung" not in md
    assert 'content: "' not in md
    assert "<java" not in md
    assert "<object" not in md


def test_filius_evidence_renders_peer2peer_file_metadata_case_insensitively() -> None:
    """Peer-to-peer metadata should render with the same case rules as extraction."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    xml = PEER2PEER_FILE_XML.replace(b"peer2peer", b"Peer2Peer").replace(
        b"Nachricht.txt", b"Nachricht.TXT"
    )

    md = build_evidence_markdown_v1(_fls_with_config(xml))

    assert 'path: "/Peer2Peer/Nachricht.TXT"' in md
    assert 'content_kind: "text"' in md
    assert "Private Aufgabenbeschreibung" not in md
    assert 'content: "' not in md
    assert "<java" not in md
    assert "<object" not in md


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


def test_filius_official_dns_fixture_matches_golden_file() -> None:
    """The official Filius DNS fixture should render byte-stable DNS evidence."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    fixture_dir = Path("backend/tests/fixtures/filius/filius-official-dns")
    fls_bytes = (fixture_dir / "dns_server.fls").read_bytes()
    expected = (fixture_dir / "dns_server.evidence.md").read_text(encoding="utf-8")

    md = build_evidence_markdown_v1(fls_bytes)

    assert md == expected
    assert 'class: "filius.software.dns.DNSServer"' in md
    assert 'path: "/dns/hosts"' in md
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md


def test_filius_official_web_fixture_matches_golden_file() -> None:
    """The official Filius Web fixture should render byte-stable Web evidence."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    fixture_dir = Path("backend/tests/fixtures/filius/filius-official-web")
    fls_bytes = (fixture_dir / "webserver.fls").read_bytes()
    expected = (fixture_dir / "webserver.evidence.md").read_text(encoding="utf-8")

    md = build_evidence_markdown_v1(fls_bytes)

    assert md == expected
    assert 'class: "filius.software.www.WebServer"' in md
    assert 'path: "/webserver/index.html"' in md
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md


def test_filius_official_email_fixture_renders_metadata_without_secrets() -> None:
    """Email evidence should include configuration metadata but never secrets or messages."""
    from backend.filius.evidence_v1 import build_evidence_markdown_v1

    fixture_dir = Path("backend/tests/fixtures/filius/filius-official-email")
    fls_bytes = (fixture_dir / "email_komplett.fls").read_bytes()
    expected = (fixture_dir / "email.evidence.md").read_text(encoding="utf-8")

    md = build_evidence_markdown_v1(fls_bytes)

    assert md == expected
    assert "## Email" in md
    assert "- email_clients:" in md
    assert "- email_servers:" in md
    assert 'mail_domain: "senior.de"' in md
    assert 'email: "rechner3@senior.de"' in md
    assert 'pop3_server: "141.99.50.233"' in md
    assert "passwort" not in md.lower()
    assert "password" not in md.lower()
    assert "vorname" not in md.lower()
    assert "nachname" not in md.lower()
    assert "subject:" not in md.lower()
    assert "huhu" not in md.lower()
    assert "<java" not in md
    assert "<object" not in md
    assert "idref" not in md


def test_filius_official_app_fixtures_keep_source_attribution() -> None:
    """Committed upstream app fixtures must carry source and license metadata."""
    fixtures = {
        "filius-official-dns": "dns_server.fls",
        "filius-official-web": "webserver.fls",
        "filius-official-email": "email_komplett.fls",
    }

    for directory, filename in fixtures.items():
        attribution = Path(f"backend/tests/fixtures/filius/{directory}/ATTRIBUTION.md").read_text(encoding="utf-8")
        assert "Filius upstream repository" in attribution
        assert "GPL-3.0" in attribution
        assert "dcd965f6139baef4c27cc6d3cc34106f6bebda40" in attribution
        assert filename in attribution
