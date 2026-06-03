# Filius-Evidence-Extraktion verbessern

Datum: 2026-06-02
Status: umgesetzt

## Ziel

Filius-`.fls`-Abgaben sollen eine fachlich vollständigere, weiterhin sichere `filius.evidence.v1`-Markdown-Evidence erzeugen. Die Änderung betrifft nur die interne Evidence-Erzeugung für Learning-Feedback. API-Vertrag, Datenbank-Schema und Upload-Vertrag bleiben unverändert.

## User Story

Als Lehrkraft möchte ich, dass Filius-Abgaben neben Topologie auch gestartete Dienste, Zieladressen, WLAN-/Routing-Hinweise und Aufgabenlabels enthalten, damit Feedback auf der tatsächlichen Simulation basiert und keine relevanten Schülerentscheidungen verloren gehen.

## BDD-Szenarien

- Given eine `.fls` mit `ClientBaustein` zu `192.168.1.4`, when GUSTAV die Evidence erzeugt, then Ziel-IP und Client-App erscheinen im App-Abschnitt.
- Given eine `.fls` mit aktivem `ServerBaustein`, when GUSTAV die Evidence erzeugt, then Server-App und Aktivstatus erscheinen.
- Given eine `.fls` mit `GUIDocuItem`, when GUSTAV die Evidence erzeugt, then Dokumentationstext, Typ und Position erscheinen im Abschnitt `Documentation`.
- Given ein WLAN-Switch mit `SSID`, when GUSTAV die Evidence erzeugt, then SSID erscheint beim Knoten.
- Given ein Router mit `ripEnabled`, when GUSTAV die Evidence erzeugt, then RIP-Status erscheint beim Knoten.
- Given eine Anwendung mit persistiertem `port`, when GUSTAV die Evidence erzeugt, then der Port erscheint bei der Anwendung.
- Given eine Datei `/peer2peer/Nachricht.txt`, when GUSTAV die Evidence erzeugt, then nur Metadaten erscheinen und der Nachrichtentext nicht.

## Umsetzung

- `backend/filius/topology.py`
  - `FiliusNode` additiv um `ssid` und `rip_enabled` erweitern.
  - `FiliusApplication` additiv um `port` und `target_ip` erweitern.
  - neue kleine Dataclass `FiliusDocumentationItem` für `GUIDocuItem`.
  - `FiliusTopology` additiv um `documentation_items`.
  - App-Allowlist um `filius.software.clientserver.ClientBaustein`, `filius.software.clientserver.ServerBaustein` und `filius.software.lokal.Terminal` erweitern.
  - Dateisystem-Allowlist für `/peer2peer/*.txt` öffnen, aber Inhalt für diesen Pfad nicht rendern.
- `backend/filius/evidence_v1.py`
  - `Nodes` rendert SSID und RIP-Status.
  - `Web` rendert App-Port, sofern vorhanden.
  - neuer Inhalt in `Custom Applications`: Client-/Server-Bausteine und Terminal-Apps als passive App-Metadaten.
  - `Documentation` rendert echte Doku-Items.
  - Dateimetadaten für `/peer2peer/*.txt` ohne `content`.

## Sicherheit und Datenschutz

- Keine Java-Deserialisierung und keine Ausführung von Filius-Code.
- Keine Roh-XML-Ausgabe.
- Keine Passwörter.
- Keine Inhalte aus `/peer2peer/*.txt`; nur Pfad, Typ, Größe und Hash.
- Bestehendes Escaping und Längenbegrenzungen bleiben erhalten.

## Testplan

- Rote Unit-Tests in `backend/tests/test_filius_evidence_v1.py` mit synthetischen Minimal-Fixtures für App-Port, Client-/Server-Baustein, Dokumentation, SSID/RIP und peer2peer-Metadaten.
- Bestehende Golden-File-Tests für Filius aktualisieren, falls additive Felder byte-stabile Ausgabe ändern.
- Worker-Regression über `backend/tests/learning_adapters/test_local_vision_filius_fls.py`, damit die reichere Evidence weiterhin durch den lokalen Workerpfad läuft.
- Zielbefehle:
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py`
  - `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py`

## Umsetzungsergebnis

- `filius.evidence.v1` bleibt additiv und stabil: API-Vertrag und Datenbank-Schema wurden nicht geändert.
- Ports und Ziel-IP-Adressen werden nun bei relevanten Filius-Anwendungen ausgegeben.
- Client-/Server-Bausteine und Terminal-Anwendungen erscheinen im Abschnitt `Custom Applications`.
- SSID und RIP-Status erscheinen bei Knoten, sofern Filius diese Informationen persistiert.
- `GUIDocuItem`-Texte und Layout-Metadaten erscheinen im Abschnitt `Documentation`.
- `/peer2peer/*.txt` wird als Metadatum aufgenommen; der Dateiinhalt wird weiterhin nicht gerendert.
- `DHCPServer` wird bewusst nicht gerendert, weil Filius in den geprüften Dateien häufig interne Thread-Objekte persistiert, ohne dass daraus zuverlässig eine aktive DHCP-Konfiguration folgt.

## Verifikation

- `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py` → 15 bestanden.
- `.venv/bin/pytest -q backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py` → 21 bestanden.
- `.venv/bin/pytest -q backend/tests/test_filius_fls_validation.py backend/tests/test_learning_filius_fls_submission_api.py backend/tests/test_filius_evidence_v1.py backend/tests/learning_adapters/test_local_vision_filius_fls.py` → 31 bestanden.
