# Kompakte, sichere und gezielte Feature-Abnahme

**Stand:** 01.09.2026
**Status:** Implementiert und nach Review erneut verifiziert

## User Story

Als Entwickler möchte ich genau die Browserreise meines aktuellen Features sicher ausführen, damit relevante Integrationsfehler auffallen, ohne fremde Daten, Produktivsysteme oder den lokalen Entwicklungsstand zu gefährden.

## BDD-Szenarien und Testzuordnung

| Szenario | Automatisierter Nachweis |
| --- | --- |
| **Given** kein, ein ungültiges oder ein unbekanntes `FEATURE`, **when** das Gate startet, **then** bricht es vor jeder Mutation ab. | `backend/tests/test_feature_acceptance_tool.py`, `backend/tests/test_feature_acceptance_gate_contract.py` |
| **Given** ein gültiger Spec-Dateistamm, **when** `make verify-feature FEATURE=<name>` läuft, **then** folgen auf `make verify` nur die markierten Tests dieser Datei. | `backend/tests/test_feature_acceptance_gate_contract.py` |
| **Given** eine entfernte Web-, Keycloak-, Storage- oder Datenbankadresse, **when** ein schreibender Browsertest startet, **then** verweigert der Preflight den Lauf. | `backend/tests/test_feature_acceptance_tool.py` |
| **Given** ein erfolgreicher oder fehlgeschlagener Test, **when** der Lauf endet, **then** wird die eigentümergebundene Bereinigung garantiert versucht. | `backend/tests/test_feature_acceptance_tool.py` |
| **Given** ein abgebrochener vorheriger Lauf, **when** der nächste Lauf startet, **then** wird zuerst dessen privates Manifest bereinigt. | `backend/tests/test_feature_acceptance_tool.py` |
| **Given** eine KI-gestützte Browserreise, **when** sie im Pflicht-Gate läuft, **then** ist die Rückmeldung deterministisch vorbereitet und kontaktiert keinen externen Provider. | gezielte Playwright-Reisen und Fixture-Vertragstests |

## Umsetzung

1. `verify-feature` verlangt einen sicheren Spec-Dateistamm; die historische Gesamtsuite wird als `test-feature-regression` ausdrücklich opt-in.
2. Ein zentraler Orchestrator prüft lokale Endpunkte, sperrt parallele Läufe, führt Playwright aus und bereinigt in `finally`.
3. Ein privates Laufmanifest erfasst ausschließlich exakt benannte E2E-Konten und exakt registrierte numerische H5P-Inhalts-IDs. Die Bereinigung löscht H5P-Inhalte, eigene Lerneinheiten und Kurse über Produktiv-APIs, wartet auf Löschaufträge und entfernt anschließend die Keycloak-Konten.
4. Feature-Specs verwenden eine gemeinsame automatische Fixture, die dieselbe Bereinigung nach jedem Test anstößt; der Orchestrator wiederholt sie als Rückfallebene am Laufende.
5. Browserprüfungen verwenden gemeinsame E2E-Personas. Detail-, Visual- und KI-Provider-Verträge bleiben in ihren gezielten Testprofilen.

## Verträge und Datenhaltung

OpenAPI, Datenbankschema, RLS und produktive Anwendungsschnittstellen ändern sich nicht. Neu sind ausschließlich lokale Entwicklerbefehle, das private Manifest unter `.tmp` und die ausdrückliche Freigabe `E2E_LOCAL_MUTATION_ALLOWED=1`.

## Abschlusskriterien

- Ungültige oder entfernte Ziele werden vor jeder Mutation abgelehnt.
- Gezielte und vollständige Feature-Profile sind getrennt.
- Testfehler und abgebrochene Vorläufe hinterlassen keinen unbemerkten Datenbestand.
- Pflichtläufe enthalten keine frei generierten externen KI-Ausgaben.
- `make verify` sowie zwei aufeinanderfolgende gezielte Browserabnahmen sind erfolgreich.

## Abschlussnachweis

- `make verify`: 2.500 Backendtests bestanden, 78 erwartungsgemäß übersprungen; 641 Frontendtests und 62 H5P-Sidecar-Tests bestanden; Svelte-Prüfung, Produktions-Build, OpenAPI-, Architektur-, Supply-Chain- und Containerprüfungen grün.
- Zwei unmittelbar aufeinanderfolgende gezielte Läufe von `learner-navigation` bestanden. Die Rückmeldung wurde deterministisch vorbereitet; ein externer KI-Provider war nicht beteiligt.
- `make test-feature-regression`: 19 serielle Ausführungen in Chromium und WebKit/iPad bestanden.
- Die gezielten H5P-Läufe `practice-session` und `cli-authoring` bestätigten nach der letzten Sicherheitsverschärfung ausdrücklich einen leeren Bestand an laufgebundenen Konten, Kursen, Lerneinheiten und registrierten H5P-Inhalten.
- Das Wiederherstellungsmanifest eines absichtlich fehlgeschlagenen frühen Probelaufs wurde beim nächsten Start exakt gebunden bereinigt. Auch fehlgeschlagene spätere Browserreisen hinterließen kein Manifest.

## Review-Reparatur vom 01.09.2026

Die erste Umsetzung erfüllt die äußeren Befehlsverträge, lässt aber an sechs Stellen noch Sicherheits- oder Wartbarkeitslücken. Die Reparatur folgt erneut Red–Green–Refactor und verändert weder OpenAPI noch Datenbankschema oder produktive Anwendungsschnittstellen.

| BDD-Szenario | Zunächst fehlschlagender Nachweis | Ziel der minimalen Umsetzung |
| --- | --- | --- |
| **Given** die lokale `.env` nennt eine lokale Datenbank, der bereits laufende Web- oder Worker-Container verwendet jedoch eine entfernte DSN, **when** die Browserabnahme startet, **then** bricht sie vor Manifest und Mutation ab. | Parametrisierte Orchestrator-Tests mit aufgezeichneter Containerumgebung | Der Preflight prüft zusätzlich die tatsächlich laufenden Container und erlaubt dort nur die lokalen Compose- und Loopback-Datenbankhosts. |
| **Given** Browser- und Bereinigungsanmeldungen haben BFF- und Anwendungssitzungen erzeugt, **when** ein Lauf bereinigt wird, **then** werden nur Sitzungen der exakt aufgelösten E2E-Benutzer entfernt und anschließend als abwesend bestätigt. | Datenbankadapter-Test mit fremden Kontrollsitzungen | Exakte `sub`- und Session-ID-Bindung; keine Tokenwerte erscheinen in Ausgabe oder Manifest. |
| **Given** ein H5P-Inhalt wird registriert, **when** die Bereinigung läuft, **then** darf ihn ausschließlich die im Manifest gebundene E2E-Lehrkraft löschen. | TypeScript- und Orchestrator-Vertragstests für unbekannte oder fremde Eigentümer | Manifest speichert Paare aus Inhalts-ID und Eigentümer-E-Mail; Bereinigung gruppiert strikt nach Eigentümer. |
| **Given** der Lauf wird während einer temporären Keycloak-SMTP-Konfiguration abgebrochen, **when** die nächste Bereinigung startet, **then** stellt sie die zuvor gesicherte Konfiguration wieder her. | Manifest- und Recovery-Tests | Der private Laufzustand erfasst die exakte vorherige Konfiguration und löscht sie erst nach erfolgreicher Wiederherstellung. |
| **Given** eine Pflichtreise fordert KI-Rückmeldung an, **when** sie läuft, **then** durchläuft die Browseraktion den echten Server-, RLS- und Queue-Pfad, während ausschließlich die Provider-Ausführung angehalten und die Fertigstellung reproduzierbar vorgenommen wird. | Browser-Fixture-Verträge und Orchestrator-Tests für beide Exitpfade | Der lokale Worker wird wiederherstellbar pausiert, die echte Anfrage erzeugt, der bestehende Auftrag deterministisch abgeschlossen und der Worker garantiert freigegeben. |
| **Given** eine umfangreiche Detailreise wurde aus dem Pflicht-Gate entfernt, **when** sie gezielt oder gesammelt angefordert wird, **then** bleibt sie über ein benanntes Opt-in-Profil ausführbar. | Makefile- und Orchestrator-Vertragstests | Sicheres `detail`-Profil mit `@feature-detail`; das Regression-Gate bleibt ausschließlich `@feature-acceptance`. |

### Reparaturreihenfolge

1. Sicherheits-, Manifest-, Makefile- und Browserverträge rot ergänzen.
2. Laufzeit-Preflight und exakt gebundene Sitzungs-, H5P- und SMTP-Bereinigung grün implementieren.
3. KI-Reisen auf echte Browseranforderung plus deterministische lokale Fertigstellung umstellen und Worker-Recovery absichern.
4. Detailprofil markieren, dokumentieren und gezielt ausführbar machen.
5. Zieltests, `make verify`, zwei identische gezielte Abnahmen und die lokale Opt-in-Regression ausführen; erst danach den Status wieder auf „Implementiert und verifiziert“ setzen.

### Abschlussnachweis der Review-Reparatur

- 39 gezielte Orchestrator- und Harness-Verträge sowie vier TypeScript-Verträge für den privaten Laufzustand bestanden; die erweiterte fokussierte Auswahl mit Makefile- und Visual-Smoke-Verträgen umfasst 62 bestandene Tests.
- Die reale Container-Laufzeitprüfung verweigerte den zunächst noch mit `GUSTAV_ENV=prod` gestarteten lokalen Stack vor jeder Mutation. Nach lokaler Neuerstellung im Entwicklungsmodus bestand sie für Web, Frontend, H5P und Learning-Worker einschließlich aller wirksamen Datenbank-DSNs.
- `learner-navigation` und `practice-session` fordern Rückmeldung wieder über die echte Oberfläche an und erzeugen reale Submission- und Queue-Zustände. Währenddessen ist ausschließlich der lokale Provider-Worker wiederherstellbar pausiert; die vorhandenen Worker-Completion- und Practice-Scheduler-Helfer verarbeiten reproduzierbare Rückgabedaten.
- Die gezielten Einladungs-, CLI-/H5P- und `@feature-detail`-Läufe bestanden und bestätigten SMTP-Wiederherstellung, exakte H5P-Eigentümerbindung sowie die Ausführbarkeit des neuen Detailprofils.
- `make verify` bestand mit 2.513 Backendtests und 78 erwarteten Überspringungen, 642 Frontendtests, 62 H5P-Tests, fehlerfreier Svelte-Prüfung und Produktions-Build sowie grünen OpenAPI-, Architektur-, Supply-Chain-, Inventar- und Containerprüfungen.
- Zwei unmittelbar aufeinanderfolgende gezielte `learner-navigation`-Abnahmen bestanden. Anschließend bestand `make test-feature-regression` mit 19 von 19 seriellen Chromium- und WebKit/iPad-Reisen.
- Nach jedem Browserlauf bestätigte der Orchestrator einen leeren Bestand an laufgebundenen Konten, Kursen, Lerneinheiten, Sitzungen, Tokens und registrierten H5P-Inhalten; das Abschlussmanifest wurde entfernt und der Learning-Worker freigegeben.
