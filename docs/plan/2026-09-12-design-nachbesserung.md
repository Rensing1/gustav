# Nachbesserung: Header, Hauptaktionen und Live-Übersicht

## Auftrag und Designentscheidungen

Ausgangspunkt `cce2c83f` auf `master`. Drei von Felix im Browser gemeldete Probleme korrigieren: ungleiche mobile Headeraktionen, dezente Fortsetzung eines Entwurfs trotz Hauptaktion und Verlust der kompakten Live-Übersicht. Keine API-, Schema-, Berechtigungs- oder Bewertungsänderungen. Keine Änderungen an fremden Dev-Lernständen, kein Push.

Theme- und Benutzerbutton teilen mobil eine Höhe von 44 px und mindestens 44 × 44 px Bedienfläche; Desktop bleibt erhalten. Beginnen und Entwurf fortsetzen verwenden dieselbe orange Variante in beiden Aufgabendarstellungen, endgültig abgegebene Aufgaben behalten „Erneut bearbeiten“ als dezente Aktion.

Live zeigt Aufgaben als fortlaufendes Raster kleiner farbiger Rechtecke in bestehender Reihenfolge statt großer Buttons und Modulüberschriften. Desktop-Bedienfläche 24 × 24 px; bei höchstens 48 rem Breite oder grobem Zeiger 44 × 44 px. Eine gemeinsame Beschriftung nennt Modul, Nummer und Zustand der fokussierten, überfahrenen beziehungsweise ausgewählten Aufgabe (Priorität in dieser Reihenfolge). Kein neuer Datenabruf. Auswahl und letzte Abgabe bleiben zusätzlich zur Bewertungsfarbe erkennbar.

## Rot → Grün → Aufräumen / QA-Inventar

| Gegeben / Wenn | Dann und Nachweis |
| --- | --- |
| Beide Rollen, Header bei 1440/1024/390/320 px in Light/Dark | Gleiche Nachbarhöhen und Ausrichtung; mobil mindestens 44 × 44 px; `design-system-consistency` plus Bilder. |
| Neue Aufgabe neben gespeichertem Entwurf, Öffnen und Themewechsel | Gleiche Hauptaktionsvariante, Entwurf bleibt unverändert; beide Layoutvarianten zusätzlich mit Komponententests. Endgültige Abgabe bleibt dezent. |
| 13 Module mit je einer Aufgabe sowie mehrere Aufgaben eines Moduls | Fortlaufende kleine Rechtecke, keine Überschriftenzeile pro Modul; 13 Aufgaben passen bei 320 px Leistenbreite in höchstens drei Reihen. `teaching-overview-consistency` plus gesamte rechte Spalte als Bild. |
| Erste/letzte Aufgabe, Hover, Tab-Fokus, Auswahl und Neuladen | Passende gemeinsame Beschriftung, gültige Navigation, erhaltene Auswahl und klare Zustände. Leere und unbewertete Abgabe nicht als Bewertung ausgeben. |
| Grober Zeiger auf breitem Bildschirm sowie schmaler Bildschirm | Größere Zielbereiche, unverändert kompakte Farbfelder; echte Touch-/Tastaturbedienung. |

Vor Implementierung fehlschlagende Komponenten-/Style-/Browsertests. Danach gezielte Tests, Frontend neu bauen und erst nach abgeschlossenem Containerstart Browser testen. Browser und Datenbanktests ausschließlich nacheinander. Beide vollständigen Gates `make verify-feature FEATURE=design-system-consistency` und `make verify-feature FEATURE=teaching-overview-consistency` erforderlich. Bilder tatsächlich sichten, nicht durch Referenzaktualisierung akzeptieren. Kurze zusätzliche Erkundung: Wechsel zwischen Fokus und Hover sowie Rückkehr nach Theme-/Viewportwechsel.

## Abschluss

Frühere Abnahmen DS-03/DS-21 sowie Headerprüfung ausdrücklich um die übersehenen Fälle berichtigen. Ein lokaler Korrektur-Commit nach grünen Gates und Bildprüfung. Keine vollständige Geräte-/Screenreader-Abnahme ableiten.

## Arbeitsprotokoll

- Plan und QA-Inventar vor Produktänderungen angelegt. Playwright-Skill gelesen; `js_repl` fehlt, daher vorhandene Testinfrastruktur mit getrennter Bildprüfung ohne abgeschwächtes TLS.

## Korrigierte Entscheidung: ursprüngliche Aufgabenleiste

Felix verwirft den ersten Nachbesserungsentwurf und benennt ausdrücklich nur die kompakte Aufgabenleiste aus `origin/master` (`3edfcc26`) als Referenz, nicht die restliche rechte Spalte. Für die Leiste ersetzt diese Entscheidung die obige 24-/44-px-Regel: ursprüngliches Raster mit 0,85 rem breiten und mindestens 1,15 rem hohen farbigen Rechtecken, 0,28 rem Rasterabstand und ursprünglichen Light-/Dark-Farben sowie Auswahl-/Letzte-Abgabe-Markierungen. Keine zusätzliche transparente Bedienfläche, keine automatische Aufweitung auf Touch-Geräten. Dadurch bleiben die früheren kleinen Touch-Ziele eine bekannte Bedienbarkeitsgrenze. Zugängliche Namen, Navigation und gemeinsame Beschriftung bleiben erhalten.

Vor der Wiederherstellung prüft ein fehlschlagender Stiltest Raster, Maße, ursprüngliche Zustandspalette und den Verzicht auf vergrößernde Breakpoints. Der Browser prüft Maße, Dichte, erste/letzte Auswahl, Fokus, Hover und Touch-Navigation bei allen vier Breiten. Die frühere rechte Spalte wird nicht zurückgesetzt.

Der Browser deckt zusätzlich einen Wechselwirkungstest auf: Am unteren Seitenende darf eine beim Hover kürzer werdende Beschriftung die Leiste nicht unter dem Zeiger verschieben. Die Beschriftung reserviert deshalb zwei Textzeilen; die ursprüngliche Rechteckgeometrie bleibt davon unberührt.

Bei der abschließenden Durchsicht wird außerdem Mausklick-Fokus von Tastaturfokus getrennt: Nur `:focus-visible` erhält Vorrang vor Hover. Ein zusätzlicher zunächst fehlschlagender Komponententest und die echte Klick-dann-Hover-Folge im Browser sichern ab, dass die Beschriftung nach einem Mausklick nicht am alten Rechteck hängen bleibt.

Zusatzbefund außerhalb der drei Korrekturen: Die bereits vorhandenen Materialkarten auf der Modulseite ragen bei 390 px bis x=411 über den Bildschirm. Aufgabenzeilen und Header bleiben innerhalb der Breite. Dieser Materialbefund wird nicht als behoben ausgegeben und nicht durch einen beiläufigen Umbau erweitert; die neue Modulprüfung begrenzt ihre Größenbehauptung ausdrücklich auf die korrigierten Aktionen.

## Prüfnachweise

- Rot: Header-Nachbarn unterschieden sich mobil um rund 7,2 px; beide Entwurfsvarianten waren dezent; Live hatte große Aktionen statt kleiner Rechtecke. Die anschließend verworfene 24-/44-px-Variante scheiterte am neuen Originalraster-/Palettentest. Alle produktbezogenen Rotfälle wurden vor ihrer jeweiligen Korrektur ausgeführt.
- Grün: 109 gezielte Komponenten-/Vertragstests. Beide isolierten Browser-Rundläufe bestanden vor den vollständigen Gates (`teaching-overview-consistency`: 39,6 s; `design-system-consistency`: 36,4 s). Testzustände wurden automatisch bereinigt; keine Dev-Lernstände zurückgesetzt.
- Sichtprüfung: 16 Headerbilder (beide Rollen), acht Modulbilder und 32 rechte Live-Spalten sowie zwei Touch-Bilder in Light/Dark bei 1440/1024/390/320 px. Bei 320 px verdeckt der angeheftete Header teilweise den oberen Rand einzelner Element-Screenshots; deshalb zusätzlich die unüberdeckten Ausschnitte der vollständigen Seitenaufnahmen gesichtet. Kein Überlauf der korrigierten Aktionen oder Live-Leiste. Der separate Materialüberlauf bleibt sichtbar und offen.
- Live: 13 Module mit einer Aufgabe plus ein Modul mit zwei Aufgaben; bei 320 px zwei Rechteckreihen, sonst eine. Erste/letzte Aufgabe, Fokus vor Hover, Auswahl nach Neuladen und Touch-Navigation bestanden. Leere und unbewertete Abgabe samt Auswahl-/Letzter-Abgabe-Markierung im Browser gesehen; Bewertungsschwellen und ursprüngliche Palette zusätzlich durch Komponenten-/Stiltests abgesichert, keine neue Browserabnahme aller numerischen Bewertungszustände behauptet.
- Beispielbilder: [Header mobil](assets/2026-09-12-design-nachbesserung/header-learner-390-dark.png), [Hauptaktionen](assets/2026-09-12-design-nachbesserung/module-actions-1440-light.png), [kompakte Leiste](assets/2026-09-12-design-nachbesserung/live-empty-panel-1440-dark.png), [Touch mit Abgabe](assets/2026-09-12-design-nachbesserung/live-touch-1024-light.png).
- Beide vollständigen Gates bestanden: `make verify-feature FEATURE=design-system-consistency` (Browser 37,3 s) und `make verify-feature FEATURE=teaching-overview-consistency` (Browser 40,5 s). Jeweils 3.044 Backend-Tests bestanden, 33 vorgesehene Auslassungen; 742 Frontend-Tests in 159 Dateien, Typprüfung ohne Fehler/Warnungen, Build und 68 H5P-Tests erfolgreich. Auch die abschließende Klick-dann-Hover-Folge ist im echten Browser grün. Lokaler Korrektur-Commit freigegeben; kein Push.
- Erster vollständiger Durchlauf: 3.043 Backend-Tests bestanden, ein alter Dateistrukturtest suchte die Leistenfarben noch in `+page.svelte`. Nach der Auslagerung prüft er nun ausdrücklich Einbindung, Aufgaben-/Auswahlübergabe, Detailnavigation und dieselben Zustände in `LiveTaskStrip.svelte`. Der gezielte Backend-Vertragstest besteht; ebenso alle 741 Frontend-Tests in 159 Dateien und die Typprüfung ohne Fehler oder Warnungen. Vollständige Gates anschließend erneut gestartet.
- Zweiter vollständiger Durchlauf: 3.044 Backend-Tests bestanden, 33 vorgesehene Auslassungen. Der Frontend-Gesamtlauf meldet trotz bestandener Einzelassertionen verspätete Formularantworten nach Abbau der Testumgebung. Drei bestehende reine Editor-/Warnungs-Komponententests lösen versehentlich echten Formulartransport aus; dieser wird über den vorhandenen `enhanceSubmit`-Abbruch gezielt unterbunden. Die Tests prüfen weiterhin Entwurfssicherung und Warnungsentscheidung; echter Transport und endgültige Abgabe bleiben Bestandteil des authentifizierten Browsertests. Der neue Leisten-Komponententest verhindert außerdem die simulierte native Navigation so wie der echte Seiten-Controller. Keine Produktlogik wird wegen eines Testfehlers verändert.
