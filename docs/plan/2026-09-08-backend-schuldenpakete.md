# Backend-Schuldenpakete 1–3 und 5

Status: Erste gemeinsame Umsetzungsetappe verifiziert; Pakete 2 und 3 noch nicht vollständig abgeschlossen. Grundlage ist der Schuldenabbauplan vom 6. September 2026; beauftragt sind Dateispeicher-Anbindung, Backend-Entkopplung, Abgabe-/Worker-/H5P-Struktur und Katalogabfragen. Gestaltung und Oberflächenmigration (Paket 4) warten ausdrücklich auf Beratung. DSPy-Version, Optimizing, Prompts und Modelle bleiben unverändert.

## Ziel und Grenzen

Als Entwickler möchte ich Abhängigkeiten und Verarbeitungsphasen von GUSTAV nachvollziehen und unabhängig testen können. Als Lehrkraft und Lernender behalte ich dieselben Antworten, Berechtigungen und gespeicherten Inhalte. Es bleibt eine zusammenhängende Plattform; getrennte Testverdrahtungen sind keine zusätzliche Betriebsarchitektur.

Öffentliche API-Verträge, Schema, ENV-Namen und Datenhaltung bleiben kompatibel. Vor jedem Teilschritt werden die betroffenen Verträge und Adapter geprüft. Keine Migration ohne fachliche Notwendigkeit; keine Produktionszugriffe, Datenresets oder Pushes. Das Refactoring schafft keinen neuen nutzerseitigen Ablauf; deshalb gilt für rein interne Teilschritte `make verify`, ergänzt um vorhandene echte DB- und gezielte Ablaufprüfungen. Falls sich doch ein Oberflächenablauf ändern müsste, wird dies nicht in diese Umsetzung hineingezogen.

## Reihenfolge und Testentwurf

1. Upload-Freigaben: Speicherabhängigkeit ausdrücklich übergeben; Aufbau des bisherigen Speicheradapters von globaler Installation trennen. Erfolgreichen Aufbau wiederverwenden, fehlgeschlagenen Aufbau erneut versuchen. Verbleibende Verbraucher werden nicht heimlich umgeschaltet.
2. Übrige Backend-Abhängigkeiten inventarisieren und nach Verbrauchergruppen migrieren. Gemeinsame reine Hilfsfunktionen direkt importieren; Daten-/Netzwerkzugriffe explizit übergeben. Reparatur-Fixtures erst nach Migration sämtlicher betroffener Verbraucher entfernen.
3. Abgabe-, Worker- und H5P-Verarbeitung entlang vorhandener fachlicher Phasen trennen. Transaktionen, Idempotenz, Sperren, Retry-Regeln und Sicherheitsreihenfolge bleiben erhalten. Zuerst Charakterisierungstests, dann Extraktionen.
4. Katalog (beauftragtes Paket 5): Kurszuordnungen und Abschnittsmetadaten gebündelt lesen. Bestehende Eigentümergrenzen, Listenlimit 200, Reihenfolge, Aktivitätsdatum und Statusprojektion erhalten. Echte DB-Parität und konstante Abfragezahl nachweisen.
5. Kritische Durchsicht, vollständige Gates, Dokumentation und lokale Commits. Der Bericht unterscheidet abgeschlossene Teile von tatsächlich verbliebenen Schulden.

| Given – When – Then | Nachweis |
| --- | --- |
| Zwei ausdrücklich konfigurierte Speicheradapter – abwechselnde Upload-Anfragen – keine gegenseitige Umschaltung und keine globale Neuverdrahtung | Neue Upload-Speicher-Isolationstests |
| Fehlende Konfiguration oder vorübergehender Aufbaufehler – autorisierte Upload-Anfrage und Wiederholung – private 503, anschließend erneuter Aufbau möglich | Provider-/HTTP-Tests und bestehende Lazy-Storage-Verträge |
| Fehlende Anmeldung, fremder Kurs, entzogene Freigabe oder falscher MIME-Typ – Upload – Ablehnung vor Signierung | Bestehende Upload-Provider- und echte DB-Tests |
| Explizite Backend-Abhängigkeiten – alternative Testverdrahtung – kein Zugriff auf Fassaden oder veränderte Endpoint-Globals | Verbraucherbezogene Isolationstests, Architekturverträge, Gesamtsuite |
| Abgabe/Job mit Erfolgs-, Wiederholungs- oder Fehlerfall – getrennte Verarbeitungsschritte – unverändertes Ergebnis und Transaktionsverhalten | Bestehende Abgabe-/Worker-Verträge plus Charakterisierung der Extraktionsgrenzen |
| H5P-Autorisierung, Import-/Speicherfehler und Rückabwicklung – getrennte Routerverantwortung – unveränderte Reihenfolge und private Fehler | Bestehende H5P-API-/Router-/Security-Tests plus gezielte Extraktionsverträge |
| Leerer/kleiner/großer Lehrkraftbestand und fremde Inhalte – Katalog lesen – identische Projektion bei begrenzter konstanter Zahl von DB-Abfragen | Neue Katalog-Batchtests, echte DB-Parität und Grenzfälle, bestehende Home-/Katalog-API-Tests |

## Nachweise

### Ergänzter Teilschritt: Dialog-Abhängigkeiten (Paket 2)

Die sechs bestehenden Dialog-Endpunkte verwenden noch einen global ersetzbaren Anwendungsfalldienst. Vor der Umstellung werden abwechselnde Zugriffe zweier Testverdrahtungen, Rollen-/CSRF-/ID-Ablehnung, alle sechs Operationen und die Freigabe der Ereignisschleife bei wartendem Dienst getestet. Die Factory hält nur den zustandslosen DB-Adapter vor; der bisherige Generator mit seinem anfragebezogenen Verbrauchspuffer wird weiterhin pro Aufruf neu erzeugt. Kein DSPy-Programm und keine KI-Konfiguration wird verändert. Bestehende Dialog-Use-Case-/DB-Verträge bleiben ergänzende Nachweise. Die übrigen Learning-/Teaching-/BFF-Provider sind damit noch nicht insgesamt migriert.

- Start: sauberer `master`, `1b701d0a`; Fast-Forward-Abgleich erfolgreich, bereits aktuell. Keine fremden Änderungen vorhanden.
- Vorprüfung: bestehende Upload-/Katalog-Endpunkte in `api/openapi.yml`, Storage-ENV-Bezeichner und Compose-Konfiguration sowie vorhandene Migrationen geprüft. Secrets werden nicht ausgegeben. Keine Vertrags-, Schema- oder Konfigurationsänderung geplant.

### Verifizierte Teilergebnisse vor dem Gesamtlauf

- Upload: neue Speicher-Provider-Verträge zuerst rot, dann grün. 109 gezielte Storage-/Upload-/Material-/DB-Tests erfolgreich. Zwei globale Storage-Reparatur-Fixtures entfernt. Kombinierte Upload-/Abgabetests benötigen weiterhin ihren alten Abgabeadapter, reichen den Upload-Adapter aber ausdrücklich an den Provider weiter.
- Katalog: Schleifenfreiheit und Batch-DB-Verträge zuerst rot, dann grün. 24 gezielte Tests erfolgreich. Echte DB-Parität bei 0, 1, 20 und 201 eigenen Einträgen sowie fremden IDs: maximal vier Leseoperationen plus vier RLS-Kontextsetzungen; leerer Katalog zwei Leseoperationen plus Kontext. Keine Migration; SQL bleibt parametrisiert und eigentümergebunden. Das bestehende Limit 200 wird nicht erweitert.
- Worker: zwei Schichtengrenzen zuerst rot; neun vorhandene Kontext-/Transaktions-/Fehlerverträge als Charakterisierung grün. Nach Extraktion 70 Worker-Tests erfolgreich. Persistenz besitzt weder Verbindungen noch Commit/Rollback; keine Änderung an Queue-Leasing, KI-Aufrufen oder Retry-Entscheidungen.
- Abgabevalidierung: 14 neue Grenzfalltests für Text, H5P-Scores und Upload-Limit grün; zusammen mit den bestehenden Extraktionsverträgen 16 Tests. Die Web-Hilfe übergibt nur noch das konfigurierte Größenlimit an die reine Fachfunktion.
- H5P: Routertests zuerst wegen fehlender Module rot. Fünf lokale HTTP-/Packaging-Tests grün, einschließlich Reihenfolge der Ergebnisweiterleitung, stabiler Idempotenzschlüssel und Minimierung weitergereichter Cookies. Vorhandene Sicherheitsverträge auf ihre tatsächlichen neuen Quellen umgestellt; keine Regel entfernt. H5P-Image gebaut, Routerimporte darin ohne Netzwerk/Volumes erfolgreich, `make docker-validate` grün. Keine laufende Installation umgestellt. Die beiden Debug-HTML-Blöcke wurden unverändert verschoben, nicht gestaltet.
- Dialog: zwölf neue Isolations-/Nebenläufigkeits-/Factorytests sowie bestehende HTTP-/Use-Case-Verträge erfolgreich (26 Tests). DB-Charakterisierung ergänzt; keine externen Modellaufrufe.
- Erster Gesamtlauf: 3015 Backend-Tests erfolgreich, sieben Fehler in alten Upload-Testverdrahtungen, 33 ausdrücklich deaktivierte Tests. Die sieben Fehler wurden ohne Produktionskompatibilitätsschalter korrigiert; 94 gezielte kombinierte DB-/Upload-/Abgabeprüfungen danach erfolgreich. Ein anfänglicher Importgrenzenfehler im neuen Test wurde durch die etablierte Testimportform behoben, nicht durch Erhöhen der Baseline.

### Neu festgestellte Vertragsgrenze: TD-010

Der neue echte Dialog-DB-Test zeigte zunächst `psycopg.errors.NoDataFound` beim Start einer noch nicht sichtbaren Aufgabe. `api/openapi.yml` dokumentiert dort bereits 404; die aktuelle DB-Ausnahme wird aber nicht übersetzt. Zusätzlich erlaubt die bestehende RLS-Policy das Lesen eigener bestehender Dialoge unabhängig von aktueller Freigabe oder Mitgliedschaft. Fremde Sitzungen werden mit 404 abgewiesen; private Rollen- und Lernzieltexte werden nicht ausgeliefert. Das Verhalten wurde als Bestand charakterisiert und im Schuldenregister erfasst. Fehlerübersetzung und die Abgrenzung zwischen aktiver Bearbeitung und Zugriff auf erhaltene eigene Arbeit sind noch zu klären beziehungsweise umzusetzen; dieses Refactoring gibt sie nicht als erledigt aus. Keine stillschweigende Änderung der Datenbankregeln oder Abschwächung eines bestehenden Tests.

### Verbleibender Umfang

Paket 1 ist für Upload-Freigaben umgesetzt; die noch vorhandene globale Speicherinitialisierung anderer Verbraucher gehört weiter zur Backend-Migration. Paket 5 ist implementiert und einschließlich Gesamtlauf verifiziert. Pakete 2 und 3 sind substantiell vorangekommen, aber nicht insgesamt abgeschlossen: übrige Teaching-/Learning-/BFF-Provider, Abgabe-Persistenzverdrahtung, Upload-/Abgabe-Speicherverbraucher, gemeinsame Authentifizierungshelfer und restliche Reparatur-Fixtures sowie weitere Worker-/Abgabephasen. Der Teaching-H5P-HTTP-Adapter ist ebenfalls noch nicht vollständig entkoppelt. Paket 4 und DSPy-Beratung wurden nicht implementiert.

### Kritische Durchsicht

- Die neuen Katalogabfragen besitzen jeweils eine eigene Verbindung wie die bisherigen Repository-Leseoperationen. Die konstante Abfragezahl bedeutet keine gemeinsame Snapshot-Transaktion. Eigentümerfilter und RLS-Kontext sind in beiden Batch-Abfragen vorhanden; leere Auswahlen öffnen keine Verbindung.
- Der gemeinsame Speicheraufbau erzeugt nur den Adapter und installiert keine Route-Abhängigkeiten. Die alte Initialisierung anderer Verbraucher wird nicht als entfernt ausgegeben. Fehler beim verzögerten Aufbau werden nicht zwischengespeichert; fehlende Konfiguration bleibt ein privater Verfügbarkeitsfehler.
- Dialog-Generatoren werden nicht über Anfragen geteilt. Der zustandslose Repository-Adapter hält keine offene Verbindung vor. Bestehende Authentifizierungs-/Cache-Helfer der Dialogrouten verwenden jedoch weiterhin die alte Fassade.
- Alle verschobenen H5P-Routenblöcke wurden zusätzlich textuell mit dem Ausgangsstand verglichen: unveränderte Inhalte in allen drei Bereichen. Die zusammengesetzte Reihenfolge und das neue Image-Packaging sind eigens getestet. Keine UI-/Graph-, OpenAPI-, Migrations-, Compose- oder ENV-Beispieldatei wurde geändert.
- Der echte Dialog-DB-Test verschweigt TD-010 nicht hinter einem Mock. Er ist eine Charakterisierung des Bestands und kein Nachweis, dass die vorhandene Zugriffsregel fachlich bereits freigegeben wäre.

### Gesamtnachweis dieser Etappe

- `PYTEST_ADDOPTS=-rs make verify` vollständig erfolgreich: **3035 Backend-Tests bestanden, 33 ausdrücklich deaktivierte Legacy-/Integrations-/historische E2E-Tests übersprungen**. Gegenüber F6j sind 38 zusätzliche Backend-Prüfungen aktiv; keine neuen bedingten DB-Skips.
- **688 Frontend-Tests, acht Tooling-Tests und 67 H5P-Tests bestanden**. Svelte ohne Fehler/Warnungen; Produktionsbuild mit bestehendem Warnungsgate grün. Import-/Architekturgrenzen, OpenAPI-Vertrag, Route-/DB-Inventare, Supply Chain, Ruff und Python-Image-Smoke erfolgreich.
- Zusätzlich `make docker-validate`, H5P-Image-Build und Router-Imports im isolierten Image erfolgreich. Kein Neustart der laufenden Installation, kein Datenreset, keine Migration und kein Push. Kein neuer Browserlauf: Die begründete Ausnahme für rein interne Änderungen steht unter Ziel und Grenzen.
- TD-009 ist erledigt. TD-004 und TD-010 sind weiterhin offene, konkret beschriebene Arbeiten. Der Abschluss dieser Etappe ist ausdrücklich kein Abschluss sämtlicher beauftragter Backend-Pakete.
