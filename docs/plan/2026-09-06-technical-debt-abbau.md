# Technische Schulden abbauen und das GUSTAV-Design verbindlich umsetzen

- Status: In Umsetzung
- Ausgangspunkt: `master`, `394d1964`; Untersuchung vom 5. September 2026.
- Auftrag: vollständige Bereinigung der betroffenen Route-Provider und Oberflächen, in einzeln nachgewiesenen Arbeitspaketen.

## Ziel und Entscheidungen

Als Produktverantwortlicher möchte ich Funktionen und Gestaltung zuverlässig ändern können, ohne globale Testzustände oder seitenspezifische Designsonderfälle berücksichtigen zu müssen. Als Lehrkraft und Lernender möchte ich vertraute Abläufe, verlässliche Daten und konsistente Bedienelemente behalten.

Das bestehende Design wird anhand von `docs/DESIGN.md` vereinheitlicht. Öffentliche API-Verträge, URLs, Berechtigungen, Entwurfsschlüssel und gespeicherte Nutzerdaten bleiben kompatibel. Schemaänderungen sind nicht vorgesehen; notwendige Vertragsänderungen erfolgen vor Tests und Implementierung. Historische Importwerkzeuge und Legacy-Code werden nicht allein wegen ihrer Größe umgebaut.

DSPy wird auf dem tatsächlich eingesetzten Stand einschließlich Abhängigkeiten vorläufig festgehalten. Versionswechsel, Optimizing, Prompts, Modelle und fachliche KI-Programme bleiben Gegenstand einer separaten Beratung. Ein Sicherheitskonflikt mit dieser Fixierung wird ausdrücklich dokumentiert und nicht durch ein beiläufiges Upgrade gelöst.

## Arbeitspakete

| Paket | Inhalt und Abschlusskriterium | Status |
| --- | --- | --- |
| A | Schuldenregister akzeptiert vollständige Einträge, prüft Verantwortlichkeit, Termine und Abschlusskriterien; aktuelle Scorecard und Ausgangsmessung | umgesetzt |
| B | Fehlerfester Docker-Build; hashgesicherte Python-Runtime-/Harness-Locks; vollständiges Inventar; drei unabhängige Online-Audits; Sicherheitsupdates getrennt nach Stack | technisch weitgehend umgesetzt; Sicherheitsabschluss blockiert |
| C | Zentrale Browser-/API-Testkontexte mit regulärer TLS-Prüfung; lokale CA; aktuelle, visuell geprüfte Referenzen und vollständiges UI-Labor | teilweise umgesetzt; UI-Labor noch nicht vollständig |
| D | Verbindliche gemeinsame UI-Bausteine und Varianten; zentrale Tokens; geordnete fachliche CSS-Importfassaden ohne Cascade Layers; ausführbare Designregeln | begonnen; vollständige Baustein-/CSS-Migration offen |
| E | Alle aktiven Oberflächen verwenden gemeinsame Bausteine; Learning-, Teaching-, Live-Controller, Aufgabenarten und Server-View-Models besitzen getrennte Verantwortung | ausstehend |
| F | Appbezogene typisierte Provider statt Route-Fassaden und Endpoint-Globals; isolierte Apps in Tests; Abgabe-/Workerphasen und H5P-Router entkoppelt | ausstehend |
| G | Gebündelte Live-Aufgabenabfrage mit didaktischer Reihenfolge; blockierende Adapterarbeit außerhalb des Event Loops; Abfragezahl und Nebenläufigkeit getestet | umgesetzt; verify-feature live-summary erfolgreich |
| H | Zentrale Ruff-Regeln E/F/I ohne E501; bereinigte Verstöße; vollständige Dokumentation und Abschlussnachweise | Lint umgesetzt; Gesamtabschlussnachweise bleiben offen |

### B: Build und Abhängigkeiten

Paketinstallation und Compilerbereinigung werden getrennt. `pip-tools` erzeugt vollständige Locks mit Hashes unter der produktiven Python-Version; Docker und Testumgebung installieren dieselben Runtime-Pins. Das Inventar wird an Locks statt nur installierte direkte Metadaten gebunden. `make dependency-audit` führt Frontend-, H5P- und Python-Audit vollständig aus und aggregiert den Fehlerstatus. `make verify` bleibt ohne externe Sicherheitsabfragen ausführbar. Sicherheitsupdates werden pro Stack mit Regressionstests durchgeführt; für unbehobene Upstream-Probleme gelten nachgewiesene Erreichbarkeit und kleine versionierte Patches statt pauschaler Unterdrückung. Ungeklärte Sicherheitsbefunde verhindern den Sicherheitsabschluss.

### C–E: Konsistente Gestaltung

Gemeinsame Aktionen/Aktionslinks, Formfelder, Seitenköpfe, Listenzeilen, Offenlegungen, Meldungen, Drawer und Bestätigungsdialoge erhalten dokumentierte Varianten und Zustände. Das UI-Labor verwendet diese echten Komponenten. Tokens haben genau einen Besitzer; Fachstyles werden nach Komponentenfamilien gegliedert und über geordnete Importfassaden geladen. Neue globale Tokendefinitionen, lokale Designfarben/-schriften und duplizierte UI-Muster werden geprüft; Fremdinhalte und fachliche Grafiken werden klar abgegrenzt. Historische Screenshots werden zunächst mit dem aktuellen Vertrag verglichen, nicht blind aktualisiert.

Migrationsreihenfolge: Shell/Primitives → Learning → Teaching → Live/Diagnostik → Profil/Auth/Kurs/Practice. Learning trennt Navigation/Wiederherstellung, Graph/Inhaltscache, Bearbeitung und Historie/Polling. Teaching trennt Auswahl/Viewport, Navigation, Entwürfe, Formulare und Dialoge. Live trennt Auswahl, Aktualisierung, Matrix und Details. Aufgabenkomponenten trennen Aufgabenarten, Bearbeitung und Ergebnisaktionen. Zustand bleibt instanzbezogen; URL, Scroll/Fokus, Entwürfe und montierte Editoren bleiben kompatibel. Server-Loader/Actions bleiben BFF-Adapter mit ausgelagerten reinen View-Models.

### F–G: Backend

Die App-Factory erhält ausdrücklich übergebbare typisierte Provider. Alle betroffenen Teaching-, Learning- und App/BFF-Routen werden migriert; Dienste konsumieren kleine frameworkunabhängige Ports. Globale Synchronisierungshelfer, Endpoint-`__globals__`-Änderungen und ausschließlich dafür erhaltene Aliase/Fixtures werden nach Migration entfernt. App-Isolation wird automatisiert geprüft.

Abgabe und Worker werden entlang vorhandener Phasen getrennt: fachliche Validierung, atomare Persistenz/Idempotenz, Kontext, externe Verarbeitung, Ergebnis/Retry. RLS, Sperren und Transaktionsgrenzen bleiben in den Adaptern. H5P wird in Authoring/Import, Player/Review und Ajax/Weiterleitung gegliedert, ohne die Reihenfolge der Sicherheitsgrenzen zu verändern.

Die Live-Zusammenfassung verwendet die bestehende gebündelte Aufgabenabfrage mit ausdrücklicher didaktischer Sortierung. Synchrone DB-Arbeit wird als zusammenhängender Serviceaufruf im Threadpool ausgeführt; Verbindungen werden dort geöffnet und geschlossen. Andere migrierte Async-Routen werden auf blockierende Adapterarbeit geprüft. Kein pauschaler Wechsel auf einen asynchronen DB-Treiber.

## BDD und Testzuordnung

| Given – When – Then | Automatisierter Nachweis |
| --- | --- |
| Vollständiger Schuldeneintrag – Prüfung – akzeptiert; fehlende Felder/ungültige Termine – abgelehnt | `test_tech_debt_inventory.py`, Harness-Vertrag |
| Fehlgeschlagene Paketinstallation oder falscher Hash – Build – Fehlerstatus | Packaging-Tests, Docker-Smoke |
| Zwei unterschiedlich verdrahtete Apps – abwechselnde Requests/Overrides – keine Vermischung | API-Isolationstests, gesamte Backend-Suite |
| Einheit mit 1, 20 oder leeren Abschnitten – Live-Zusammenfassung – korrekte Reihenfolge bei konstanter Aufgabenabfragezahl | API-/Repository-Tests mit lokaler DB |
| Wartender DB-Aufruf – unabhängiger Request – Event Loop bleibt frei | Synchronisierter Nebenläufigkeitstest |
| Lernender wechselt Aufgabe/Kontext/Verlauf und finalisiert – Zustand bleibt zugeordnet | `learner-navigation`, `learner-task-drafts`, `learner-reference-workspace`, `learner-task-finalization` |
| Lehrkraft bearbeitet erstes/letztes Modul, bricht ab oder erhält Speicherfehler – Arbeitskontext bleibt erhalten | Komponenten-/API-Tests, `teacher-graph-module-actions` |
| Beide Rollen, Light/Dark, verschiedene Breiten – gemeinsame Varianten/Fokus/Layout | neue `design-system-consistency`, bestehende Design-/Visualtests |
| H5P-Import, Schülerbearbeitung, Review, fehlerhafter Upload – Funktion und Berechtigungen erhalten | H5P-Tests, neue `h5p-authoring-review` |
| Fremder Kurs, entfernte Mitgliedschaft, abgelaufene Sitzung – Zugriff – bestehende Ablehnung | Auth-/RLS-/API-Tests, neue `live-summary` |

Neue Browser-Specs verwenden `@feature-acceptance` und den vollständigen authentifizierten lokalen Rundlauf. Visuelle Breiten: 390, 1024 und 1440 Pixel; Moduleditor zusätzlich 1920 Pixel. Relevante iPad-WebKit-Läufe ergänzen die Prüfung, ersetzen aber keinen historischen Safari.

## Durchführung und Gates

Jede Verhaltensänderung beginnt mit einem fehlschlagenden Test. Reine Extraktionen erhalten zuerst Charakterisierungstests. A und H besitzen keinen nutzerseitigen Ablauf; ihr Gate ist `make verify`. Dockeränderungen erfordern zusätzlich `make docker-validate`. Betroffene Oberflächenpakete erfordern vor Abschluss und Commit `make verify-feature FEATURE=<zugeordnete-spec>` und passende visuelle Nachweise. Vor Browserläufen: `make local-ca-status`. Testdaten gehören ausschließlich dem jeweiligen lokalen Lauf und werden durch die vorhandenen Fixtures aufgeräumt.

Kleine zusammenhängende Commits erfolgen auf `master`, ohne Push. Kein Paket gilt allein wegen sinkender Dateigröße als erledigt. Der Gesamtabschluss erfordert alle zugeordneten Gates, Backend-/Frontend-/H5P-Tests, Produktionsbuild, visuelle Prüfung und aktuelle Audits. Die historische Gesamtregression bleibt ausdrücklich opt-in. Offene externe Blocker bleiben sichtbar und werden nicht als erledigt gewertet.

## Umsetzungsnachweise

- 2026-09-06: Arbeitsbaum zu Beginn sauber; `master` per `git pull --ff-only` synchronisiert, bereits aktuell. Plan vor der ersten Codeänderung angelegt.
- A: Registervalidator und Scorecard-Zählung durch Red-Green-Tests abgesichert; vollständige Einträge, überfällige Termine, Abschlussnachweise und verwaiste Tabellenzeilen werden geprüft. September-Ausgangsmessung erstellt; dort noch nicht ausgeführte Gates sind ausdrücklich als solche ausgewiesen.
- B: Docker-Installationsfehler werden nicht mehr verschluckt (ausgeführte Shell-Regressionstests). Frontend-Pins aktualisiert: aktueller npm-Audit ohne Meldungen; 680 Vitest-Tests, zwei Tooling-Tests, Typprüfung und Build erfolgreich. H5P-Pins aktualisiert; 16 Testdateien erfolgreich, Audit enthält weiterhin drei hohe Meldungen in der ungepatchten `image-size`-Abhängigkeitskette.
- B: Tatsächlich laufender Worker verwendet DSPy 3.3.1, während die vorherige lokale Testumgebung 3.2.1 enthielt. Vorläufige Baseline mit 59 DSPy-Abhängigkeiten erfasst. Audit des vorherigen vollständigen Worker-Paketstands: 79 Meldungen in 14 Paketen, einschließlich installierter Buildwerkzeuge. Sicherheitsupdates außerhalb dieser Baseline vorbereitet; Hash-Locks und Gesamtverifikation laufen noch. Meldungen in eingefrorenen gemeinsamen Abhängigkeiten sind damit nicht freigegeben.
- C: Reguläre TLS-Prüfung über zentrale Browser-/API-Testkontexte abgesichert; lokale Caddy-CA wird vertraut. Interaktive Browser-Skill-Verbindung scheitert an einem fehlenden Plugin-Bestandteil. Projekt-Playwright-Browser mussten neu installiert werden; der Design-Referenzlauf ist noch nicht abgeschlossen. Keine Referenzbilder ungeprüft ersetzt.
- G: Neue echte DB-Regressionstests mit 0, 1 und 20 Abschnitten wurden zuerst rot, dann grün: einmalige gebündelte Aufgabenabfrage, leere Abschnitte, mehrere Aufgaben und didaktische Reihenfolge unabhängig von Adapterreihenfolge. Synchronisierter Nebenläufigkeitstest zuerst rot, dann grün; zusammenhängende Summary-Arbeit läuft im begrenzten Threadpool. 37 Summary-/Readiness-/Route-Split-Tests erfolgreich. Frameworkunabhängige Gesamtdienst-Extraktion, Browsernachweis und vollständiges Gate sind noch ausstehend.

### Verifizierter Zwischenstand

- Abschließendes `make verify-feature FEATURE=live-summary` erfolgreich: 2.624 Backend-Tests, 683 Frontend-Tests, acht Frontend-Tooling-Tests, 62 H5P-Tests, alle Teilgates, Produktionsbuild und der echte Live-Browserrundlauf. Danach zusätzlich sieben Supply-Chain-Tests einschließlich einer neuen Regression für verschachtelte Requirement-Quellen sowie `supply-chain-check` und Ruff erfolgreich. API-Vertrag und Datenbankschema wurden nicht geändert.
- `make verify-feature FEATURE=design-system-consistency` erfolgreich: 2.619 Backend-Tests, 683 Frontend-Tests, acht Frontend-Tooling-Tests, 62 H5P-Tests, Typprüfung, Produktionsbuild, Offline-Inventar, Architektur-/API-/Routenprüfungen und Docker-Image-Smoke. 78 explizit ausgeschlossene Backend-Tests bleiben ausgewiesen; dies ist keine Ausführung der opt-in-Gesamtregression.
- Gezielte authentifizierte Browserprüfungen `live-summary` und `dialog-task-learning` erfolgreich. Die neue Live-Spec prüft drei Aufgaben aus mehreren Abschnitten, Wiederherstellung der letzten Auswahl und die Ablehnung eines Lernenden am Lehrkraft-Endpunkt. Die Design-Spec prüft zwei Rollen sowie Entwurfserhalt nach Theme-, Breitenwechsel und Neuladen.
- Drei Design-Detailtests mit 18 Referenzbildern in Light/Dark bei 390, 1024 und 1440 Pixeln erfolgreich; erzeugte Dialogbilder visuell geprüft und anschließend ohne Update erneut verglichen. Testbedingtes Scrollen vor der Aufnahme wurde korrigiert. Das UI-Labor verwendet echte Dialognachrichten, Aufgaben-/Kontextflächen und Spaltentrenner; übrige Laborkopien bleiben Gegenstand von C–E.
- Hashabweichung mit echtem pip offline nachgewiesen: manipuliertes Test-Wheel wird beim Dry-Run verworfen, ohne Installation oder Registryzugriff. `make docker-validate` erfolgreich.
- Wiederholte Monatsmessungen vergleichen jetzt ausschließlich mit älteren Monaten. Neu erzeugte Prüfkommandos verwenden relative Repository-Pfade. Beide Änderungen durch Red-Green-Tests abgesichert.
- Der Vergleich laufender Dienste zeigte zunächst 107 identische Runtime-Pins und drei zusätzliche alte Basisimage-Werkzeuge. Daraufhin wurden pip, setuptools und wheel explizit aufgenommen. Finaler Build und Vergleich erfolgreich: Web und Worker enthalten jeweils exakt alle 110 Runtime-Pins, ohne abweichende Versionen oder zusätzliche Python-Pakete. Der erneute Audit bleibt bei null Frontend-, drei hohen H5P-Einträgen und 19 Python-Meldungen in sechs Paketen.

### Sicherheitsbefunde und Entscheidungsgrenze

Der Audit vom 6. September nach den Python-Sicherheitsupdates meldet für das Frontend null Befunde, für H5P drei hohe npm-Einträge und für Python 19 Meldungen in sechs Paketen. Die Python-Ausgabe enthält einen doppelten Eintrag für `PYSEC-2026-388`; die Zahl bezeichnet Meldungen, nicht 19 unterschiedliche Schwachstellen. Die H5P-Zahl enthält die Weitergabe über zwei abhängige Lumi-Pakete, nicht drei unabhängige Parserfehler.

| Paket/Gruppe | Verbleibender Befund | Nächste notwendige Entscheidung/Arbeit |
| --- | --- | --- |
| jinja2 3.1.4, requests 2.32.3, python-dotenv 1.0.1, litellm 1.83.0 | Audit nennt korrigierte Versionen; Pakete gehören zur vorläufig fixierten DSPy-Abhängigkeitsmenge | Sicherheitsausnahmen von der Fixierung separat beraten und mit KI-Regressionstests belegen; hier kein stilles Upgrade |
| diskcache 5.6.3 | Audit nennt keine korrigierte Version; Teil der DSPy-Fixierung | Erreichbarkeit und Mitigation separat untersuchen |
| ecdsa 0.19.2 | Audit nennt keine korrigierte Version; transitive JOSE-Abhängigkeit außerhalb der DSPy-Fixierung | Tatsächlich verwendete Algorithmen/Backends prüfen und anschließend Mitigation oder Abhängigkeitsablösung planen |
| image-size über Lumi H5P | Keine korrigierte Version im npm-Audit; Endlosschleifen in ICNS sowie JXL/HEIF | Erreichbare Upload-/Importpfade prüfen und kleinen getesteten Patch oder sicheren Ersatz erarbeiten |

Upstream-Nachweise für H5P: [ICNS](https://github.com/advisories/GHSA-w3rx-r6r6-pgpr), [JXL/HEIF](https://github.com/advisories/GHSA-5p2g-fcmc-qvqq). Die Meldungen wurden weder unterdrückt noch als akzeptiertes Risiko geschlossen. Ein grünes funktionales Gate ersetzt diesen Sicherheitsabschluss nicht. Die vorläufige DSPy-Baseline bleibt eine Kompatibilitätsentscheidung, keine Sicherheitsfreigabe.

### Weiterhin offen

E und F sind nicht umgesetzt: vollständige Seiten-/Controller-/View-Model-Migration, appbezogene typisierte Provider einschließlich Entfernung der Reparatur-Fixtures, Abgabe-/Workerphasen sowie H5P-Routertrennung. D enthält bisher nur zentrale globale Tokenprüfung und die gemeinsame Dialognachricht; gemeinsame Aktions-/Formvarianten, vollständige Seitennutzung und fachliche CSS-Importfassaden fehlen. C besitzt geprüfte Designreferenzen, aber noch kein vollständiges UI-Labor. Die vorgesehenen H5P-Authoring-/Review- und zusätzlichen iPad-WebKit-Nachweise gehören zu den jeweiligen noch offenen Paketen. Der Gesamtplan ist deshalb ausdrücklich nicht abgeschlossen.
