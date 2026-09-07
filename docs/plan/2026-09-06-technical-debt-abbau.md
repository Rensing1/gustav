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
| F | Appbezogene typisierte Provider statt Route-Fassaden und Endpoint-Globals; isolierte Apps in Tests; Abgabe-/Workerphasen und H5P-Router entkoppelt | begonnen: Profil-/CLI-, Kummerkasten-, Lernenden-Kurs- und Lehrer-Katalog- und Inhaltseditorprovider migriert; Gesamtmigration offen |
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

E und der größte Teil von F sind noch offen: vollständige Seiten-/Controller-/View-Model-Migration, übrige appbezogene Provider einschließlich Entfernung der Reparatur-Fixtures, Abgabe-/Workerphasen sowie H5P-Routertrennung. F1 migriert Profil und CLI-Verwaltung, F2 den Kummerkasten, F3 die Lernenden-Kursübersicht, F4 Lehrer-Startseite und Lerneinheitenkatalog, F5 den Inhaltseditor (siehe unten). D enthält bisher nur zentrale globale Tokenprüfung und die gemeinsame Dialognachricht; gemeinsame Aktions-/Formvarianten, vollständige Seitennutzung und fachliche CSS-Importfassaden fehlen. C besitzt geprüfte Designreferenzen, aber noch kein vollständiges UI-Labor. Die vorgesehenen H5P-Authoring-/Review- und zusätzlichen iPad-WebKit-Nachweise gehören zu den jeweiligen noch offenen Paketen. Der Gesamtplan ist deshalb ausdrücklich nicht abgeschlossen.

### F1: Appbezogene Profil-Provider (7. September 2026)

Als Entwickler möchte ich zwei Apps mit unterschiedlichen Identitätsadaptern betreiben und testen können, ohne dass Profilzugriffe die Abhängigkeiten der anderen App verwenden. Als angemeldeter Benutzer behalte ich meine Profilfelder und die bestehende 180-Tage-Namenssperre; CLI-Tokens bleiben ausschließlich ihrer Lehrkraft zugeordnet.

1. Charakterisierungs- und Isolationstests zuerst: abwechselnde Profilzugriffe zweier Apps, getrennte Schreibzugriffe und Claims, fehlende Anmeldung, gesperrte Namen und unveränderte partielle Identity-Updates.
2. Kleine typisierte Identity- und Token-Ports; Profilregeln und Normalisierung in `identity_access`; explizite Profil-Provider an der App-Factory. Keine dynamischen Rückgriffe auf `routes.app`, keine neuen globalen Synchronisierungshelfer. CLI-Verwaltung verwendet denselben appbezogenen Store wie die Authentifizierung.
3. Alle sechs Profil-/CLI-Handler migrieren. Synchrone externe Arbeit im Threadpool ausführen; mit einem wartenden Adapter und einem unabhängigen Request nachweisen. Überholte Profil-Fassaden und zugehörige Alias-Vertragstests entfernen bzw. durch Ownership-Tests ersetzen.
4. Nachweise: gezielte Profil-/CLI-/Kompositions- und Architekturtests, `make verify-feature FEATURE=profile-cli-token-role` einschließlich regulärem `make verify`; vor Browserprüfung `make local-ca-status`. Der authentifizierte Browsertest prüft Anzeigename, Vor-/Nachname, Persistenz nach Neuladen und Namenssperre für Lernende; ein Lehrkraft-Test ergänzt Token-Erzeugung, Auflistung und Widerruf über die echte Oberfläche und persistente lokale Datenhaltung.

BDD-Zuordnung: Zwei Apps → abwechselnd lesen/schreiben → isolierte Adapter und Claims (`test_profile_provider_isolation.py`); wartender Adapter → Shell-Request → freie Ereignisschleife (dieselbe Datei); Sperre/Attributerhalt/ungültige Eingaben/fehlende Berechtigung → Profil-API → unveränderte Statuscodes und Daten (`test_profile_view_api.py`); Lehrkraft und Lernender → echte Profiloberfläche → erlaubter Token-Lebenszyklus bzw. keine Token-Verwaltung (`profile-cli-token-role.spec.ts`).

Vorprüfung: Die bestehenden Profilverträge in `api/openapi.yml`, die CLI-Token-Migration mit RLS und die etablierten ENV-Namen bleiben gültig. Keine Vertrags-, Schema-, ENV- oder DSPy-Änderung erforderlich. Dieser Schritt ist eine abgeschlossene Teilmigration von F, nicht der Abschluss aller Backend-Provider; Teaching/Learning, übrige BFF-Routen und ihre Reparatur-Fixtures bleiben anschließend offen.

#### Im Browser entdeckte Konfigurationsschuld

Die zusätzliche echte Namensänderung speichert Vor-/Nachname, aber nicht die Sperre. Die bestehende Realm-Vorlage und ein lesender Abruf der aktiven lokalen User-Profile-Konfiguration bestätigen: `name_locked_until` ist nicht deklariert; unverwaltete Attribute sind nicht freigegeben. Keycloak verwirft damit das Sperrfeld. Der Fehler bestand bereits vor der Provider-Extraktion und war durch Adapter-Mocks verdeckt.

Reparatur vor Abschluss von F1: zuerst einen roten Realm-Vertragstest für genau dieses Attribut schreiben; anschließend das optionale, ausschließlich für Administratoren les-/schreibbare Attribut in der Realm-Vorlage deklarieren. Im vorhandenen lokalen Realm dieselbe einzelne Deklaration per Admin-API ergänzen, alle anderen Profilregeln unverändert erhalten und den Wert zurücklesen. Kein Realm-Reset, kein Benutzer-Reimport, keine pauschale Freigabe unverwalteter Attribute. Bestehende Installationen benötigen dieselbe Konfigurationsübernahme; die Vorlage allein betrifft nur neu importierte Realms. Zusätzliche Gates: Realm-Tests und `make docker-validate`. Der zuvor rote authentifizierte Profilrundlauf muss anschließend Namenspersistenz und wirksame Sperre nach Neuladen belegen. Beide Rollen bilden wegen des vorhandenen Harness-Vertrags genau ein Acceptance-Szenario pro Spec.

Grundlage: [Keycloak User Profile](https://www.keycloak.org/docs/latest/server_admin/index.html#user-profile) beschreibt explizit verwaltete Attribute und die standardmäßige Ablehnung unverwalteter Attribute.

#### Abschlussnachweis F1

- Ausgangspunkt: sauberer `master` auf `64bbf090`, vor Arbeitsbeginn per Fast-Forward synchronisiert. Die bisherigen 17 Profil-/Normalisierungstests waren vor der Extraktion grün; die neuen Provider-/Factory-Isolationstests zunächst rot.
- Profilregeln und Normalisierung sind in `identity_access` verlagert. Die sechs Profil-/CLI-Handler haben keine dynamischen Fassadenrückgriffe mehr. Profiltests erzeugen eigene Apps mit ausdrücklich verdrahteter Authentifizierung statt globale Main-/Route-Helfer zu überschreiben. Die anderen Bereiche benötigen ihre bisherigen Reparatur-Fixtures weiterhin.
- Separate Zwei-App-Tests sichern Identitätsadapter, Schreibzugriffe, verifizierte Ersatz-Claims und Token-Stores. Ein synchronisierter Warte-Test belegt, dass der Identity-Adapter den Event Loop nicht blockiert. Der neue `db_write`-Test prüft Token-Erzeugung, echte Verifikation, Metadaten ohne Geheimnisse, fremde Eigentümerschaft und Widerruf gegen die vorhandene lokale DB; er löscht ausschließlich seine eigenen Testzeilen. Das DB-Testinventar ist aktualisiert.
- Die Namenssperre war im erweiterten Browsertest und im neuen Realm-Vertrag zuerst rot. Nach Ergänzung der adminverwalteten Deklaration in Vorlage und lokalem Realm ist der echte Profilrundlauf grün. Keycloak ergänzt beim Zurücklesen den Standard `multivalued: false`; dieser ist auch in der Vorlage ausdrücklich gesetzt. Der semantische Vorlagenvergleich bestätigt, dass alle bisherigen Attribute und übrigen Realm-Einstellungen unverändert sind. Web- und Keycloak-Image wurden neu gebaut; bestehende Benutzer und Realm-Daten blieben erhalten.
- Abschließendes `make verify-feature FEATURE=profile-cli-token-role` erfolgreich: **2.641 Backend-Tests**, 78 ausgewiesene Skips, **683 Frontend-Tests**, acht Frontend-Tooling-Tests, **62 H5P-Tests**, Typprüfung ohne Fehler/Warnungen, Produktionsbuild, Architektur-/Import-/API-/Routen-/Inventarprüfungen, Docker-Image-Smoke und ein authentifizierter Profilrundlauf für beide Rollen. Der Rundlauf prüft alle sechs migrierten Handler, Persistenz nach Neuladen und die wirksame Namenssperre. Die Bereinigung aller lauf-eigenen Konten und Produktdaten ist bestätigt.
- `make local-ca-status` und `make docker-validate` erfolgreich. API-Vertrag, PostgreSQL-Schema, ENV-Beispiel, Python-Locks und DSPy-Fixierung sind unverändert. Keine historische opt-in-Gesamtregression ausgeführt.

F1 ist damit abgeschlossen. Für bestehende andere Installationen bleibt die Übernahme derselben einzelnen Keycloak-Profildeklaration ein notwendiger Deployment-Schritt; ein Push oder Zugriff auf eine entfernte Installation fand nicht statt. F insgesamt sowie C–E und der Sicherheitsabschluss bleiben wie oben beschrieben offen.

### F2: Appbezogener Kummerkasten

Als Lernender möchte ich einen Hinweis weiterhin nur an meine eigene Kurslehrkraft senden und selbst wählen, ob mein Name sichtbar ist. Als Lehrkraft möchte ich ausschließlich Hinweise meiner Kurse lesen, archivieren und wiederherstellen. Als Entwickler möchte ich diese Abläufe mit getrennt verdrahteten Apps prüfen können, ohne globale Routen- oder Repository-Zustände zu überschreiben.

Die fünf Kummerkasten-Endpunkte erhalten einen gemeinsamen fokussierten Router und explizite appbezogene Repository-/Namensprovider. Die fachliche Projektion und Mitgliedschaftsprüfung werden hinter kleine frameworkunabhängige Ports verschoben. Der Produktionsprovider erzeugt den vorhandenen RLS-Repository-Adapter verzögert und appbezogen; DB-Verbindungen bleiben in den vorhandenen Adapteroperationen. Die synchrone Arbeit läuft im begrenzten Threadpool. Die bisherigen Home-Routen bleiben zunächst in ihren Modulen; ausschließlich Kummerkasten-Aliase und dynamische Rückgriffe entfallen. Die kanonische Namensauflösung wird ohne Verhaltensänderung in Identity & Access geteilt.

| Given – When – Then | Nachweis |
| --- | --- |
| Zwei Apps mit getrennten Repositories – abwechselnd lesen/senden/archivieren/wiederherstellen – keine Vermischung | neue Provider-Isolationstests |
| Anonyme und benannte Hinweise – Posteingang laden – Namensauflösung nur für benannte Hinweise, keine Subject-IDs in der Antwort | Service-/API-Tests |
| Fremder Kurs oder fremde Lehrkraft – senden/archivieren/wiederherstellen – unveränderte Ablehnung und unveränderte gespeicherte Daten | echte lokale DB-Tests |
| Fehlende Rolle, Anmeldung, Same-Origin-Nachweis oder ungültige ID – Mutation – Ablehnung vor Adapterzugriff | API-Tests |
| Wartender Repository-Aufruf – unabhängigen Shell-Request ausführen – Event Loop bleibt frei | synchronisierter Nebenläufigkeitstest |
| Authentifizierter Lernender und Lehrkraft – Hinweis senden, lesen, archivieren und wiederherstellen – Zustand bleibt nach Neuladen erhalten | `concern-box-lifecycle` mit genau einem `@feature-acceptance`-Szenario |

Vorprüfung: OpenAPI-Endpunkte und bestehende Kummerkasten-Migrationen einschließlich RLS und atomarer Mitgliedschaftsprüfung bleiben unverändert. Keine Schema-, API-, ENV-, Keycloak- oder DSPy-Änderung vorgesehen. Tests werden zuerst geschrieben; vorhandene API-Tests werden auf frische Apps und explizite Testdatenbereinigung umgestellt. Gate vor Abschluss und Commit: `make verify-feature FEATURE=concern-box-lifecycle`, davor `make local-ca-status` und Neubau des lokalen Webdienstes. Keine historische Gesamtregression und kein Reset fremder Daten.

#### Umsetzung und Zwischenprüfung F2

- Ausgangspunkt: sauberer, per Fast-Forward synchronisierter `master` auf `30b00a1a`. Die ersten neuen Isolationstests waren wegen des noch fehlenden Providers rot; nach der Extraktion sind die gezielten API-/Isolations-/Namens-/Routerprüfungen grün.
- Der neue Dienst kennt kein FastAPI. Die vorhandene Repository-Implementierung behält die atomare Mitgliedschaftsprüfung und Eigentümer-RLS. Der appbezogene Standardprovider initialisiert verzögert, behandelt Initialisierungsfehler als private 503-Antwort und erlaubt einen erneuten Versuch. Namensauflösung erfolgt gebündelt und ausschließlich für benannte Beiträge.
- Die bisherigen Kummerkasten-API-Tests verwenden frische Apps und löschen ausschließlich selbst angelegte Kurse samt abhängigen Testbeiträgen. Das DB-Inventar erfasst diese Tests nun ausdrücklich als `db_write`; Route-Inventar und öffentliche API bleiben unverändert.
- Der neue authentifizierte Browserrundlauf prüft getrennte Rollen/Sitzungen, anonymes und benanntes Senden sowie Archivierung und Wiederherstellung einschließlich Neuladen. Die ersten Läufe korrigierten einen zu strengen Label-Selektor und ein Neuladen vor abgeschlossener Navigation im neuen Test; Produkt-UI und Authentifizierung wurden nicht geändert. Der gezielte Rundlauf ist anschließend grün, die Bereinigung seiner Testkonten und Daten bestätigt.
- Kritische Durchsicht: HTTP-Rollen-/CSRF-Prüfungen bleiben im Router, Datensichtbarkeit im fachlichen Dienst und RLS im DB-Adapter. Die bestehende statische Namensfunktion bleibt nur für noch nicht migrierte Teaching-Aufrufer als Alias erhalten. Die Home-Routen wurden bewusst nicht mitverschoben; ihre Provider-Migration bleibt ein eigenes Arbeitspaket.

#### Abschlussnachweis F2

- `make local-ca-status`: aktuelle lokale CA in System, Chromium/Codex und Firefox vertraut. `docker compose up -d --build web`: lokaler Webdienst erfolgreich neu gebaut und gestartet.
- `make verify` und anschließend das vollständige `make verify-feature FEATURE=concern-box-lifecycle`: erfolgreich. Abschlusslauf: **2659 Backend-Tests bestanden, 78 vorgesehen übersprungen; 683 Frontend-Tests, 8 Tooling-Tests und 62 H5P-Tests bestanden; 1 authentifizierter Browserrundlauf bestanden**. Die Feature-Bereinigung bestätigt, dass keine laufbezogenen Konten oder Daten zurückbleiben.
- Svelte-Prüfung ohne Fehler/Warnungen; Produktionsbuild mit ausschließlich den dokumentierten Upstream-Ausnahmen. Import-/Architekturgrenzen, API-Vertrag, Route-/DB-Inventar, Supply Chain, Ruff und Image-Smoke grün. `git diff --check` ohne Befund.

F2 ist abgeschlossen; F insgesamt, die noch offenen Frontend-/Worker-/H5P-Pakete und der Sicherheitsabschluss bleiben offen. API, Schema, ENV, Keycloak und DSPy wurden in diesem Teilpaket nicht verändert. Kein Zugriff auf eine entfernte Installation und kein Push.

### F3: Expliziter Datenzugang der Kursübersicht für Lernende

Als Lernender möchte ich auf meiner Startseite weiterhin meine aktuellen und vergangenen Kurse sehen und die freigegebenen Lerneinheiten meiner Kurse erreichen. Als Entwickler möchte ich für diese Leseabläufe gezielt ein Test-Repository übergeben können, ohne globale Learning-Repositories oder App-Helfer zu überschreiben. GUSTAV bleibt eine zusammenhängende Plattform mit einer Installation je Dev-/Prod-System; mehrere Test-Anwendungsobjekte dienen ausschließlich dem Nachweis, dass Testdaten und Einstellungen sich nicht gegenseitig beeinflussen.

Umfang: drei GET-Endpunkte (`/api/learning/views/learner-home`, `/api/learning/courses`, `/api/learning/courses/{course_id}/units`). Ein expliziter appbezogener Kurs-Provider verwendet den bestehenden DBLearningRepo und die vorhandenen Kurs-Anwendungsfälle. Die Home-Projektion wandert in einen frameworkunabhängigen Anwendungsfall. Synchrone Handler führen DB-Arbeit im begrenzten Threadpool aus. Überholte Home-Aliase und die beiden Kurs-Handler in der Learning-Fassade entfallen; die übrigen Learning-Endpunkte bleiben zunächst unverändert. Die Lehrer-Startseite benötigt die gesonderte Entkopplung des Lerneinheitenkatalogs und gehört nicht zu F3.

| Given – When – Then | Automatisierter Nachweis |
| --- | --- |
| Zwei getrennt vorbereitete Test-Anwendungsobjekte mit unterschiedlichen Kurs-Repositories – abwechselnd Home/Kurse/Lerneinheiten laden – keine gegenseitige Beeinflussung | `test_learning_course_provider_isolation.py` |
| Aktuelle/vergangene/leere Kurslisten und extreme Seitengrößen – laden – unveränderte Links, Projektion und Begrenzung | Provider-/Use-Case-Tests |
| Fehlende Anmeldung, falsche Rolle oder ungültige Kurs-ID – lesen – 401/403/400 vor Repositoryzugriff | Provider-/API-Tests |
| Fremder oder nach Austritt nicht mehr zugänglicher Kurs – Lerneinheiten lesen – unverändert 404, kein Existenzleck | echte DB-Tests in `test_learning_my_courses_api.py` |
| Wartender Kursadapter – unabhängiger Shell-Request – Event Loop bleibt frei | synchronisierter Isolationstest |
| Authentifizierte Lehrkraft und Lernender – Kurs öffnen, archivieren, Startseite neu laden – aktuelle und vergangene Kurse bleiben richtig getrennt | `learner-course-overview.spec.ts`, genau ein `@feature-acceptance`-Szenario |

Vorprüfung: Die drei OpenAPI-Verträge und die Kursarchiv-/Mitgliedschaftsmigrationen bleiben unverändert; dieselben ENV-Namen und DB-Adapter gelten lokal und produktiv. Keine Schema-, API-, DSPy-, KI- oder UI-Änderung vorgesehen. Tests zuerst (Red-Green-Refactor), gezielte API-Tests auf frische Apps und laufbezogene Bereinigung umstellen. Vor Abschluss: lokale CA prüfen, Webdienst neu bauen, `make verify-feature FEATURE=learner-course-overview` erfolgreich ausführen. Keine historische Gesamtsuite, kein Reset bestehender Konten, kein Push.

#### Umsetzung und gezielte Nachweise F3

- Fortgesetzt vom unveränderten Produktstand `5370878e`: Vor der Unterbrechung waren nur Plan und neue Tests geschrieben. Der neue Provider-Test war vor Implementierung wegen fehlender Verdrahtung rot; anschließend wurden die drei Lese-Handler umgestellt.
- Die neue Verdrahtung besitzt nur einen Repository-Zugang. `ListCoursesUseCase` und `ListCourseUnitsUseCase` bleiben unverändert; `LearnerHomeUseCase` übernimmt lediglich die bisher im Web-Handler verschachtelte Projektion. Es entstehen keine zusätzlichen Dienste, Datenbanken oder Konfigurationsvariablen.
- Die Kurs-API-Tests benötigen keinen globalen Session-Store-Austausch mehr. Sie erzeugen ihre eigene Authentifizierung und bereinigen ausschließlich selbst erzeugte Kurse und Lerneinheiten. Die Home-Tests übergeben ihr Test-Repository ausdrücklich. Globale Reparatur-Fixtures bleiben für noch nicht migrierte Bereiche bestehen, werden von diesen drei Handlern aber nicht benötigt.
- 47 gezielte Home-/Provider-/Kurs-/Modul-/Repository-Tests erfolgreich, einschließlich echter DB-Nachweise für Reihenfolge, Archivierung, beendete Mitgliedschaft und identische 404-Antworten für fremde und unbekannte Kurse.
- Authentifizierter Browserrundlauf `learner-course-overview` erfolgreich: leere Startseite, Kurs-/Lerneinheitennavigation, Archivierung durch die Lehrkraft, aktuelle/vergangene Kurslisten und Archivlinks nach Neuladen. Im neuen Test wurden die bereits bestehende Weiterleitung ins Lehrerarchiv und der Schuljahr-Zusatz in Archivlinks berücksichtigt; keine Produkt-UI geändert. Laufbezogene Testdatenbereinigung bestätigt.
- Kritische Durchsicht: Rollenprüfung und HTTP-Statuscodes bleiben im Adapter, Seitengrößen im bestehenden Anwendungsfall, Kurs-/Archivsichtbarkeit im bestehenden RLS-Repository. Keine zusätzlichen Abfragen pro Kurs; die Startseite liest weiterhin jeweils eine begrenzte aktuelle und vergangene Kursliste. Das vorhandene Fehlerverhalten bleibt unverändert, ohne stillen Rückfall auf ein globales Repository.

#### Abschlussnachweis F3

- `make local-ca-status`: lokale CA in System, Chromium/Codex und Firefox vertraut. `docker compose up -d --build web`: lokaler Webdienst erfolgreich neu gebaut und gestartet.
- `make verify-feature FEATURE=learner-course-overview` vollständig erfolgreich: **2672 Backend-Tests bestanden, 78 vorgesehen übersprungen; 683 Frontend-Tests, 8 Tooling-Tests, 62 H5P-Tests und 1 authentifizierter Browserrundlauf bestanden**. Die anschließende Feature-Bereinigung bestätigt, dass keine laufbezogenen Konten oder Daten zurückbleiben.
- Svelte-Prüfung ohne Fehler/Warnungen; Produktionsbuild mit ausschließlich den dokumentierten Upstream-Ausnahmen. Import-/Architekturgrenzen, API-Vertrag, Route-/DB-Inventar, Supply Chain, Ruff und Image-Smoke grün. `git diff --check` ohne Befund.

F3 ist abgeschlossen. Die übrige Provider-Migration einschließlich Lehrer-Startseite, weitere Frontend-/Worker-/H5P-Arbeitspakete und der Sicherheitsabschluss bleiben offen. Keine API-, Schema-, ENV-, UI- oder DSPy-Änderung; kein zusätzlicher Dienst, keine zusätzliche Datenbank und kein Push.

### F4: Gemeinsame Regeln für Lehrer-Startseite und Lerneinheitenkatalog

Als Lehrkraft möchte ich auf der Startseite weiterhin meine Kurse und die drei zuletzt bearbeiteten Lerneinheiten finden. Der Katalog soll dieselbe Bearbeitungsreihenfolge, Suchfunktion, Kurszuordnung und Statusanzeige behalten. Als Entwickler möchte ich beide Lesewege mit gezielt übergebenen Testdaten prüfen können, ohne gemeinsame Web-Module umzuschreiben.

Umfang: `GET /api/teaching/views/teacher-home` und `GET /api/teaching/views/units/catalog`. Ein gemeinsamer frameworkunabhängiger Katalogdienst hinter vier eigentümergebundenen Repository-Operationen übernimmt die bisherigen Projektionen. Ein kleiner expliziter Provider verwendet den vorhandenen DBTeachingRepo; beide HTTP-Handler laufen synchron im begrenzten Threadpool. Der Katalog-Handler erhält ein fokussiertes Modul; tote Katalog-/Home-Aliase entfallen. Workspace-/Editor-Routen und ihre noch benötigten Helfer bleiben unverändert. Keine zusätzlichen Dienste oder Datenbanken; GUSTAV bleibt eine Plattform.

| Given – When – Then | Nachweis |
| --- | --- |
| Getrennt vorbereitete Test-Anwendungsobjekte – Home/Katalog abwechselnd laden – ausschließlich die übergebenen Repositorydaten | `test_teacher_catalog_provider_isolation.py` |
| Entwurf, bearbeitete und kursgebundene Einheit – Katalog laden – unveränderte Statuslabels, Kurslinks und Reihenfolge einschließlich Abschnittsänderungen | Service-/API-Tests |
| Mehr als drei Einheiten, leere Listen und Such-/Sortierparameter – Home/Katalog laden – Begrenzung, leere Zustände und Filter unverändert | Service-/API-Tests |
| Fehlende Anmeldung oder Schülerrolle – laden – 401/403 vor Adapterzugriff; Adapterausfall – private 503-Antwort | Isolationstests |
| Eigene und fremde Inhalte – eigene Home-/Katalogansicht – nur eigene Kurse und Einheiten | echte DB-Tests in `test_teaching_units_catalog_view_api.py` |
| Wartender DB-Zugang – unabhängiger Shell-Request – Event Loop bleibt frei | synchronisierter Isolationstest |
| Echte Lehrkraft – von Home zu Live/Editor/Katalog wechseln, suchen und neu laden – Zuordnung und Anzeige bleiben erhalten | erweitertes `teacher-home-workstarter.spec.ts` mit genau einem `@feature-acceptance`-Szenario |

Vorprüfung: Die beiden vorhandenen OpenAPI-Verträge einschließlich 503 bleiben gültig. Bestehende Kurs-/Einheiten-/Abschnitts-RLS und ENV-Namen bleiben unverändert; keine Migration, UI-, KI- oder DSPy-Änderung. Tests zuerst, bestehende Katalogtests auf frische Authentifizierung und echte DB mit gezielter Datenbereinigung umstellen. Gate: lokale CA prüfen, lokalen Webdienst neu bauen, `make verify-feature FEATURE=teacher-home-workstarter`. Kein Push.

Bewusste Grenze: Die vorhandene begrenzte Katalogabfrage lädt weiterhin Kurszuordnungen pro Kurs und Abschnitte pro Einheit. F4 beseitigt keine N+1-Struktur und ändert die bisherigen 200er-Anforderungen/Adaptergrenzen nicht stillschweigend. Eine spätere gebündelte Katalogabfrage benötigt eigene DB-Paritäts-/Abfragezahltests und bleibt offen. Die Startseite kann die doppelte Kurslistenabfrage ohne Änderung der Projektion vermeiden.

#### Umsetzung und gezielte Nachweise F4

- Ausgangspunkt: sauberer, per Fast-Forward synchronisierter `master` auf `994a7380`. Der neue Isolationstest war vor Implementierung wegen des fehlenden Providers rot. Anschließend wurden die beiden Lese-Handler migriert und die überholten Home-/Katalog-Aliase entfernt.
- `UnitCatalogService` übernimmt die bisherigen Regeln unverändert hinter vier Repository-Operationen. Die Startseite verwendet die bereits gelesene Kursliste erneut und übernimmt höchstens drei Katalogeinträge. Die HTTP-Adapter behalten Rollenprüfung und private Antworten; Initialisierungsfehler bleiben private 503-Antworten mit erneut versuchbarer Initialisierung.
- 24 gezielte Service-/Provider-/Home-/Katalog-/Routertests erfolgreich: Statusanzeigen, Suche, Titel-/Aktivitätssortierung, Abschnittsaktivität, leere Listen, Drei-Einheiten-Grenze, Admin-Zugang, 401/403/503 und unabhängiger Shell-Zugriff bei wartendem Repository. Echte lokale DB-Tests weisen für zwei synthetische Eigentümer getrennte Kurse, Einheiten und Kurszuordnungen nach.
- Die bisherigen Katalogtests verwenden ausdrücklich vorbereitete Authentifizierung und echte DB-Daten statt globaler In-Memory-Umschaltungen. Ein beim ersten fehlgeschlagenen Testlauf zurückgebliebener leerer Testkurs wurde anhand seiner konkreten ID und seines synthetischen Eigentümers bereinigt. Die korrigierte Fixture erfasst und löscht ausschließlich ihre eigenen Kurse und Einheiten; das DB-Inventar ist aktualisiert.
- Der erweiterte authentifizierte Browserrundlauf `teacher-home-workstarter` ist erfolgreich: Startseite → Live-Unterricht, Startseite → Editor, Startseite → Katalog, Suche einschließlich Neuladen und leerer Treffermenge sowie Öffnen des Anlegedialogs. Die laufbezogene Browser-Testdatenbereinigung wurde bestätigt; die Produkt-UI ist unverändert.
- Kritische Durchsicht: Keine FastAPI-Abhängigkeit im Katalogdienst, keine dynamische Fassade in beiden Handlern, keine zusätzliche Installation oder Datenbank. Workspace/Node-Editor und ihre benötigten Helfer bleiben bewusst unangetastet. Die verbleibenden kurs-/einheitenweisen Einzelabfragen und Listenbegrenzungen sind ausdrücklich als TD-009 erfasst und nicht als gelöst gewertet.

#### Zusätzliche Eingrenzung am Abschluss-Gate

Der erste vollständige F4-Lauf endete mit 14 Fehlern, 2668 bestandenen und 78 übersprungenen Backend-Tests. Die Fehler betreffen globale Learning-Repository-Overrides; derselbe Block besteht isoliert vollständig (22 Tests). Insbesondere liest `learning._get_repo()` im Gesamtlauf nach `set_repo(replacement)` weiter ein altes DB-Repository. Vor Abschluss wird diese reihenfolgeabhängige Testleckage mit einem minimalen Reproduktionsnachweis eingegrenzt. Eine nötige Korrektur soll ausschließlich die Testisolation des verursachenden Tests betreffen; keine Aufweichung fachlicher Zugriffsprüfungen und keine Erweiterung der Produktmigration auf Upload oder Portfolio.

Eingrenzung: Alle 433 Learning-Tests bestehen für sich. Ein temporärer Diagnosecheck im Gesamtlauf meldet die erste falsche Getter-Modulidentität unmittelbar nach `test_upload_intent_lazy_rewire_on_first_request`. Dessen vorhandene Aufräumroutine stellt nur `sys.modules` wieder her; `set_repo` hat aber auch die Namespaces der vorher registrierten Handler verändert. Reparaturplan: zuerst ein deterministischer Test für Import/Repository-Austausch/Wiederherstellung, dann die lokale Import-Isolation dieses Reload-Tests um Namespace- und Package-Attribut-Wiederherstellung ergänzen. Keine neue globale Reparatur-Fixture und keine Änderung der Produkt-Repository-Logik.

Der gezielte Regressionstest war mit der bisherigen Aufräumroutine rot: Die Identität des ursprünglichen `_get_repo` ging verloren. Nach der lokalen Korrektur sind beide Varianten (normaler Ablauf und Ausnahme während des Neuladens) sowie die drei bestehenden Reload-Tests grün. Auch der gemeinsame Lauf mit den zuvor betroffenen Portfolio-/Upload-/Repository-Tests ist grün. Die ursprünglichen globalen Produkt-Fassaden bleiben als offene Schuld bestehen; die Korrektur beschränkt sich auf die bereits vorhandene Import-Isolation dieses Testmoduls. Der temporäre Diagnosecheck wird nicht Teil des Repositorys.

#### Abschlussnachweis F4

- `make local-ca-status`: lokale CA in System, Chromium/Codex und Firefox vertraut. `docker compose up -d --build web`: lokaler Webdienst erfolgreich neu gebaut und gestartet.
- `make verify-feature FEATURE=teacher-home-workstarter` vollständig erfolgreich: **2684 Backend-Tests bestanden, 78 vorgesehen übersprungen; 683 Frontend-Tests, 8 Tooling-Tests, 62 H5P-Tests und 1 authentifizierter Browserrundlauf bestanden**. Die anschließende Feature-Bereinigung bestätigt, dass keine laufbezogenen Browser-Testkonten oder Daten zurückbleiben.
- Svelte-Prüfung ohne Fehler/Warnungen; Produktionsbuild mit ausschließlich den dokumentierten Upstream-Ausnahmen. Import-/Architekturgrenzen, API-Vertrag, Route-/DB-Inventar, Supply Chain, Ruff und Image-Smoke grün. `git diff --check` ohne Befund.

F4 ist abgeschlossen. Die übrigen Provider, insbesondere Workspace/Node-Editor, die Frontend-/Worker-/H5P-Arbeitspakete und der Sicherheitsabschluss bleiben offen. Die Katalog-Abfrageoptimierung ist als TD-009 dokumentiert. API, Schema, ENV, UI und DSPy bleiben unverändert; keine zusätzliche Installation, kein zusätzlicher Dienst, keine zusätzliche Datenbank und kein Push.

### F5: Expliziter Datenzugang des Inhaltseditors

Als Lehrkraft möchte ich Materialien, Aufgaben und Einstellungen meiner Abschnitte und Module unverändert bearbeiten können. Als Entwickler möchte ich die Editoransicht mit ausdrücklich übergebenen Daten prüfen können, ohne globale Teaching-Repositories oder Workspace-Helfer umzuschalten.

Abgrenzung: Zunächst nur `GET /api/teaching/views/units/{unit_id}/nodes/{node_id}/editor`. Der Workspace besitzt zusätzliche Graph-/Auswahlregeln und bleibt ein separates Folgepaket. Der Editor erhält einen expliziten Repository-Provider und einen frameworkunabhängigen Lesedienst. Die bereits vorhandene reine Aufgaben-Normalisierung wird unverändert in den Fachkontext verschoben und über den bestehenden Serializer-Alias weiterverwendet; Aufgabenarten werden nicht neu implementiert. Synchrone DB-Arbeit läuft im begrenzten Threadpool. Keine zusätzliche Installation, Datenbank oder Infrastruktur.

| Given – When – Then | Nachweis |
| --- | --- |
| Getrennte Testdaten – abwechselnd Editoransichten lesen – keine gegenseitige Beeinflussung | neue `test_teacher_editor_provider_isolation.py` |
| Linearer Abschnitt oder Lern-/Übungsmodul – laden – korrekte Materialien, Aufgabenarten, Einstellungen und Backing-Section | Service- und echte DB-Tests |
| Erster/letzter/leerer Abschnitt und fremder Knoten derselben Lehrkraft – laden – richtige Reihenfolge/leere Listen bzw. 404 | echte DB-Tests |
| Fremde Einheit, unbekannte Einheit – laden – unverändert 403 bzw. 404 vor Inhaltsabfrage | Service-/DB-Tests; bestehende Unterscheidung bewusst beibehalten |
| Fehlende Anmeldung, Schülerrolle oder ungültige IDs – laden – 401/403/400 vor Repository-Erzeugung | Isolationstests |
| Repositoryausfall oder wartender Adapter – laden – private 503-Antwort bzw. unabhängiger Shell-Request bleibt möglich | Provider-/Nebenläufigkeitstests |
| Aufgaben mit vorhandenen/alten Konfigurationsfeldern – normalisieren – identische öffentliche Felder ohne interne H5P-Spalten | Normalisierungs-/Editor-Tests |
| Authentifizierte Lehrkraft – linearen und modularen Editor öffnen, Material ändern, neu laden – Inhalte und gespeicherte Änderung bleiben korrekt zugeordnet | neues `teacher-node-editor.spec.ts`, ein `@feature-acceptance`-Szenario |

Vorprüfung: OpenAPI-Vertrag einschließlich 400/401/403/404/503 und bestehende Einheiten-/Modul-/Abschnittsmigrationen gelten unverändert. RLS, Aufgabenarten, ENV-Namen, API, Schema und UI werden nicht geändert; DSPy/KI bleiben ausdrücklich außerhalb dieses Pakets. Tests zuerst (Red-Green-Refactor). Bisherige Editor-Tests werden von globalen In-Memory-Overrides auf echte DB-Tests mit laufbezogener Bereinigung umgestellt; Workspace-Tests bleiben unverändert. Gate vor Abschluss: `make local-ca-status`, lokaler Web-Neubau, `make verify-feature FEATURE=teacher-node-editor`. Kein Push.

#### Umsetzung und gezielte Nachweise F5

- Ausgangspunkt: sauberer, per Fast-Forward synchronisierter `master` auf `d31a41a9`. Die neuen Tests waren vor Implementierung wegen des fehlenden Providers rot. Nach der Extraktion sind 20 Provider-/Service-/Normalisierungstests grün. Ein zusätzlicher zunächst roter Fehlerfall sichert die bestehende geschlossene 403-Antwort bei unklarem Existenznachweis ab.
- `NodeEditorService` verwendet sieben vorhandene Repository-Operationen. Die Eigentümerprüfung erfolgt vor Inhaltsabfragen; fremde Einheiten behalten 403, fehlende Einheiten/Knoten 404. Die Zuordnung von Modulen zur Backing-Section bleibt einheitengebunden. Materialien, Aufgaben, Musterlösungen, Fachkontext und Einstellungen behalten ihre bisherige Lehrkraft-Projektion. Der Web-Handler besitzt Rollen-/Parameterprüfung und HTTP-Fehlerabbildung, aber keine dynamische Fassade.
- Die reine Aufgaben-Normalisierung wurde unverändert verschoben. Der statische Serializer-Alias bleibt für bestehende Aufrufer erhalten; keine zweite Aufgabenarten-Implementierung und keine KI-Änderung. Die bisherigen Serializer-/H5P-/Aufgabenartenprüfungen sind grün (19 Tests).
- Die zwei bisherigen Editor-Tests liegen nun in `test_teacher_node_editor_db.py` mit frischer Authentifizierung, echten DB-Daten und gezielter Bereinigung ausschließlich selbst angelegter Einheiten samt abhängiger Inhalte. Der bisher wegen fehlender In-Memory-Modulfunktionen übersprungene Editor-Test läuft nun tatsächlich. Drei zusätzliche Szenarien sichern leere erste/letzte Knoten sowie Eigentümer-/Einheitengrenzen für lineare Einheiten, Lernmodule und Übungsmodule ab. DB-Inventar aktualisiert.
- Gemeinsamer gezielter Lauf: 32 Editor-/Workspace-/OpenAPI-Tests bestanden, ein bestehender In-Memory-Workspace-Test vorgesehen übersprungen. Der neue Browserrundlauf `teacher-node-editor` ist grün: lineare und modulare Materialien über die echte Oberfläche umbenennen, Seite verlassen, wieder öffnen und neu laden; anschließend Kriterien einer Modulaufgabe anzeigen. Im Test wurde der doppelte Labeltext „Titel“ auf das Materialformular eingegrenzt. Produkt-UI unverändert; laufbezogene Browser-Testdatenbereinigung bestätigt.
- Kritische Durchsicht: Keine zusätzlichen Abfragen je Material oder Aufgabe; weiterhin jeweils eine Material- und Aufgabenlistenabfrage für den ausgewählten Knoten. Die Eigentümer-/Knotenermittlung wird nicht stillschweigend verändert. Workspace und dessen globale Helfer bleiben als Folgepaket offen. Der neue Provider initialisiert verzögert, erlaubt Wiederholung nach Initialisierungsfehlern und teilt keine Verbindung oder Benutzerkontexte zwischen Requests.

Der erste vollständige Backend-Durchgang ergab 2707 bestandene Tests, 77 vorgesehene Überspringungen und ausschließlich einen Dokumentationsbefund: Der historische Harness-Vertrag verbietet die pauschale Formulierung „bleibt offen“. Die Workspace-Notiz verweist nun konkret auf die offene Schuld TD-004 und den Umsetzungsplan; der Arbeitsstand wird nicht verborgen oder als abgeschlossen ausgegeben. Alle 22 Harness-Dokumentationsprüfungen sind danach grün. Die funktionalen Prüfungen einschließlich des im vorigen Paket korrigierten Reload-Testblocks blieben ohne Befund.

#### Abschlussnachweis F5

- `make local-ca-status`: lokale CA in System, Chromium/Codex und Firefox vertraut. `docker compose up -d --build web`: lokaler Webdienst erfolgreich neu gebaut und gestartet.
- `make verify-feature FEATURE=teacher-node-editor` vollständig erfolgreich: **2708 Backend-Tests bestanden, 77 vorgesehen übersprungen; 683 Frontend-Tests, 8 Tooling-Tests, 62 H5P-Tests und 1 authentifizierter Browserrundlauf bestanden**. Die anschließende Feature-Bereinigung bestätigt, dass keine laufbezogenen Browser-Testkonten oder Daten zurückbleiben.
- Svelte-Prüfung ohne Fehler/Warnungen; Produktionsbuild mit ausschließlich den dokumentierten Upstream-Ausnahmen. Import-/Architekturgrenzen, API-Vertrag, Route-/DB-Inventar, Supply Chain, Ruff und Image-Smoke grün. `git diff --check` ohne Befund.

F5 ist abgeschlossen. Nächstes Backend-Teilpaket ist die Workspace-Ansicht mit Graph und Knotenauswahl. Die übrige Provider-Migration, Frontend-/Worker-/H5P-Arbeitspakete und der Sicherheitsabschluss bleiben offen; der Gesamtplan ist nicht abgeschlossen. API, Schema, ENV, UI und DSPy bleiben unverändert; keine zusätzliche Installation, kein zusätzlicher Dienst, keine zusätzliche Datenbank und kein Push.

### F6a: Gemeinsamer Graphnachweis für Lehrkraft und Lernende

Ergänzter Auftrag vom 7. September: Die Graphansicht existiert in beiden Rollen; Darstellung und Knotenanordnung dürfen nicht unabhängig voneinander weiterentwickelt werden. Dieser rollenübergreifende Schritt geht der geplanten Workspace-Provider-Migration F6b voraus.

Als Lehrkraft und Lernender möchte ich dieselbe Lerneinheit räumlich wiedererkennen: Phasen, relative Knotenpositionen, Knotengrößen und Verbindungen sollen übereinstimmen. Unterschiedliche Bearbeitungsrechte, Sperren, Fortschrittsanzeigen und individuell ausgewählte Ausschnitte bleiben erhalten.

Vorbefund: `buildLearningUnitFlow` verwendet bereits `buildTeacherUnitFlow` für die Geometrie. Ein zweiter Layoutalgorithmus ist deshalb nicht vorgesehen. Die Lehrkraft verwendet eigene Fokus-/Gesamtansichtssteuerung, Lernende dagegen automatisches `fitView` und Standardsteuerung. Die beiden Knotendarstellungen verwenden unterschiedliche Innenabstände. Die Learning-Abfrage liefert auch gesperrte Graphknoten, aber keine gesperrten Aufgabeninhalte. Diese Sicherheitsgrenze darf nicht zur Herstellung visueller Gleichheit erweitert werden.

| Given – When – Then | Nachweis |
| --- | --- |
| Dieselben Phasen, Verzweigungen, Zusammenführungen und Übungsmodule – beide Rollen bauen den Graphen – identische Positionen, Größen, Elternzuordnung und Kantenführung | neue `unit-flow-parity.test.ts` |
| Dieselben fachlichen Positionen, unterschiedlich sortierte Eingabelisten – Layout aufbauen – stabile didaktische Reihenfolge und Kantenführung ohne Mutation der Eingaben | Layout-Regressionstests; gezielte Korrektur nur bei reproduziertem Befund |
| Offene/gesperrte/erledigte Module – Schülergraph aufbauen – Status verändert nur Darstellung/Öffnen, niemals Geometrie oder Bearbeitungsrechte | Layout-/Adaptertests |
| Beide Rollen öffnen denselben mehrphasigen Graphen – Fokus und Gesamtansicht verwenden – gemeinsame Steuerung und lesbarer Start; keine Lehrkraft-Bearbeitungsaktionen im Lernpfad | Komponenten- und Browsertests |
| Echte Lehrkraft und eingeschriebener Schüler – dieselbe gespeicherte Lerneinheit öffnen und neu laden – Graphdaten und tatsächliche gerenderte Geometrie stimmen überein; gesperrte Inhalte bleiben gesperrt | neues `graph-role-parity.spec.ts` mit `@feature-acceptance` |
| Desktop, Tablet und Mobil, Light/Dark – Graph anzeigen – kein Seitenüberlauf; Screenshots visuell prüfen | derselbe gezielte Browsernachweis |

Umsetzung: Tests zuerst (Red-Green-Refactor), tatsächliche Geometrie getrennt von Zoom/Ausschnitt vergleichen. Vorhandene Graphsteuerung als gemeinsamer UI-Baustein nutzbar machen; keine duplizierten Fokusregeln. Gegebenenfalls Reihenfolge normalisieren, aber keinen neuen Layoutstil oder neue Navigationshierarchie einführen. Eine konkrete abweichende Lerneinheit wurde zusätzlich beim Produktverantwortlichen erfragt; bis dahin dient ein laufbezogener verzweigter Testgraph als Nachweis.

Contract-/Umgebungsprüfung: Bestehende Teaching-Workspace- und Learning-Graph-Verträge, Rollenprüfungen und SQL-Abfragen wurden verglichen. Keine API-, Schema-, ENV-, KI- oder DSPy-Änderung vorgesehen; daher keine Migration und kein neuer API-Endpunkt. Die echte DB wird über vorhandene API-Endpunkte im authentifizierten Browserrundlauf geprüft. Vor Browserprüfung lokale CA prüfen; ausschließlich lokalen Stack und laufbezogene Testdaten mit bestehender Bereinigung verwenden. Gate vor Fertigmeldung und Commit: `make verify-feature FEATURE=graph-role-parity`. F6b und die übrigen offenen Pakete werden dadurch nicht als erledigt gewertet.

#### Umsetzung und gezielte Nachweise F6a

- Ausgangspunkt: sauberer, synchronisierter `master` auf `ee14d89e`. Paritäts-/Darstellungstests wurden vor Produktänderungen angelegt. Die unveränderte rollenübergreifende Knotenberechnung bestand bereits; permutierte Phasen-/Kantenlisten und unterschiedliche Komponentennutzung waren rot. Phasen werden nun anhand ihrer gespeicherten Position sortiert, Kanten mit gleichem Ursprung zusätzlich anhand des Ziels. Die Eingabedaten bleiben unverändert.
- Der erste echte Browservergleich reproduzierte identische Knotenpositionen und Größen, aber um zwei Pixel versetzte Pfeilenden sowie verschiedene Innenabstände. Die Schüler-Anschlusspunkte lagen außerhalb, die Lehrkraft-Anschlusspunkte innerhalb des gerahmten Knotens. Beide verwenden jetzt denselben Bezugsrahmen und die bestehende kompakte Innenabstandsregel. Die acht Schüler-Anschlusspunkte werden einheitlich erzeugt, sind nicht verbindbar und für assistive Technik dekorativ.
- `GraphViewportControls` ersetzt die bisherige rein lehrkraftbezogene Steuerung ohne Kopie. Ein zusätzlicher roter Browsernachweis zeigte, dass die Schülerknoten nach dem Mount eintreffen; die Initialisierung wartet nun auf gemessene Knoten und eine fertige Zeichenfläche. Der Fokus wird nur einmal angewandt. Die Schüleransicht bietet keinen Interaktionsschalter, der Knotenverschiebung oder Verbindungsbearbeitung aktivieren könnte.
- Die visuelle Prüfung des ersten grünen Browserlaufs zeigte abgeschnittene Phasenüberschriften auf Mobilgeräten: Die bisherige Zoom-Untergrenze 0,52 verhinderte eine vollständige Gesamtansicht. Eine neue zunächst rote Bounding-Box-Prüfung erfasst alle Knoten einschließlich Phasenrahmen innerhalb der Zeichenfläche. Die Untergrenze für beide Zeichenflächen und die Gesamtansicht beträgt nun 0,1; der lesbare Fokus bleibt bei mindestens 0,82. Dies ändert keine gespeicherten Knotenpositionen.
- Der laufbezogene Browsergraph besitzt drei Phasen (eine leer), sechs Module einschließlich Übungsmodul, Verzweigung, Zusammenführung und horizontale sowie phasenübergreifende Kanten. Die Fixture verwendet ausschließlich vorhandene APIs; unzulässige rückwärts gerichtete Testkanten wurden korrigiert, nicht fachliche Graphregeln aufgeweicht. Fehlende Test-Kursmetadaten und ein Test-Dateipfad wurden ebenfalls korrigiert. Jeder Lauf bestätigte die Bereinigung ausschließlich eigener Testdaten.
- 17 fokussierte Layout-/Darstellungs-/bestehende Routenprüfungen grün; Svelte-Prüfung ohne Fehler oder Warnungen. Keine neuen Abfragen, keine Änderung von Sperren, Fortschritt oder RLS. Die Rolle entscheidet weiterhin über Daten und Bedienmöglichkeiten, nicht über eine zweite räumliche Struktur.

#### Abschlussnachweis F6a

- `make local-ca-status`: lokale CA in System, Chromium/Codex und Firefox vertraut. `docker compose up -d --build --no-deps frontend`: lokaler Produktionsbuild erfolgreich erstellt und gestartet; Compose-Konfiguration unverändert.
- `make verify-feature FEATURE=graph-role-parity` vollständig erfolgreich: **2708 Backend-Tests bestanden, 77 vorgesehen übersprungen; 688 Frontend-Tests, 8 Tooling-Tests, 62 H5P-Tests und 1 authentifizierter rollenübergreifender Browserrundlauf bestanden**. Svelte-Prüfung ohne Fehler/Warnungen, Produktionsbuild mit ausschließlich den 16 dokumentierten Upstream-Ausnahmen. Architektur-/Importgrenzen, API-Vertrag, Inventare, Supply Chain, Ruff und Image-Smoke grün.
- Zusätzlich `make test-feature-acceptance FEATURE=teacher-graph-module-actions` erfolgreich: bestehender Lehrkraft-Ablauf einschließlich Auswahl, Seitenleiste, Bearbeitung, Entwürfen, Rückkehr zum Graphen und bestätigten Testlöschungen. Beide Profile bestätigen die vollständige laufbezogene Testdatenbereinigung. Keine historische Gesamtsuite und kein Reset der festen Dev-Personas.
- Zwölf finale Screenshots bei 1440 × 900, 1024 × 768 und 390 × 844, jeweils beide Rollen in Light/Dark, visuell geprüft. Die Bilder zeigen die bewusst verkleinerte Gesamtansicht einschließlich aller Phasen; der lesbare Startfokus ist zusätzlich automatisiert geprüft. Seitenkopf, Werkzeugleisten und Statusfarben bleiben rollenbezogen. Screenshots beginnen nach explizitem Zurückscrollen am Seitenanfang, damit automatisches Scrollen zu den Graphsteuerungen nicht mit Layoutfehlern verwechselt wird. Keine historischen Referenzbilder überschrieben.
- 41 Dokumentations-/Schuldenregistertests und `git diff --check` ohne Befund. Die bestätigten Korrekturen beziehen sich auf den reproduzierten gemeinsamen Testgraphen und die Eingabereihenfolge; eine konkret vom Produktverantwortlichen beobachtete Lerneinheit wurde noch nicht benannt.

F6a ist abgeschlossen. F6b entkoppelt als nächstes die Backend-Datenaufbereitung der Graph-/Workspace-Ansichten; der rollenübergreifende Vergleich bleibt dabei ein gemeinsamer Regressionsnachweis. Übrige Provider-, Seiten-/Controller-/CSS-, Worker- und H5P-Arbeit sowie der Sicherheitsabschluss bleiben offen. Keine API-, Schema-, ENV- oder DSPy-Änderung und kein Push.
