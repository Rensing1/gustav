# Moduleditor auf breiten Bildschirmen ausbalancieren

## User Story

Als Lehrkraft möchte ich den modularen Inhaltseditor auf einem breiten Monitor ohne große ungenutzte Fläche verwenden, damit Inhaltsübersicht und Bearbeitungsformular gleichzeitig gut lesbar bleiben.

## BDD-Szenarien und Testzuordnung

- **Gegeben** ein modularer Inhaltseditor bei 1920 × 1080 Pixeln, **wenn** die Seite geöffnet wird, **dann** nutzt die Zweiflächenansicht mindestens 90 Prozent der verfügbaren Arbeitsbreite.
  Automatisiert durch den Designvertrag und den authentifizierten Playwright-Rundlauf in `teacher-graph-module-actions.spec.ts`.
- **Gegeben** die breite Zweiflächenansicht, **wenn** Materialien oder Aufgaben ausgewählt werden, **dann** bleibt die Inhaltsübersicht zwischen 22 und 25 rem breit und der Bearbeitungsinhalt höchstens 72 rem breit.
  Automatisiert durch Designvertrag, berechnete Browsergeometrie und visuelle Referenzen.
- **Gegeben** ein ausgewähltes Material oder eine ausgewählte Aufgabe, **wenn** deren Editor erscheint, **dann** stehen Titel und Aktionsmenü in einem gemeinsamen Bereichskopf und es gibt keinen leeren Aktionsstreifen im Formular.
  Automatisiert durch Komponentenvertrag und authentifizierten Browser-Rundlauf.
- **Gegeben** ein Markdown-Editor auf Desktop oder Tablet, **wenn** genügend Komponentenbreite verfügbar ist, **dann** bleibt die Werkzeugleiste kompakt und die Formatauswahl belegt nicht die gesamte Zeile.
  Automatisiert durch berechnete Browserstyles und visuelle Referenzen.
- **Gegeben** eine Komponentenbreite unter 64 rem, **wenn** zwischen Inhaltsübersicht und Editor gewechselt wird, **dann** bleibt der bestehende Ablauf `Inhalte → Bearbeiten` unverändert und ohne horizontalen Überlauf.
  Automatisiert durch Komponenten- und visuelle Browsertests bei 1024 × 768 und 390 × 844 Pixeln.
- **Gegeben** bestehende Material- und Aufgabenentwürfe, **wenn** die Darstellung geändert wird, **dann** bleiben Auswahl, Speicherung, Verwerfen und Löschen fachlich unverändert.
  Automatisiert durch die vorhandenen Interaktions- und Feature-Acceptance-Tests.

## Technische Festlegungen

- Nur der modulare Workbench überschreibt die bestehende 64-rem-Begrenzung; lineare Editoren bleiben unverändert.
- Die breite Inhaltsübersicht verwendet `clamp(22rem, 23cqw, 25rem)`.
- Der rechte Bearbeitungsinhalt wird auf 72 rem begrenzt und innerhalb der verfügbaren Fläche zentriert.
- `TeacherNodeEditorSection` erhält einen optionalen Aktions-Snippet für den gemeinsamen Bereichskopf.
- Produktive Styles verbleiben in der Lehrkraft-CSS-Schicht; API, Datenbank und Backend ändern sich nicht.

## Nachprüfung des projektweiten visuellen Gates

Der vollständige visuelle Gate hat zusätzlich veraltete Verträge aus früheren, bereits freigegebenen Oberflächenänderungen sichtbar gemacht. Sie werden vor einem Commit konsistent bereinigt:

- Der Lehrkraft-Arbeitsstarter wird auf die gemeinsame 80-rem-Breite von Kurs- und Lerneinheitenkatalog begrenzt. Die 112-rem-Shell bleibt als äußerer Raum verfügbar, bestimmt aber nicht die Lesebreite der beiden Arbeitsbereiche.
- Der Dialogvertrag prüft die Sitzungsaktionen relativ zum tatsächlich berechneten Innenabstand der Seitenleiste statt gegen einen überholten festen 16-px-Wert.
- Referenzbilder für Arbeitsstarter, Kurskatalog und Dialogzustände werden nur nach visueller Prüfung auf den bereits beabsichtigten aktuellen Zustand aktualisiert.

**Gegeben** eine breite Lehrkraftansicht, **wenn** `/teaching`, `/teaching/courses` oder `/teaching/units` geöffnet wird, **dann** verwenden die primären Inhaltsflächen dieselbe maximale Arbeitsbreite von 80 rem.
Automatisiert durch den statischen Breitenvertrag und die integrierten visuellen Browsertests.

**Gegeben** die breite Dialogseitenleiste, **wenn** deren Sitzungsaktionen am unteren Rand angeordnet werden, **dann** entspricht ihr Abstand höchstens dem berechneten unteren Innenabstand der Seitenleiste.
Automatisiert durch die berechnete Browsergeometrie im Designsystemtest.
