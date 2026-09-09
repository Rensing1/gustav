# Paket 4: Browser-Befundkatalog der Lernenden-Arbeitsfläche

Nachtrag vom 9. September: Diese Untersuchung war für einen plattformweiten Designvergleich zu eng. Insbesondere fehlten die abweichenden Buttons in `/learning/practice` und die Lehrkraftseiten. Der [rollenübergreifende Ergänzungskatalog](2026-09-09-design-befundkatalog.md) dokumentiert diese Lücke und die neue Browserprüfung; die folgenden älteren Befunde bleiben als gesonderte Aufgabenraum-Stichprobe erhalten.

Stand: 8. September 2026. Ergebnis: **sieben bestätigte Abweichungen und ein Gestaltungsvorschlag**, dazu zwei gesonderte Prüfhinweise. Dies ist eine priorisierte Browser-Stichprobe, keine vollständige Freigabe der Oberfläche und noch kein Implementierungsauftrag für einzelne Lösungen.

## Grundlage und Reichweite

- Geprüft wurde die laufende lokale GUSTAV-Installation über `https://app.localhost`, mit echtem Dev-Schüler-Login und vorhandenen synthetischen Inhalten. Quellabgleich auf `master`, Stand `a2666b77`. Die Installation wurde nicht neu gebaut; eine vollständige Gleichheit aller laufenden Container mit diesem Commit ist nicht nachgewiesen.
- Chromium **153.0.8010.12**, Desktop **1440 × 1000**, Tabletgröße **1024 × 768**, Mobilgröße **390 × 844** CSS-Pixel; Aufgabenflächen in Light und Dark. Größenprüfungen erfolgten im Desktop-Browser, nicht auf einem echten Touchgerät und nicht mit Safari/WebKit.
- Bereiche: Lernraum → Kurs → Lernpfad → Module → Textaufgaben, vorhandene Rückmeldung/Kriterien/Abgabe, Materialkontext, Großlesen, Dateiauswahl, Layouteinstellungen und H5P-Minimalinhalt. Offene, erledigte und gesperrte Knoten wurden betrachtet.
- Maßstab ist [DESIGN.md](../DESIGN.md), insbesondere Abschnitte 3, 4, 9 und 11. Keine externe Designvorlage wurde neu abgerufen. Die Untersuchung trennt sichtbare Gestaltung, Bedienverhalten und zugängliche DOM-Beschriftung; sie ersetzt keinen Test mit einem Screenreader.
- P2 = regulär zu behebende Abweichung mit Auswirkung auf Orientierung, konsistente Bedienung oder Zugänglichkeit. P3 = geringere Priorität beziehungsweise gestalterische Verbesserung. In dieser Stichprobe kein bestätigter P1-Blocker. Daraus folgt keine Aussage über ungeprüfte Abläufe.

## Übersicht

| ID | Priorität | Befund | Einordnung |
| --- | --- | --- | --- |
| UI-01 | P2 | Rückmeldung, Kriterien und Abgabe verwenden noch eine abweichende Hierarchie | Design-/Komponentenabweichung |
| UI-02 | P2 | Materialkontext ist in zwei Bereiche aufgeteilt statt eines gemeinsamen Modulbaums | Design-/Strukturabweichung |
| UI-03 | P2 | Lerneinheitentitel wird mobil in der Kopfzeile abgeschnitten | Reproduzierbarer Darstellungsfehler |
| UI-04 | P2 | Antworteditor trägt den technischen zugänglichen Namen `text_body` | Zugänglichkeitsabweichung |
| UI-05 | P2 | Aufgabenraum enthält einen zweiten, verschachtelten Hauptbereich | Semantische Strukturabweichung |
| UI-06 | P2 | Graph enthält englische Zoom-Namen und technische Verbindungs-IDs im Accessibility-Baum | Zugänglichkeitsabweichung |
| UI-07 | P3 | Unterschiedliche Materialbilder haben denselben generischen Alternativtext | Zugänglichkeitsabweichung |
| UI-08 | P3 | Mobile Aufgabenfläche verbraucht viel Höhe vor dem eigentlichen Schreiben | Gestaltungsvorschlag, kein Funktionsblocker |

## Befunde mit Reproduktion und Zielzustand

### UI-01 – Rückmeldung und Abgabe sind noch nicht einheitlich aufgebaut

**Reproduktion:** Im vorhandenen Testkurs „Start und Überblick“ öffnen, die Textaufgabe über „Erneut bearbeiten“ aufrufen und „Rückmeldung“, „Auswertung“ und „Entwurf“ öffnen. Keine neue Abgabe notwendig.

**Beobachtung:** Drei gleichrangige Offenlegungen statt Rückmeldung mit untergeordneten Kriterien und einer getrennten „Meine Abgabe“. Die beiden Abschlussaktionen besitzen nicht die im Vertrag beschriebene gemeinsame Überschrift „Dein nächster Schritt“. Der Quellabgleich bestätigt, dass `LearningTaskCard.svelte` diesen Bereich separat rendert, während `LearningResponseGroup.svelte` bereits die andere Hierarchie anbietet. Das ist nicht nur eine abweichende Beschriftung in alten Testdaten.

**Ziel:** Ein verständlicher Zusammenhang zwischen Hinweisen, Kriterien und dem dazugehörigen Snapshot; dieselbe Komponentenfamilie in Arbeits- und Ergebnisansichten. Überarbeiten und Finalisieren bleiben fachlich unverändert. Vor einer Migration die bisherige Offenlegungs-, Fokus- und Snapshot-Zuordnung mit Tests sichern.

**Nachweis:** [Desktop, Dark](assets/2026-09-08-lernenden-ui/05-feedback-desktop-dark.png), [Tablet, Light](assets/2026-09-08-lernenden-ui/16-feedback-tablet-light.png). Designvertrag 11.4.

### UI-02 – Zwei Materialbereiche statt eines durchgängigen Modulbaums

**Reproduktion:** Erst „Start und Überblick“, dann „Interaktiv üben und reflektieren“ öffnen. Zur Textaufgabe im ersten Modul zurückkehren und „Weitere Materialien und eigene Abgaben“ aufklappen.

**Beobachtung:** Aktuelle Materialien stehen zuerst direkt unter „Materialien“. Darunter verbirgt eine zusätzliche Offenlegung den Modulbereich samt eigenen Abgaben. Das aktuelle Modul erscheint dort nochmals als Überschrift. Die eigentliche Modulhierarchie ist damit erst nach zusätzlichem Aufklappen verständlich. `LearnerTaskContext.svelte` setzt hierfür ausdrücklich einen fokussierten Materialbereich und einen getrennten weiteren Materialbereich zusammen.

**Ziel:** Der im Vertrag beschriebene flache Modulbaum: aktives Modul oben und geöffnet, weitere Module zunächst geschlossen, Materialien und „Eigene Abgaben“ darunter. Bestehende Inhalte, Lesepositionen, offene Dokumente und Schutz des aktiven Moduls erhalten; keine neue Quellenverwaltung.

**Nachweis:** [Geöffneter Materialkontext](assets/2026-09-08-lernenden-ui/14-material-structure-desktop.png). Designvertrag 11.4.

### UI-03 – Mobil abgeschnittener Lerneinheitentitel

**Reproduktion:** Die Einheit „Digitale Systeme untersuchen“ bei 390 × 844 Pixeln in einer Aufgaben- oder Materialansicht öffnen. Nach Ende aller Größen-/Themeübergänge erneut betrachten.

**Beobachtung:** Der letzte Breadcrumb wird mitten im Wort abgeschnitten, ohne Auslassungszeichen. Der Breadcrumb-Bereich endet bei x = 362 Pixeln, der Titel reicht bis ungefähr x = 383 Pixeln. Der Titel verwendet `overflow: visible` und `text-overflow: clip`, wird aber von einem übergeordneten Bereich begrenzt. Das Dokument hat trotzdem exakt 390 Pixel Scrollbreite: Ein einfacher Test auf Seitenüberlauf entdeckt den Fehler nicht. Light und Dark sind betroffen.

**Ziel:** Eine erkennbare, zugängliche Kürzung oder ein geordneter Umbruch innerhalb der bestehenden Kopfzeile; keine zusätzliche Navigation. Neben der Dokumentbreite die tatsächlichen Text- und Containergrenzen prüfen.

**Nachweis:** [Mobil, Light](assets/2026-09-08-lernenden-ui/09-task-mobile-light.png), [Mobil, Dark](assets/2026-09-08-lernenden-ui/19-task-mobile-dark-stable.png). Designvertrag 3.3 und 9; relevante Komponente `BreadcrumbBar.svelte`.

### UI-04 – Technischer Name des Antworteditors

**Reproduktion:** Eine native Textaufgabe öffnen, den vollständig geladenen Editor mit der Tastatur erreichen und seine zugängliche Beschriftung untersuchen.

**Beobachtung:** Das editierbare Element besitzt `aria-label="text_body"`. Die anfängliche Textarea wird im Accessibility-Baum ebenfalls mit diesem Namen angeboten. Nach Initialisierung ist ein editierbarer Bereich mit `tabindex="0"` vorhanden, aber ohne explizite Textbox-Rolle. Die tatsächlich angesagte Rolle muss zusätzlich mit einem Screenreader geprüft werden; der technische Name ist bereits eindeutig belegt. `MarkdownWysiwygEditor.svelte` verwendet standardmäßig den technischen Feldnamen als `ariaLabel`.

**Ziel:** Ein deutscher, fachlicher Name wie „Deine Antwort“, eine nachvollziehbare Verbindung zu Aufgabenstellung und Fehlermeldungen sowie gleichwertige Semantik vor und nach Editorinitialisierung. Formatierungswerkzeuge und Tastaturbedienung erhalten.

**Nachweis:** DOM-/Accessibility-Prüfung; zugehörige Oberfläche [Texteditor](assets/2026-09-08-lernenden-ui/13-task-desktop-reloaded.png). Der Screenshot allein belegt den zugänglichen Namen nicht. Designvertrag 9.

### UI-05 – Verschachtelte Hauptbereiche

**Reproduktion:** Eine Text- oder H5P-Aufgabe öffnen und die Hauptbereiche im DOM beziehungsweise Accessibility-Baum prüfen.

**Beobachtung:** Die Seite enthält zwei `main`-Elemente: den äußeren Arbeitsbereich und darin `main aria-label="Bearbeitung"`. Das innere Element wird in `LearnerContentWorkspace.svelte` gerendert. Es handelt sich um zwei gleichzeitig sichtbare Hauptbereiche, nicht nur um einen versteckten, montiert gebliebenen Kontext.

**Ziel:** Ein Hauptbereich pro Ansicht; untergeordnete, sinnvoll benannte Regionen für Kontext und Bearbeitung. Vor der Änderung einen semantischen Regressionstest ergänzen. Sichtbares Layout muss dafür nicht neu gestaltet werden.

**Nachweis:** DOM-Zählung `main = 2` und verschachtelter Accessibility-Baum in Desktop- und Mobilaufgaben. Designvertrag 9. Ein tatsächlicher Screenreader-Rundlauf steht noch aus.

### UI-06 – Graphbeschriftungen enthalten Implementierungsdetails

**Reproduktion:** Lernpfad öffnen; Zoomknöpfe und Verbindungen im Accessibility-Baum betrachten.

**Beobachtung:** Die Zoomknöpfe heißen „Zoom In“ und „Zoom Out“, während die zusätzlichen Aktionen deutsch beschriftet sind. Verbindungen werden als „Edge from <Modul-ID> to <Modul-ID>“ angeboten. Die IDs sind hier technische Kennungen, keine nachgewiesene Offenlegung personenbezogener Daten; für die Orientierung sind sie dennoch ungeeignet.

**Ziel:** Deutsche Zoombezeichnungen und fachlich verständliche Verbindungstexte oder eine gleichwertige zugängliche Beschreibung der Abhängigkeiten. Verbindungen nicht ersatzlos vor Hilfstechnologien verstecken. Weil die Graphbasis gemeinsam ist, eine spätere Korrektur gegen beide Rollen prüfen; eine neue Lehrkraft-Browserprüfung war nicht Teil dieser Stichprobe.

**Nachweis:** Accessibility-Baum; [zugehöriger mobiler Graph](assets/2026-09-08-lernenden-ui/12-graph-mobile-light.png). Die sehr kleine Darstellung nach bewusster „Gesamtansicht“ ist ausdrücklich kein Befund: Sie entspricht dem bestehenden Graphvertrag. Designvertrag 9 und 11.2.

### UI-07 – Generischer Alternativtext für Materialbilder

**Reproduktion:** Bildmaterial in „Start und Überblick“ und „Materialien analysieren“ öffnen und den zugänglichen Bildnamen prüfen.

**Beobachtung:** Sowohl „Bausteine eines digitalen Systems“ als auch „Vereinfachtes Datendiagramm“ besitzen nur `alt="Materialvorschau"`. `LearningMaterialCard.svelte` setzt diesen Text fest. Die vorhandenen Titel werden nicht zur Unterscheidung genutzt.

**Ziel:** Mindestens den jeweiligen Materialtitel zur Identifikation verwenden. Eine echte inhaltliche Bildbeschreibung ist davon zu unterscheiden und darf nicht aus dem Titel erfunden werden. Falls zusätzliche Autoreneingaben nötig werden, wäre dies ein separater fachlicher Schritt mit API-/Schema-Prüfung.

**Nachweis:** DOM-/Accessibility-Prüfung beider Bilder. Designvertrag 9 und 11.4. Die einfarbigen synthetischen Testbilder selbst sind kein Produktfehler.

### UI-08 – Mobile Fläche vor dem Schreiben verdichten

**Reproduktion:** Textaufgabe bei 390 × 844 Pixeln mit Standardschriftgröße am Seitenanfang öffnen.

**Beobachtung:** Kopfzeile, zwei Rückwege, Statuszeile, Kontextumschalter, eine gerahmte Aufgabenstellung mit zusätzlicher Innenfläche und Antwortform nehmen fast die gesamte erste Bildschirmhöhe ein. Der eigentliche Schreibbereich beginnt bei der kurzen Beispielaufgabe erst bei ungefähr y = 809 Pixeln. Die Bearbeitung ist durch Scrollen erreichbar; das ist kein Funktionsausfall.

**Vorschlag:** Bei der Angleichung zuerst überflüssige Innenflächen und vertikale Abstände prüfen. Aufgabenstellung und Rückwege nicht entfernen und nicht durch einen neuen Ablauf ersetzen. Den verbindlichen flachen Aufgabenraum als Maßstab verwenden; genaue Verdichtung anhand eines Vorher-/Nachher-Bildes entscheiden.

**Nachweis:** [Mobil, Light](assets/2026-09-08-lernenden-ui/09-task-mobile-light.png), [Mobil, Dark](assets/2026-09-08-lernenden-ui/19-task-mobile-dark-stable.png). Designvertrag 11.3 und 11.4. Dies ist ein Gestaltungsvorschlag, kein zusätzlicher bestätigter Bedienfehler.

## Zusätzliche Prüfhinweise, nicht als bestätigte Fehler gezählt

1. **Scrollkoordination beim Aufgabenwechsel:** Beim ersten Wechsel aus der gescrollten Modulansicht lag der Kontextkopf teilweise unter dem klebenden Aufgabenkopf. [Beobachteter Zustand](assets/2026-09-08-lernenden-ui/03-task-desktop-light.png), [korrekter Zustand nach Neuladen](assets/2026-09-08-lernenden-ui/13-task-desktop-reloaded.png). In einem weiteren Aufgabenwechsel trat die Überdeckung nicht erneut auf. Deshalb vor einer Änderung eine deterministische Reproduktion mit Ausgangsscrollposition und Fokus herstellen; nicht aus einem einzelnen Bild eine allgemeine Höhenkorrektur ableiten.
2. **Ansprache in vorhandener KI-Rückmeldung:** Die betrachtete Rückmeldung verwendet „Sie/Ihnen“, während die Oberfläche „du/deine“ verwendet. Das betrifft gespeicherten KI-Inhalt, nicht nachweislich die heutige Generierung. Als Beobachtung für die getrennte DSPy-/Feedbackberatung vormerken; weder Promptänderung noch Neugenerierung sind Bestandteil dieses Katalogs.

## Was in der Stichprobe funktioniert hat

- Echter Login, Kurs-/Einheitennavigation sowie Öffnen mehrerer Module; gesperrte Transferknoten sind deaktiviert. Die vorhandenen Fortschrittsanzeigen wurden nicht verändert.
- Graphaktionen „Gesamtansicht“, Vergrößern, Verkleinern und Fokussieren ließen sich bedienen. Knoten außerhalb des aktuellen Ausschnitts waren nach „Gesamtansicht“ erreichbar.
- Materialoffenlegungen, vorhandene eigene Abgaben und der Großlesemodus waren erreichbar. „Zurück zur Aufgabe“ stellte den Fokus wieder auf die auslösende Großlesen-Aktion.
- Text-/Dateiauswahl funktioniert über sichtbare Beschriftung beziehungsweise Tastatur. Es wurde keine Datei ausgewählt oder übertragen.
- Ein bestehender Text blieb bei Aufgabenwiederaufruf, Größen-/Themewechsel und Neuladen erhalten. Neue Texte oder ein vollständiger Entwurfs-/Abgabezyklus wurden nicht getestet.
- Layoutdialog: Schriftgrößen Klein/Groß und Rückkehr zu Standard sowie Schließen mit Escape geprüft. Zweispaltiger Aufgabenraum bei 1024 Pixeln, kompakter Umschalter bei 390 Pixeln. [Tablet, Dark](assets/2026-09-08-lernenden-ui/18-task-tablet-dark-stable.png).
- Light/Dark-Endzustände lesbar; Editorwerkzeuge brechen auf schmalen Flächen um. Kein horizontaler Dokumentüberlauf in den gemessenen Aufgaben-/Graphansichten. UI-03 zeigt, weshalb diese Messung allein nicht genügt.
- H5P-Minimalinhalt erreichte nach dem Ladezustand „Fixture OK: GUSTAV Minimal“. Keine unbehandelten Seiten-JavaScriptfehler im instrumentierten Browser. Das ist kein vollständiger Netzwerk-, Barrierefreiheits- oder Sicherheitsnachweis.

## Grenzen und nächste Verwendung

Nicht geprüft: neue Abgabe, Finalisierung, externe KI-Verarbeitung, vollständiger Dialogrundlauf, echte interaktive H5P-Aufgaben, Netzwerkausfall, Mitgliedschaftsentzug, lineare Einheit, Übungssitzung, Lehrkraftseiten und andere Browser. Die vorhandene Dialogkomponente startet beim Öffnen automatisch eine Sitzung; sie wurde daher nicht geöffnet. Die PDF-Einbettung und ihr benannter Rahmen wurden erreicht, der eigentliche PDF-Inhalt blieb im verwendeten Headless-Browser unbestätigt. Kein Schluss auf einen Produktfehler allein aus dieser leeren Vorschau.

Die acht Punkte können als Arbeitsliste für Paket 4 dienen. Zuerst die bestätigten Struktur-/Zugänglichkeitsabweichungen mit Charakterisierungs- und Regressionstests absichern; danach die gestalterische Verdichtung gemeinsam beurteilen. Das ist noch kein entscheidungsvollständiger Implementierungsplan. Weder Backend-Restpakete noch DSPy noch neue Rechteentscheidungen werden damit freigegeben.

Zehn unbearbeitete Viewport-Screenshots synthetischer Testinhalte sind beigefügt; keine Zugangsdaten, Profilseiten oder realen Lernerarbeiten. Produktcode, Datenbankschema und bestehender Lernstand wurden nicht bearbeitet. Änderungen an Auswahl, Offenlegungen und Darstellung blieben im separaten Browserkontext; beide für die Prüfung geöffneten Browserzugänge und der temporäre Controller wurden anschließend geschlossen. Kein Reset und kein Push.
