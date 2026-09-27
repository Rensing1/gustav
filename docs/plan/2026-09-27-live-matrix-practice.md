# Implementierungsplan: Live-Matrix mit getrennten Übungsmodulen

Status: Darstellung gemeinsam iteriert und freigegeben; technische Abschlussprüfung am 27.09.2026 erfolgreich abgeschlossen.

## User Story

Als Lehrkraft möchte ich Lernaufgaben und Übungsstand aller Schüler in einer kompakten Matrix vergleichen und aus jeder Zelle direkt zu Aufgabenstellung, Abgabe, Rückmeldung und Auswertung gelangen.

## BDD-Szenarien und automatisierte Nachweise

1. **Lernmatrix nach Modulen**
   - Given eine Lerneinheit mit mehreren Lernmodulen
   - When die Lehrkraft `/live` öffnet
   - Then erscheinen Schüler als Zeilen und nach tatsächlichen Modulen gruppierte Aufgaben als Spalten.
   - Nachweis: View-Model-/Komponententest und `frontend/e2e/live-summary.spec.ts`.
2. **Bewertungszustände**
   - Given offene, unbewertete und numerisch bewertete Abgaben
   - When die Matrix gerendert wird
   - Then bleiben die Zustände durch Wert, Textalternative und die vorhandenen Schwellenwerte unterscheidbar.
   - Nachweis: View-Model- und Komponententest.
3. **Aufgabendetail**
   - Given eine offene oder eingereichte Aufgabe
   - When die Lehrkraft ihre Zelle auswählt
   - Then bleiben Aufgabenstellung und Schüler sichtbar; vorhandene Abgabe, Rückmeldung und Auswertung sind direkt erreichbar.
   - Nachweis: Komponenten-/Interaktionstest und Feature-Acceptance-Test.
4. **Getrennte Übungsmodule**
   - Given die Lerneinheit besitzt Übungsmodule
   - When die Lernmatrix sichtbar ist
   - Then enthält sie nur eine kompakte Spalte `Üben` mit fälligen und aktuell sicheren Aufgaben; die Übungsaufgaben stehen nicht zwischen den Lernaufgaben.
   - Nachweis: API-, View-Model- und Komponententest.
5. **Übungsmatrix und Drill-down**
   - Given die Lehrkraft öffnet die Übungsansicht
   - When ein Schüler und ein Übungsmodul ausgewählt werden
   - Then sind Fälligkeit, Einstufung, letzte Aktivität und die einzelnen Übungsaufgaben sichtbar; eine Aufgabe öffnet den bestehenden Detailpfad.
   - Nachweis: Komponenten-/Interaktionstest und Feature-Acceptance-Test.
6. **Schmale Ansicht**
   - Given eine Breite von 390 CSS-Pixeln
   - When Aufgaben- oder Übungsansicht geöffnet wird
   - Then begrenzt ein Modulwähler die Spalten, das Detail folgt darunter und die Seite selbst läuft nicht horizontal über.
   - Nachweis: Komponentenvertrag und Browserprüfung.
7. **Leere und gesperrte Zustände**
   - Given keine Schüler, keine Abgaben, keine Übungsmodule oder ein gesperrtes Übungsmodul
   - When die Ansicht geladen wird
   - Then zeigt sie knappe fachliche Leer- beziehungsweise Sperrzustände und erfindet keine Werte.
   - Nachweis: API-, View-Model- und Komponententest.
8. **Berechtigungsgrenzen**
   - Given einen Schüler, eine fachfremde Lehrkraft oder eine entfernte Kursmitgliedschaft
   - When Live- oder Übungsdaten angefordert werden
   - Then werden keine fremden Daten ausgegeben.
   - Nachweis: API- und echte Datenbanktests; authentifizierter Browserrundlauf für den Rollenpfad.

## Vertrag und Datenfluss

- Der vorhandene Live-Summary-Endpunkt bleibt der einzige Matrixabruf und wird um Modulart sowie Übungsaggregate erweitert.
- Eine eigentümergeschützte SQL-Funktion liest Übungszustände für die bereits paginierte Schülerliste in einem Bulk-Aufruf. Sie prüft Kursbesitz, Kurs-Lerneinheit-Zuordnung und Mitgliedschaft und verwendet die bestehende Freischaltlogik.
- Die Teaching-Schicht bildet Datenbankzeilen in ein frameworkunabhängiges Read-Model ab. FastAPI bleibt für Authentifizierung, Autorisierung und HTTP-Serialisierung zuständig.
- Das Svelte-View-Model gruppiert Lernaufgaben nach Abschnitt beziehungsweise Modul und hält Darstellungslogik aus der Route heraus. Detailabruf und Live-Polling bleiben erhalten.

## Gestaltungsvertrag

- `docs/DESIGN.md` und die zentralen Theme-Tokens sind verbindlich.
- Die Namensspalte ist sticky und enthält keine Bearbeitungsquote.
- Übungszahlen zählen einzelne Aufgaben: Blau bedeutet neu oder fällig; Grün bedeutet sicher mit einem Fälligkeitszeitpunkt in der Zukunft. Die Mengen sind disjunkt.
- Die Übungsansicht verwendet die Zustände `gesperrt`, `fällig`, `noch nicht sicher`, `teilweise sicher` und `sicher`.
- Nur der beschriftete Tabellenbereich darf horizontal scrollen. Tabelle und Detailbereich stehen bei allen Bildschirmgrößen untereinander; die Aufgabenstellung und Antwort stehen innerhalb des Details auf breiten Flächen nebeneinander.

## Ausführungs- und Prüfgrenze

### Darstellungsiteration nach Rückmeldung

Die folgenden Notizen dokumentieren die Iterationen, neueste zuerst. Frühere Varianten sind durch spätere Rückmeldungen ersetzt; maßgeblich ist der abschließende Gestaltungsvertrag in `docs/DESIGN.md`.

Korrektur der Werkzeugleiste: Aufgabenleiste linksbündig direkt unter dem Schülernamen, weiterhin kompakt. Browserdiagnose: Der wechselnde HTML-Scrollbalken reduziert die linke Detailspalte von rund 470,61 auf 464,93 px. Die Live-Route reserviert deshalb dauerhaft Scrollbalkenplatz; für ältere Browser dient `overflow-y: scroll` als Fallback. Die Route entfernt ihre HTML-Klasse beim Verlassen. Given unterschiedlich lange Detailinhalte, when zwischen allen drei Reitern gewechselt wird, then bleibt die linke Spaltenbreite identisch. Nachweis: gezielter Strukturtest und DOM-Breitenmessung im Browser.

Werkzeugdichte im Schülerdetail: Name und Aufgaben-Navigation teilen auf breiten Flächen eine Kopfzeile. Die Aufgabenleiste selbst bleibt unverändert; ihre Beschriftung behält den reservierten Umbruchraum. Panelpadding und vertikale Abstände werden reduziert; Aufgabentyp und Zeitangabe stehen kompakt zusammen. Given ein gewählter Schüler, then nutzt der Detailkopf auf Desktop eine Zeile und stapelt mobil ohne Seitenüberlauf. Nachweis: Strukturtest für den gemeinsamen Kopf, gezielte Kompilierung und Browserprüfung.

Spacing-Runde: Der Matrixkopf wird zu einer kompakten Zeile mit Überschrift, Bestandsangabe und Umschalter ohne sichtbare redundante Legende. Die Legende bleibt für assistive Technik erhalten. Im Schülerdetail werden Aufgabenleiste und ihre Beschriftung gemeinsam gruppiert, damit der übergeordnete Grid-Abstand nicht zusätzlich zwischen beide tritt. Einheitliche Innenabstände und kontrollierte Textabstände ersetzen kumulierte Standard-Margins. Die reservierte Beschriftungshöhe der unveränderten Aufgabenleiste bleibt erhalten. Nachweis: gezielter Strukturtest, Kompilierung und Browseransicht.

Redundante Detailtexte entfallen: kein sichtbares „Detail“ oberhalb der Reiter und keine wiederholte Beschriftung „Abgabe“, „Rückmeldung“ oder „Auswertung“ im bereits benannten Panel. Given ein aktiver Detailreiter, then bezeichnet allein der Reiter den Inhalt; die zugängliche Panelbeschriftung bleibt erhalten. Nachweis: gezielter Strukturtest und Browserkontrolle.

Die beiden Live-Umschalter erhalten dieselbe transparente Liniengestaltung: ChoiceSwitch für die native Radioauswahl und semantische Tabs für das Detail teilen ihre CSS-Basis. Given eine gewählte Detailansicht, when zwischen Abgabe, Rückmeldung und Auswertung gewechselt wird, then markieren Text und Akzentlinie die Auswahl ohne graue Füllfläche. Ein Strukturtest prüft die gemeinsame Stylingbasis; Browserprüfungen decken Auswahl und Hell/Dunkel ab. Andere Workspace-Reiter bleiben unverändert.

Die freigegebene nächste Variante stellt Tabelle und Schülerdetail bei allen Bildschirmgrößen untereinander dar. Die Tabelle erhält die volle verfügbare Arbeitsbreite, ohne die 48-px-Aufgabenspalten zu strecken. Innerhalb des Details stehen Aufgabenstellung und Antwortbereich auf breiten Bildschirmen nebeneinander, mobil untereinander. Auswahlmarkierung und Scrollposition bleiben unverändert. Given eine ausgewählte Abgabe, when das Detail erscheint, then folgt es unter der Matrix und enthält getrennte Aufgaben- und Antwortbereiche. Nachweis: gezielter Strukturtest sowie Browserprüfung der breiten und schmalen Darstellung, inklusive offener Aufgabe und Detailtabs.

Aufgabenspalten erhalten feste 48 px statt inhaltsabhängiger Breiten. Modultitel werden innerhalb ihrer Spaltengruppe begrenzt und umbrechen; sie dürfen die Zellen nicht auseinanderziehen. Der Ansichtswechsel erhält einen eigenen kompakten Bereich, damit seine globale Vollbreite die Überschrift nicht zusammendrückt. Auswahlleiste, Tabelle und Detailpanel bekommen abgestimmte Abstände und weniger verschachtelte Rahmen. Die Kontrolle erfolgt über Kompilierung und echte Browseransichten mit gemessenen Spaltenbreiten.

- Red-Green-Refactor gilt für OpenAPI, Migration, API und View-Model.
- Nach der ersten vertikalen Implementierung laufen ausschließlich die unmittelbar betroffenen Tests und ein kurzer Kompilierungscheck.
- Anschließend erfolgt die visuelle Browseriteration mit den festen Dev-Personas bei 1600×900, 1024×768 und 390×844 in Hell und Dunkel.
- Erst nach visueller Freigabe folgen die breiten technischen Prüfungen und `make verify-feature FEATURE=live-summary`.
- `make test-feature-regression` bleibt opt-in. Ein Push erfolgt nicht automatisch.

## Technische Abschlussprüfung

Konkrete Testzuordnung:

| Szenarien | Automatisierter Nachweis |
| --- | --- |
| 1, 2, 4, 7 | `frontend/src/routes/live/live-matrix-view.test.ts`: Trennung, Bewertungsgrenzen, offene/unbewertete Zellen und leere Schülerliste |
| 1, 3, 4, 6, 7 | `frontend/src/routes/live/LiveOverviewMatrix.test.ts`: echte Komponenten, Auswahlereignisse, mobile Modulwahl, gesperrte Übungszellen und Leerzustand |
| 3 und Live-Aktualisierung | `frontend/src/routes/live/page-interaction.test.ts`: Detailauswahl, Polling, Cursorfortschritt, Fehler- und Parallelitätsfälle |
| 4, 5, 7, 8 | `backend/tests/migration/test_teaching_live_practice_roundtrip.py`: echte DB, disjunkte neue/fällige/sichere/teilweise/unsichere Aufgaben, Bulk-Schülerliste, Besitzerbindung, Kurszuordnung, Sperren und Mitgliedschaftsentzug |
| 4, 5, 8 | `backend/tests/test_teaching_live_unit_summary_api.py::test_summary_exposes_practice_catalog_counts_and_membership_boundary`: echter API-/DB-Pfad über die Anwendungsrolle, Cache-Header und Rollenprüfung |
| Vertrag und Statuspriorität | `backend/tests/test_openapi_teaching_live_unit_contract.py`, `backend/tests/test_teaching_live_practice_read_model.py`, `backend/tests/migration/test_teaching_live_practice_aggregates_contract.py` |
| 1, 3, 4, 5, 6, 8 | `frontend/e2e/live-summary.spec.ts`: authentifizierter `@feature-acceptance`-Rundlauf mit echter Datenhaltung, echter Schülerabgabe über die Oberfläche, Live-Aktualisierung ohne Neuladen, Detail-Direktlink, stabiler Spaltenbreite beim Reiterwechsel, getrenntem Übungskurs, Tastaturumschaltung, mobiler Darstellung und Lernendenzugriffssperre |

Die ersten Abschlussläufe fanden ein veraltetes DB-Testinventar, alte Browserselektoren und einen doppelten Abschnittsabruf. Die Kataloge verwenden nun dieselben autorisierten Abschnittsdaten. Der Stiltest des ChoiceSwitch berücksichtigt die gemeinsame Selektorbasis mit den Detailtabs. Ein expliziter Leertext ergänzt die Matrix bei leerem Kurs.

Der Browserrundlauf ersetzt ausschließlich das externe KI-Ergebnis deterministisch. Login, Aufgabenbearbeitung, Abgabe, Datenhaltung, Live-Polling und Detailanzeige durchlaufen den echten lokalen Stack. Der lokale Provider-Worker wird dafür kontrolliert pausiert und auch im Fehlerfall wieder freigegeben; der Testlauf bestätigt anschließend die Bereinigung seiner synthetischen Daten.

README-Prüfung: Die vorhandene Galerie zeigt keine Live-Ansicht; ihre Bilder sind durch diese Änderung nicht veraltet. Daher bleiben die Screenshots unverändert. Der Funktionsüberblick beschreibt jetzt ausdrücklich die Lernmatrix und den getrennten Übungsstand.

Commitaufteilung: Datenvertrag/Backend einschließlich zugehöriger Tests und Migration; UI mit Komponenten- und Interaktionstests; Feature-Acceptance-Nachweis und Abschlussdokumentation. Kein Push.

### Abschließende Ergebnisse

`make verify-feature FEATURE=live-summary` wurde gegen den freigegebenen lokalen Stack erfolgreich ausgeführt (Exit-Code 0). Die lokale CA wurde vor den Browserprüfungen geprüft; TLS-Prüfungen blieben unverändert aktiv.

- Backend: 3.042 Tests bestanden, 33 übersprungen, 4 Warnungen.
- Frontend: 166 Testdateien mit 795 bestandenen Tests sowie erfolgreiche ergänzende Build-/CSS- und H5P-Prüfungen.
- Svelte-/TypeScript-Prüfung: keine Fehler und keine Warnungen. Produktionsbuild erfolgreich; 16 dokumentierte Upstream-Warnungen vom bestehenden Warnungsfilter akzeptiert.
- Vertrags-, Architektur-, Inventar-, Abhängigkeits- und Stilprüfungen sowie Docker-Image-Smoke erfolgreich.
- Authentifizierter Feature-Acceptance-Rundlauf: bestanden; Bereinigung der synthetischen Testdaten bestätigt. Der erweiterte Rundlauf bestand auch separat vor dem vollständigen Gate.
- `git diff --check`: erfolgreich. Die historische Gesamt-Feature-Suite wurde nicht ausgeführt.
