# Lehrer- und Auth-UI: automatisierte Prüfung und Commit-Aufteilung

## Auftrag und Vorgehen

Nach der abgeschlossenen manuellen Sichtprüfung werden die bisherigen Lehrer-, Live- und Auth-Änderungen automatisiert abgesichert, gefundene Fehler behoben und in fachlich zusammenhängende Commits aufgeteilt. Der Auftrag schließt die historische Gesamtsuite ausdrücklich ein. Keine API- oder Schemaänderung ist geplant.

## Prüfreihenfolge

1. Bestand und lokale Voraussetzungen prüfen: CA, Datenbank, laufender Stack, Testprofile.
2. Betroffene Komponenten und Auth-Verträge prüfen. Countdown mit absoluter Frist, Reload, Ablauf, getrennten Auth-Vorgängen und Versandfehlern als gezielte Regression absichern.
3. `make verify-feature FEATURE=auth-platform` als verbindliches Feature-Gate ausführen. Ergänzende authentifizierte Abläufe für Lehrereditor, Live-Ansicht und Registrierung prüfen.
4. `make test-full-prod-like` einschließlich historischer Feature-Regression, Integrationen und visueller Smokes ausführen; zusätzlich `make docker-validate` für Keycloak. Fehler nach einem reproduzierbaren Prüffall beheben und betroffene Prüfungen erneut ausführen.
5. Geänderte visuelle Referenzen nur nach tatsächlicher Bildprüfung gegen DESIGN.md übernehmen. Keine blinden Snapshot-Aktualisierungen.
6. Öffentliche Dokumentation auf personenbezogene Prüfdaten und Zugangsdaten prüfen. Sinnvolle Commits für Lehrerrahmen/Editoren, Live-Darstellung und Auth-Abläufe erstellen. Kein Push.

## BDD-Szenarien und Zuordnung

- Gegeben eine Mail-Sperrfrist, wenn die Seite neu geladen oder ein Hintergrund-Tab wieder aktiv wird, dann bleiben absolute Frist und deaktivierter Versandbutton korrekt. Zuordnung: gezielter Skript-Verhaltenstest mit kontrollierter Uhr und DOM.
- Gegeben eine abgelaufene oder fremde Auth-Sitzung, wenn die Warteseite geladen wird, dann blockiert kein veralteter Countdown den Versand. Zuordnung: derselbe Verhaltenstest.
- Gegeben erfolgreicher/fehlgeschlagener Mailversand, wenn erneut angefordert wird, dann erscheint ausschließlich die passende aktuelle Rückmeldung. Zuordnung: Skript-Verhaltenstest und vorhandene Keycloak-Theme-Verträge; native Form wurde bereits manuell ohne JavaScript geprüft.
- Gegeben eine angemeldete Lehrkraft, wenn sie Module bearbeitet und Abgaben öffnet, dann bleiben Navigation, Auswahl und Inhalt verwendbar. Zuordnung: authentifizierte Specs `teacher-node-editor`, `dialog-task-authoring`, `live-summary` sowie Gesamtsuite.
- Gegeben ein nicht angemeldeter Besucher, wenn Anmeldung, Registrierung und Passwort-Hilfe durchlaufen werden, dann bleiben sichere Weiterleitung und Formularzustände erhalten. Zuordnung: `auth-platform`, `auth-registration`, `auth-session-continuity` und Keycloak-Sicherheits-Smoke.

## Ergebnisse

Die Prüfungen laufen auf dem freigegebenen lokalen Stack. Backend-/Datenbankprüfungen und authentifizierte Browserprüfungen werden sequenziell ausgeführt, damit sie keine gemeinsamen Sitzungen gegenseitig verändern.

### Gefundene Abweichungen

- Alte Komponentenprüfungen verlangten die vor der Sichtprüfung verworfenen Auth-Schatten/eckigen Rahmen und unbeschriftete Mini-Aufgabenfelder. Erwartungen an den genehmigten Designvertrag angepasst; Verhalten und Bewertungsgrenzen bleiben geprüft.
- Auth-Abnahme erwartete einen veralteten Fehlertitel; Registrierung und Logout-Abnahme an die aktuellen sichtbaren Überschriften und die explizite Abmeldebestätigung angepasst.
- Mail-Prüfaufbau konnte nach temporärem SMTP-Wechsel nur das von Keycloak gelieferte Passwort-Maskierungszeichen wiederherstellen. Vor der Mutation wird nun das passende konfigurierte Passwort aufgelöst; bei fremdem Server/Benutzer oder fehlendem Passwort bricht der Aufbau ab. Fünf gezielte Prüffälle sichern dies ab.

- Browserprüfungen verwenden nun eine gemeinsame Bedienhilfe für Kontextnavigation und den Darstellungswechsel im Kontomenü. Veraltete Selektoren und Miniatur-Abmessungen werden an den bereits manuell freigegebenen Stand angepasst. Die UI-Labor-Karte erhält ebenfalls den dokumentierten 8-px-Radius und dezenten Rahmen.
- Der erste Backend-Gesamtlauf ergab 3.178 bestandene Prüfungen und zwei bereits behobene alte Template-Erwartungen. Der anschließende komplette Frontend-/H5P-Lauf bestand. Datenbank- und Browser-Gesamtläufe werden anschließend sequenziell ausgeführt, um wechselnde Testsitzungen nicht zu überlagern.
- SMTP-Wiederherstellung: Keycloak 26.8.1 entfernt maskierte Passwörter bei geänderten SMTP-Zielen ausdrücklich. Deshalb wird vor jeder Mutation eine wiederherstellbare Konfiguration benötigt. Quelle: [DefaultExportImportManager](https://github.com/keycloak/keycloak/blob/26.8.1/model/storage-private/src/main/java/org/keycloak/storage/datastore/DefaultExportImportManager.java).

- Der echte Live-Browserlauf zeigte eine Layoutregression: Die auf volle Breite gestreckte Tabelle verbreiterte auch die beiden Summenspalten (88 px wurden zu rund 234 px). Die Aufgaben-Spalten nehmen jetzt den freien Platz auf; Name und Summen behalten ihre festen Breiten. Der bestehende Browserfall `live-summary` prüft diesen Fehler.
- Historische Lernpfad-Prüfungen erwarteten auf iPads noch den inzwischen durch die Phasenliste ersetzten Graphen. Desktop prüft weiterhin Graphgeometrie, auf schmalen Ansichten werden stattdessen Modulverbindungen und Sperrzustände geprüft. Entwurfs- und Abgabeprüfungen behalten ihre fachlichen Aussagen und nutzen die aktuellen sichtbaren Beschriftungen.

- Rücksprung aus dem Lehrereditor: Der gemeinsame Breadcrumb übernimmt jetzt die Modul-/Abschnittsauswahl. Die bisherigen eigenen Rücklinks waren verborgen worden, während der neue Link nur die Lerneinheit adressierte. Die authentifizierten Graph-/Abschnittsabläufe prüfen die Wiederherstellung.
- Live ohne Aufgaben: Ein neuer, zunächst fehlschlagender Komponententest sichert die Erreichbarkeit eingeschriebener Lernender. Die Tabelle bleibt nun auch ohne Lernaufgaben sichtbar, zusammen mit dem vorhandenen Leerhinweis.

- Browseraktionen erhalten eine begrenzte Wartezeit von 20 Sekunden (Navigation 30 Sekunden). Fehlende Bedienelemente sollen gezielt scheitern, statt bis zum langen gesamten Workflow-Timeout zu blockieren. Explizite längere Wartezeiten für fachliche Verarbeitung bleiben erhalten.

### Visuelle Referenzen

Die drei freigegebenen Visual-Specs wurden nach Anpassung der historischen Verträge erfolgreich im Aktualisierungsmodus ausgeführt. 102 tatsächlich geänderte PNG-Referenzen wurden als neun beschriftete Übersichten visuell geprüft, ergänzt durch Detailprüfung der schmalen Modulansicht. Abgedeckt sind UI-Labor, Moduleditor, Kurskatalog/Archiv, Graph-Inspektor/Löschdialog sowie Lernarbeitsplatz und Materialleser in Hell/Dunkel. Keine unerwarteten Überlagerungen oder horizontalen Beschnitte erkannt. Der abschließende Lauf ohne Snapshot-Aktualisierung besteht mit 13/13 Fällen. Die sechs Startseitenbilder wurden nach der Stabilisierung der Zeitangaben nochmals gesondert geprüft.

### Bereits bestandene Prüfblöcke

- Lokale CA: System, Chromium/Codex und Firefox vertrauen der aktuellen Caddy-CA.
- Compose-/Keycloak-Konfiguration: `make docker-validate` erfolgreich.
- Vollständiger `verify`-Block im Gesamttest: Import-/Architekturgrenzen, API-/Routen-Baselines, Datenbankinventar, Supply-Chain-Vertrag, Ruff und Container-Smokes erfolgreich; Backend 3.181 bestanden, 36 übersprungen, 2 Warnungen. Die übersprungenen Integrationen werden anschließend über ihre ausdrücklich aktivierten Profile ausgeführt.
- Abschließender Frontend-Komponentenlauf: 176 Dateien mit 859 bestandenen Tests; Typ-/Svelte-Prüfung ohne Fehler oder Warnungen. Darin enthalten sind die sieben Countdown-/Versand-Verhaltenstests, die fünf SMTP-Wiederherstellungsfälle und der neue Live-Leerzustand.
- Node-Tooling: 11 bestanden; H5P-Sidecar: 74 bestanden.
- Abhängigkeitsaudit: keine bekannten Lücken. Das lokal gepatchte DSPy-Paket wird über die vorhandene Upstream-Prüfung ergänzt.

### Commit-Zuschnitt

1. Sichere Mail-Prüfhelfer und gemeinsame Browserbedienhilfen.
2. Lehrer-Kopfleiste und Modul-/Aufgabeneditoren einschließlich Rücksprungkontext.
3. Live-Bewertungsfarben, Aufgabenfelder, Klassen-/Abgabenwechsel und Leerzustände.
4. Auth-Rahmen, Fehler-/Erfolgszustände und E-Mail-Warteablauf.
5. Sicherer Löschkonflikt bei vorhandenen Abgaben.
6. Erreichbarer Abschluss leerer Übungssitzungen und unabhängige H5P-Abläufe.
7. Aktualisierte Browserregression und visuell geprüfte Referenzen.
8. Historische Storage-/HTTP-E2E-Prüfhelfer und wiederherstellbares Produktions-Prüfprofil.
9. Abschließender Prüfbericht.

### Zusätzlicher schmaler Graphfall

Der authentifizierte Fall `graph-role-parity` reproduziert eine echte Überlagerung: Bei breiter Auswahlleiste auf schmalen Bildschirmen schrumpft die Zeichenfläche so stark, dass die vertikalen Graphbuttons unter der Leiste liegen und keine Zeigerereignisse erhalten. Gegeben eine schmale Lehreransicht mit ausgewählter Phase, wenn Graphsteuerung per Zeiger und Tastatur verwendet wird, dann müssen alle aktiven Buttons erreichbar bleiben. Derselbe zuerst fehlgeschlagene Browserfall prüft die Korrektur. Der mobile Bereich erhält automatische Gesamthöhe mit weiter wirksamer verfügbarer Mindesthöhe und mindestens 18 rem Zeichenfläche; bei Platzmangel bleibt normales Seitenscrollen möglich.

Die manuelle Bildkontrolle der 320-px-Lehreransicht bestätigt die getrennten Bereiche für Auswahlleiste, Zeichenfläche und alle fünf Graphsteuerungen. Der zugehörige Browserfall besteht nach der Korrektur einschließlich Zeiger-/Tastaturbedienung und Kamerawiederherstellung. Beim Wechsel aus der mobilen Phasenliste zurück zum Desktop muss der Kameratest die vorgesehene Orientierungsanimation abwarten; eine gespeicherte Gesamtansicht darf weiterhin kleiner als der Lesezoom sein. H5P-Fortschritt verwendet für den Modulrücksprung die sichtbare Kontextaktion statt eine von der Browserhistorie abhängige Annahme. Dialogabschluss, echte H5P-Freischaltung, Übungssitzung und die sechs Safari-Kompatibilitätsfälle bestehen gezielt.

### Leere aktive Übungssitzung

Im vollständigen Lauf reproduzierbar, einzeln nicht: Die H5P-Drag-Prüfung ließ eine Sitzung aktiv. Nach dem regulären Löschen ihrer Kursaufgaben blieb eine aktive Sitzung mit `total_items: 0` und `current_item: null` zurück. Die bisherige Übungsoberfläche renderte dafür keinen Inhalt. Dies ist auch bei gelöschten Aufgaben einer echten laufenden Sitzung möglich. Gegeben eine aktive Sitzung ohne verfügbare Aufgabe, wenn die Übungsseite geöffnet wird, dann erscheint eine klare Meldung mit nativem Formular zum Beenden statt einer leeren Seite. Zuordnung: neuer, zunächst roter `PracticeSessionWorkspace`-Komponententest. Keine API-/Schemaänderung: Das Formular verwendet die vorhandene End-Aktion. Die beiden H5P-Browserfälle beenden ihre Sitzungen über die echte UI, bevor ihre Aufgaben aufgeräumt werden; damit bleiben die Fälle unabhängig.

Der bestehende authentifizierte `@feature-acceptance`-Fall `h5p-drag-layout` bildet den neuen Leerzustand zusätzlich vollständig ab: aktive Bearbeitung, Löschen der letzten Aufgabe durch ihre Lehrkraft über die vorhandene API, Neuladen beim Schüler, native Beenden-Aktion und echte Sitzungszusammenfassung. Damit wird der echte Fehler geprüft und nicht nur durch Testbereinigung verdeckt. `h5p-learner-feedback-progress` schließt seine erste Übungssitzung ebenfalls regulär ab.

Der zusätzliche Löschversuch einer bereits beantworteten Aufgabe legte eine fehlende Fehlerübersetzung offen. Ergänzender Vertrag, roter/grüner DB-Test und sichere 409-Behandlung sind im [Löschschutz-Plan](2026-10-22-task-delete-submissions.md) dokumentiert. Die vorherige Aussage „keine API-Änderung geplant“ bleibt der ursprüngliche Umfang; diese nachgewiesene Fehlerkorrektur ergänzt ausschließlich den fehlenden Konfliktstatus, ohne Schema- oder Löschschutzänderung. Der abschließende Feature-Gate wird deshalb zusätzlich für `h5p-drag-layout` ausgeführt.

Auch der historische HTTP-E2E-Logoutfall wird an den freigegebenen Ablauf angepasst: GET zeigt die Bestätigung und erhält die Sitzung, erst POST meldet ab. Der Test entfernt das Cookie anschließend nicht mehr selbst, sondern prüft die tatsächliche Invalidierung durch die Anwendung. Der gleiche Ablauf ist bereits im echten Auth-Browserfall abgesichert.

Die vollständige historische Browserregression besteht mit 53/53 Fällen. Im danach aktivierten Storage-Profil scheiterten vier alte Fixtures bereits an `course_metadata_incomplete`, bevor ein Upload stattfand. Die Kurs-Fixtures werden an den bestehenden Vertrag mit Fach, Jahrgang und Schuljahresbeginn angepasst; keine Lockerung der Produktionsvalidierung. Der echte Supabase-Upload-Rundlauf wird anschließend wiederholt.

Die nächste echte Storage-Prüfung erreichte Upload und Abschlussvalidierung. Der Host-Prüfprozess hatte jedoch im Gegensatz zu Compose keine öffentliche Supabase-Origin, wenn `SUPABASE_PUBLIC_URL` in `.env` leer blieb. Dadurch traf die korrekte Produktions-SSRF-/HTTPS-Regel auf eine direkte HTTP-Signaturadresse. Das Prüfziel erhält denselben HTTPS-Standardwert wie Compose (`https://app.localhost`). Sicherheitsregeln, Zertifikatsprüfung und `.env` bleiben unverändert; die Abschlussvalidierung lädt weiterhin echte hochgeladene Bytes.

HTTPX im Python-Venv verwendet eine eigene CA-Auswahl und vertraute der lokalen Caddy-CA noch nicht. Das Storage-Prüfziel verwendet deshalb über `SSL_CERT_FILE` denselben vorhandenen Caddy-CA-Nachweis wie das E2E-Profil; eine explizit konfigurierte CA-Datei bleibt vorrangig. Dies aktiviert Zertifikatsprüfung mit der richtigen Vertrauenskette, statt sie auszuschalten.

Eine gezielte Beobachtung des realen Abschlussaufrufs zeigte anschließend `NullStorageAdapter`: Die alten Tests entfernten einzelne Module aus `sys.modules`, während bereits registrierte Router und Package-Attribute weiter auf frühere Instanzen zeigten. Die Tests behalten nun einen kanonischen Modulgraphen und initialisieren den echten Supabase-Adapter nach dem gemeinsamen Fixture-Reset über dieselbe idempotente Produktionsfunktion. Es werden keine Dateibytes oder Storage-Antworten gemockt.

Die ältere HTTP-E2E-Suite zeigte acht defekte Formularhelfer: HTML-Entitäten in Aktionsadressen und Standardwerten wurden nicht dekodiert. Acht zunächst rote, dann grüne Prüffälle prüfen die browsergleiche Dekodierung. Die Helfer dekodieren nun korrekt; die Error-Page-Prüfung akzeptiert die gemeinsame zusätzliche Rahmenklasse. Temporäre Passwortregeln der Registrierungsvalidierung werden außerdem in einem Fixture mit `finally` auf den zuvor gelesenen Wert zurückgestellt.

Die historische HTTP-Suite bestand danach 11 von 15 Fällen. Ergänzt werden die bereits erforderlichen Kursmetadaten auch im `finishedData`-Fixture sowie die Erwartung an das stärkere `SameSite=Strict` des aktuellen Keycloak-Cookies. Der lokale Stack war über `.env` im Modus `dev`; das H5P-Debugseiten-Verbot gilt ausdrücklich im Produktionsmodus. Der E2E-Block wird deshalb mit `GUSTAV_ENV=prod make test-e2e` geprüft; auch `test-full-prod-like` setzt dies für seinen E2E-Unteraufruf explizit. Nach der Prüfung wird der vorherige Betriebsmodus aus der unveränderten `.env` wiederhergestellt. Keine Debug-/Cookie-Sicherheitsregel wird gelockert.

Im Produktionsmodus bestehen 14/15 HTTP-E2E-Fälle. Der letzte veraltete Fall verlangte eine CSRF-Ausnahme für `Origin: null`, die dem aktuellen Same-Origin-Vertrag widerspricht. Der Test prüft nun ausdrücklich die 403-Ablehnung und anschließend denselben authentifizierten H5P-Ergebnisrundlauf mit korrekter Herkunft bis zur echten Abgabehistorie. Die Produktionsregel bleibt streng.

Alle 15 HTTP-E2E-Fälle bestehen im Produktionsmodus. Der visuelle Feature-Prüfrahmen verweigert mutierende Browserprüfungen absichtlich gegen als Produktion markierte Dienste. Das vollständige Prüfziel stellt deshalb nach seinem isolierten Produktions-E2E-Block den ursprünglichen Stack über `make up` wieder her, bevor es visuell weiterprüft. Dies geschieht auch bei einem E2E-Fehler; dessen Exitstatus bleibt erhalten. Die Produktionssperre des Feature-Prüfrahmens wird nicht umgangen.

Der erste abschließende Bildvergleich bestand 12/13 Fälle. Die Abweichung betraf 28 Pixel am Rand einer zeitabhängig breiten Datumsmaske auf der Lehrerstartseite, nicht die Graphdarstellung. Für diese Aufnahme werden volatile Zeitangaben per Screenshot-Stil unsichtbar, statt eine variable farbige Maskenfläche zu zeichnen. Die eigentliche Oberfläche und die Screenshot-Fehlertoleranz bleiben unverändert. Die sechs Referenzen dieser Startseite werden anschließend erneut visuell geprüft.

## Abschließender Nachweis

Nach den Fehlerkorrekturen wurden alle Unterprofile von `make test-full-prod-like` sequenziell erfolgreich abgeschlossen. Bereits grüne Produktions-/Komponentenprüfungen wurden nach ausschließlich testseitigen Anpassungen nicht unnötig wiederholt. Beide erforderlichen Feature-Gates wurden ausgeführt; der zusätzliche fachliche Fehlerfix ist im H5P-Gate vollständig enthalten.

| Prüfung | Ergebnis |
|---|---|
| `make verify-feature FEATURE=auth-platform` | bestanden |
| `make verify-feature FEATURE=h5p-drag-layout` | bestanden; vollständiger Backend-Lauf: 3.182 bestanden, 36 regulär übersprungen, 2 Warnungen |
| Frontend | 176 Testdateien, 860 Tests bestanden; Typ-/Svelte-Prüfung ohne Fehler oder Warnungen |
| Node-Tooling / H5P-Sidecar | 11 / 74 bestanden |
| `make test-feature-regression` | 53/53 bestanden, einschließlich Chromium und WebKit/iPad |
| `make dependency-audit` | keine bekannten Lücken; gepatchtes DSPy ergänzend über Upstream auditiert |
| `make test-supabase` | 5/5 echte Storage-Rundläufe bestanden |
| `make test-openai` | 2/2 Endpunkt-Smokes bestanden |
| `GUSTAV_ENV=prod make test-e2e` | 15/15 HTTP-E2E-Fälle bestanden |
| `make test-visual-smoke` ohne Aktualisierung | 13/13 bestanden |
| Ergänzende Prüfhelfer-/TLS-/Makefile-Verträge | 72 bestanden, einschließlich acht HTML-Dekodierungen und zweier ausführbarer Orchestrierungstests für Erfolg/Fehler mit Moduswiederherstellung |
| Abschließende Gates | Backend-Lint, DB-Inventar, OpenAPI-, Import-, Architektur- und Routen-Baselines sowie `docker-validate` bestanden |

Die normalen Skips des Standardlaufs bleiben sichtbar; die aktivierten Integrationsprofile wurden separat tatsächlich ausgeführt. Die Storage-Warnungen betreffen die vorhandenen SDK-Deprecations und eine automatisch ergänzte URL-Endung, keine ausgeschaltete Prüfung. 102 geänderte Bildreferenzen wurden visuell geprüft, die sechs stabilisierten Startseitenbilder nochmals gesondert. Der neue Übungs-Leerzustand wurde zusätzlich auf Desktop und mobil betrachtet.

Der ursprüngliche lokale Betriebsmodus ist wiederhergestellt. `.env`, Zertifikatsprüfung und die Produktionssperre des Feature-Prüfrahmens bleiben erhalten. Keine Schemaänderung, keine neuen Laufzeitabhängigkeiten und kein Push.

## Erstellte Commits

| Commit | Inhalt |
|---|---|
| `35ab868f` | Sichere Mail-Prüfhelfer und gemeinsame Browsernavigation |
| `1e99e5c4` | Lehrer-Kopfleisten, gemeinsame Gestaltung und Aufgabeneditoren |
| `5ff8cfaa` | Live-Bewertungszustände und Wechsel zur Klassenübersicht |
| `bbcd9014` | Auth-Formulare, Mail-/Tokenzustände und persistenter Countdown |
| `fe13465d` | Erhalt vorhandener Abgaben beim Löschen einer Aufgabe |
| `95f65bfe` | Klarer Abschluss leerer Übungssitzungen und H5P-Isolation |
| `43d8d90a` | Aktualisierte Browserabläufe und 93 weitere visuelle Referenzen (9 Editorbilder bereits im Lehrer-Commit) |
| `711fb45d` | Historische Storage-/HTTP-Prüfungen und sicheres vollständiges Prüfprofil |

Ein abschließender Dokumentationscommit hält diesen Nachweis fest. Alle Commits entstehen lokal auf `master`; es wird nichts gepusht.
