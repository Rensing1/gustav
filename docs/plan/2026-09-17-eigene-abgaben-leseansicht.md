# Eigene Abgaben direkt in der Leseansicht

## Auftrag und User Story

Als Schüler möchte ich unter einer Aufgabe meine eigene Abgabe wiedererkennen, vollständig lesen und die zugehörige Rückmeldung und Auswertung öffnen können, ohne dafür die Bearbeitung aufzurufen. Ausgangspunkt ist der bestätigte Entwurf A3. Die später bestätigte visuelle Präzisierung weiter unten ersetzt dessen Kartenrahmen; die Offenlegungslogik bleibt erhalten. Die Mockups wurden auf Wunsch des Nutzers vor dem Commit entfernt; der verbindliche Gestaltungsvertrag ist hier und in `docs/DESIGN.md` dokumentiert.

Die Änderung gilt für Module und lineare Abschnitte. Aufgabenraum, Übungssitzungen und Abgabeprozess behalten ihr Verhalten. Die Aufgabenstellung bleibt sichtbar, ohne Aufklappfunktion. Darunter erscheinen maximal drei gerenderte Vorschauzeilen der eigenen Abgabe; „Ausklappen“ verlängert ausschließlich die Abgabe. An ihrem Ende liegen getrennt aufklappbare „Rückmeldung“ und „Auswertung“. „Einklappen“ schließt auch diese Bereiche. Kurze Antworten benötigen den Schalter nur, wenn zusätzliche Inhalte oder Verarbeitungszustände vorhanden sind.

## Fachliche Entscheidungen

- Neueste endgültige Abgabe zuerst; neuere gespeicherte Entwürfe erhalten einen eigenen Hinweis mit „Entwurf weiterbearbeiten“.
- Ohne endgültige Abgabe erscheint der neueste Feedback-Entwurf als „Mein Entwurf · Noch nicht abgegeben“. Lokale Editorentwürfe erscheinen hier nicht.
- Inhalt und Rückmeldung/Kriterien stammen aus genau demselben Snapshot. Fehlende Bereiche bleiben weg.
- Bildvorschau klein und unverzerrt, aufgeklappt größer; PDFs zunächst Metadaten, aufgeklappt begrenzter Viewer. Programmdateien verwenden bestehende Artefaktdarstellungen. Dialoge zeigen die Abschlussantwort und laden erst beim Öffnen den Verlauf. H5P zeigt nur tatsächlich gespeicherte Angaben, keine rekonstruierten Antworten. Dateinamen werden nicht erfunden.
- Designwerte ausschließlich aus zentralen Tokens; Lernraum-Stylesheet, Hell/Dunkel, Lesebreite ungefähr 68ch, mindestens 44 Pixel Bedienhöhe auch für den dezenten Textbutton. Tastaturfokus und aria-expanded/aria-controls; keine verborgenen interaktiven Details.

## Umsetzung (Contract-first und Red–Green–Refactor)

1. Designvertrag in Abschnitt 11.3 ergänzen. GET `/api/learning/courses/{course_id}/tasks/{task_id}/submissions` erhält optional `intent=submit|feedback`, vor Pagination angewandt. Ungültige Werte: 400/invalid_intent. Ohne Parameter unveränderte Historie. Keine Migration: vorhandene Spalten und Indizes genügen.
2. Rote API-/DB-Tests für Filter, ältere Dateien und Berechtigungen; danach minimale Implementierung in Route, frameworkfreiem Use Case und Repository. Dateiabruf gezielt nach ID unter denselben Zugriffskontrollen, nicht innerhalb der letzten 100 Datensätze.
3. Rote Komponenten-/Ladetests und Browser-Spec; danach `LearningSubmissionPreview` als schreibgeschützten Baustein unter der kompakten Aufgabenzeile integrieren. Vorhandene Markdown-, Datei-, Kriterien- und Dialogbausteine nutzen.
4. Sichtbare Aufgaben laden Vorschauen automatisch, höchstens vier gleichzeitig, doppelte Anfragen zusammenführen. Zuerst endgültige Abgabe mit limit=1; nur falls leer neuester Feedback-Entwurf. Vorschau und vollständige Historie strikt getrennt. Nach neuer Bearbeitung betroffene Vorschau aktualisieren. Keine zusätzliche Persistierung von Abgabetexten.
5. Fehler lokal mit Wiederholungsaktion anzeigen, 401 über bestehende Auth-Erneuerung, bei 403/404 Inhalte verwerfen. Offenlegungen verändern weder URL noch Historie, erhalten ihren Zustand solange montiert und beginnen bei einem neuen Snapshot geschlossen.
6. Refactoring auf verständliche Verantwortungsteilung; erklärende englische Kommentare für Snapshot-Auswahl, Nebenläufigkeit und Sicherheit. Dokumentation und Changelog aktualisieren.

## BDD und automatisierter Nachweis

| Given – When – Then | Nachweis |
| --- | --- |
| Lange endgültige Abgabe; Leseansicht öffnen; drei Zeilen ohne Bearbeitungsaufruf sichtbar | Komponente, authentifizierter Feature-Test |
| Vorschau; Ausklappen; Volltext und geschlossene Rückmeldung/Auswertung | Komponente, Feature-Test |
| Vollansicht; Rückmeldung/Auswertung unabhängig öffnen und Abgabe einklappen; Details verborgen und Fokus erhalten | Komponente, Tastatur-Browsertest |
| Mehr als 100 neuere Entwürfe; Vorschau/Datei öffnen; endgültiger Snapshot bleibt auffindbar | API gegen lokale DB |
| Nur Entwurf oder keine Abgabe; öffnen; korrekte Bezeichnung beziehungsweise kein leerer Block | Komponenten- und Browser-Detailtest |
| Bild/PDF/Programmdatei/Dialog; öffnen; passender vorhandener Renderer | Typbezogene Komponenten- und Browser-Detailtests |
| Kurze Antwort, fehlendes Feedback, laufende Analyse oder Ladefehler; anzeigen; passende Inhalte/Zustände | Komponenten-/Ladetests |
| Fremder Schüler oder entzogene Freigabe; Inhalt/Datei anfragen; kein Zugriff | API-Sicherheitstests gegen lokale DB |
| Erste/letzte Aufgabe im Modul/linearen Abschnitt; bearbeiten und zurückkehren; Zuordnung/Entwurf erhalten | Browser-Detailtests |
| Markdown mit Code, Tabellen, Links und schädlichem HTML; anzeigen; sichere lesbare Ausgabe | Renderer-/Komponententests |

Spec: `learner-submission-preview.spec.ts`. Mindestens ein `@feature-acceptance`-Test durchläuft Login, echte Aufgabenbearbeitung, deterministisch erzeugtes Anbieterfeedback, endgültige Abgabe und Rückkehr samt Offenlegungen. Server und Datenhaltung bleiben echt. Die Spec wird dem vorhandenen WebKit-iPad-Projekt zugeordnet.

## Konkrete Testzuordnung

- `backend/tests/test_learning_submission_preview_api.py`: Filter vor Pagination und unveränderte Historie, ungültiges Intent, endgültige Datei jenseits von 100 neueren Abgaben, Fremdzugriff, Rollenprüfung, Kursaustritt und fehlende Abschnittsfreigabe.
- `frontend/src/lib/learning-unit/submission-preview.test.ts`: endgültige Fassung vor Feedback-Entwurf, leere Ergebnisse, maximal vier Anfragen, Zusammenführung gleicher Anfragen, Wiederholung, Zugriffsentzug, Auth-Erneuerung, Aktualisierungsrennen und lesbare sichere Markdown-Vorschau.
- `frontend/src/lib/components/learning-unit/LearningSubmissionPreview.test.ts`: unabhängige geschlossene Offenlegungen, Fokus, kurzer Inhalt, Fassungswechsel und Erhalt derselben Fassung, Entwurfskennzeichnung, lokale Fehler, Bild/PDF/Programmdateien, verzögertes Laden des Dialogverlaufs, H5P ohne rekonstruierte Antwort sowie laufende/fehlgeschlagene Auswertung.
- `frontend/src/lib/utils/markdown.test.ts`: bestehende Renderer-Prüfungen für sichere Vollansicht, Links, Tabellen, Code und unerwünschtes HTML; die Vorschau verwendet dieselbe Markdown-Grammatik.
- `frontend/src/lib/components/learning-unit/LearnerContentWorkspace.test.ts`: Zuordnung eines neueren Entwurfs trotz identischer Sekunden-Zeitstempel; bestehende Kontext- und Navigationsfälle bleiben erhalten.
- `frontend/e2e/learner-submission-preview.spec.ts`, `@feature-acceptance`: vollständiger authentifizierter Browser-Rundlauf von der Kursseite über Bearbeitung, Feedback und endgültige Abgabe bis zu den drei Offenlegungen, Tastaturfokus und erneutem Laden.
- Dieselbe Spec, `@feature-detail`: gespeicherte/lokale Entwürfe, endgültige Fassung trotz neuerem Entwurf auch nach Neuladen, erste/letzte Aufgaben in Modulen und linearen Abschnitten, echte Bild-/PDF-Uploads, geschützte Dateiabrufe sowie die sechs Größen-/Theme-Kombinationen. Beide Browserprojekte sind einbezogen.

## Verifikation und Abschluss

Vor Browserprüfungen `make local-ca-status`; ausschließlich freigegebener lokaler Stack, keine abgeschwächte Zertifikatsprüfung. Visuell Hell/Dunkel bei 1920 × 1080, 1024 × 768 und 390 × 844 prüfen, einschließlich Tastatur, Touch-Zielgrößen und fehlendem horizontalem Seitenüberlauf. Gezielte Detailtests und `make verify-feature FEATURE=learner-submission-preview` müssen erfolgreich sein. Keine historische Gesamtsuite ohne Auftrag. Danach Dokumentation der Ergebnisse und Commit auf master; kein Push.

## Visuelle Präzisierung nach der ersten Umsetzung

Die visuelle Abnahme beanstandet die geringe Lesbarkeit der Aufgabenstellung, die konkurrierenden Rahmen und den Leerraum bei kurzen Antworten. Gewählte Richtung: eine leicht eingerückte Antwort ohne eigene Karte. Aufgabe und Abgabe bilden einen zusammenhängenden Lesebereich; Metadaten sind nachgeordnet. Die Aufgabenstellung wird mindestens in der normalen Leseschriftgröße dargestellt. Bearbeitungsaktionen für bestehende Abgaben verlieren ihren Schatten und ihre Versalschreibung. Kurze Antworten sollen einschließlich Kennzeichnung und Aufklappaktion auf breiten Ansichten höchstens 112 Pixel belegen. Die Bedienhöhe von 44 Pixeln bleibt erhalten; drei Zeilen sind eine Obergrenze, keine Mindesthöhe. Die ursprüngliche Offenlegungslogik bleibt verbindlich. Auch geöffnet gibt es keine Außenkarte: Rückmeldung und Auswertung verwenden gleich große Schrift, links platzierte Chevrons, mindestens 44 Pixel Bedienhöhe und jeweils eine einzelne feine Trennlinie. Die Anzahl der Kriterien bleibt als nachgeordnete Information in derselben Zeile. Browserprüfungen sichern Lesbarkeit, kompakte Höhe und alle drei Bildschirmgrößen ab.

## Zweite visuelle Präzisierung und Freigabevorbehalt

Die weitere Abnahme mit kurzen und langen realen Antworten verlangt ein zusammenhängendes Leseraster: Die gesamte Aufgabe mit eigener Antwort erhält eine ruhige, rahmenlose Grundfläche ohne durchscheinendes Punktraster. Aufgabenzeile und Materialtitel teilen ihre äußere Einrückung; die eigene Antwort folgt genau eine Abstandsstufe weiter innen. Beschriftung, Antworttext und Texte der Offenlegungen stehen auf derselben Antwortachse, deren Chevrons leicht ausgerückt sind. Metadaten unterscheiden sich durch Gewichtung und einen sichtbaren Trenner. Die Antwort bleibt auf ungefähr 68 Zeichen pro Zeile begrenzt; Bearbeitungs- und Aufklappaktionen teilen die äußere rechte Achse. Auf breiten Ansichten nutzt eine geschlossene kurze Antwort dieselbe Zeile wie die Aufklappaktion, auf schmalen Ansichten bleiben Aktionen darunter. Die Offenlegungen erhalten einen bewussten Abstand nach der Antwort. Sichtung und Browserprüfungen berücksichtigen ausdrücklich kurze und lange Texte sowie beide Offenlegungszustände.

**Kein Commit ohne ausdrückliche Freigabe des Nutzers.** Das frühere automatische Commit-Abschlusskriterium ist durch diese neuere Anweisung aufgehoben. Der Stand wird zuerst lokal umgesetzt, geprüft und zur visuellen Abnahme gezeigt. Die ausdrückliche Freigabe erfolgte am 17.09.2026 mit „Sieht gut aus. Bitte committen.“.

## Arbeitsnachweise

- Contract-first: `intent` zuerst im OpenAPI-Vertrag ergänzt. Zwei neue API-Tests waren zunächst rot (Filter vor Pagination und Datei außerhalb der letzten 100 Abgaben); nach Durchreichen der optionalen Filter durch Use Case und Repository erfolgreich. Die vier neuen API-/Sicherheitstests laufen gegen die echte lokale DB; die gezielte Auswahl bestehender Listen-/Dateitests bestand ebenfalls.
- TDD im Frontend: Vorschauauswahl, begrenzte Nebenläufigkeit, Fehler/Wiederholung, geschlossene Offenlegungen, Fassungswechsel und Dateitypen zunächst durch Tests beschrieben. Gleichzeitige Fassungen werden über Abgabenummern unterschieden, damit Zeitstempel mit Sekundenauflösung keinen neueren Entwurf verbergen. Die laufende Vorschauaktualisierung bewahrt offene Details, solange dieselbe Abgabe angezeigt wird.
- Visuelle Korrektur: Die kurze Antwort belegte zunächst 146 Pixel und verletzte den neuen Test (höchstens 112 Pixel). Nach Entfernen von Kartenrahmen und Kopfzeilenteilung besteht der Test. Aufgabenstellung in Leseschriftgröße, einheitliche Offenlegungen mit 44-Pixel-Zielen und zurückhaltende Bearbeitungsaktionen sind im Lernraum-Stylesheet gekapselt. Ein entdeckter intrinsischer Breitenüberlauf der Materialspalten wurde ohne Abschneiden von Inhalten behoben.
- Datei- und Sondertypen: Echte Bild- und PDF-Uploads sowie authentifizierte Dateiabrufe in Chromium/WebKit; Scratch, Calliope, Filius, verzögert geladene Dialoge und H5P über typbezogene Komponentenprüfungen. Die PDF-Fixture ist ein synthetisches einseitiges Dokument ohne personenbezogene Inhalte. Bestehende Code-/Strukturdarstellungen erhalten nur eine Originaldatei-Aktion.
- Lokaler Stack: CA-Vertrauen und Supabase geprüft; lokale Dienste gebaut. Keine neuen ENV-Werte, keine Schemaänderung, keine Migration, keine Browser-Speicherung von Vorschauinhalten.
- Visuelle Sichtung: Hell/Dunkel bei 1920 × 1080, 1024 × 768 und 390 × 844. Browserprüfungen kontrollieren drei Vorschauzeilen, kompakte Kurzantworten, einheitliche Offenlegungen, Fokus, 44-Pixel-Ziele und fehlenden horizontalen Seitenüberlauf. Sechs Detail-Rundläufe in Chromium und WebKit bestanden, einschließlich der zusätzlichen Navigation zur letzten Modulaufgabe.
- Vollständiges Gate `make verify-feature FEATURE=learner-submission-preview`: erfolgreich vor dem zweiten visuellen Feinschliff. 3.028 Backend-Tests bestanden, 33 bestehende Opt-in-Fälle übersprungen; 762 Frontend-Tests in 163 Dateien bestanden, Typprüfung ohne Fehler/Warnungen, Build, allgemeine Vertrags-/Architektur-/Containerprüfungen sowie zwei authentifizierte Akzeptanzläufe erfolgreich. Das durch die neue DB-Testdatei veraltete Testinventar wurde regeneriert.
- Zweiter visueller Feinschliff: Die neue Abnahme für den ruhigen Hintergrund war zunächst rot. Danach in beiden Browsern grün: sechs Detailläufe einschließlich kurzer/langer Antworten, maximal 16 Pixel Abstand im gespeicherten Lesestand ohne Statusmeldung, gemeinsame rechte Aktionsachse sowie alle Bildschirmgrößen und Themes. Leere Editorbereiche erzeugen keinen zusätzlichen Abstand. Die 762 Frontend-Tests, Typprüfung und lokaler Container-Build wurden erneut erfolgreich ausgeführt. Anschließend bestanden auch beide authentifizierten Akzeptanzläufe mit Tastatur und den Vergleichsansichten erneut.
- Abschließendes Gate nach visueller Freigabe: `make verify-feature FEATURE=learner-submission-preview` erneut vollständig erfolgreich. 3.028 Backend-Tests bestanden, 33 übersprungen; 762 Frontend-Tests bestanden, Typprüfung ohne Fehler/Warnungen, Build und allgemeine Prüfungen erfolgreich. Beide authentifizierten Akzeptanzläufe in Chromium und WebKit bestanden; deren Testdaten wurden vollständig bereinigt. Das lokale CA-Vertrauen wurde vor den Browserprüfungen erneut bestätigt.
- Freigabestatus: visuell abgenommen, Commit ausdrücklich freigegeben und vollständiges Feature-Gate am freigegebenen Stand bestanden. Mockups einschließlich ihrer Begleitdokumente auf ausdrücklichen Wunsch entfernt. Kein Push.
