# DESIGN.md

## Status

Dieses Dokument ist der verbindliche Designvertrag für die Svelte-Oberfläche
von GUSTAV. Es ersetzt `docs/UI-UX-Leitfaden.md` fachlich vollständig. Die
Preview-Route unter `/ui-lab` dient als visuelle Referenzfläche; Stitch-Projekt
`7234666190356643774` ist die kanonische visuelle Quelle für diese Fassung.

Primäre Stitch-Referenzen:

- `GUSTAV Task Redesign - Mistral Style Base`
- `GUSTAV Graph-Übersicht - Mistral Style Base`
- Designsystem `Gustav Logic`

## 1. Produktbild

GUSTAV folgt jetzt einer `Mistral`-artigen Produktsprache. Das Produkt wirkt
präzise, kontrastreich, technisch-scharf und bewusst gestaltet. Es ist kein
freundlich-rundes EdTech-Produkt und keine warme Editorial-Oberfläche mehr.

Verbindliche Zielwahrnehmung:

- Präzision
- Klarheit
- Eigenständigkeit

Verbindliche Negativrichtung:

- nicht weichgespült
- nicht generisch-SaaS
- nicht verspielt

Der Primäranker ist die Aufgabenfläche. Der Graph übernimmt dieselbe Sprache,
ordnet sich aber der Task-Fläche gestalterisch unter.

## 2. Rollen und Grundhaltung

GUSTAV optimiert weiterhin im Zweifel zuerst für Lernende. Lehrkraftflächen
teilen jedoch dieselbe harte Formensprache und denselben Kontrast.

Verbindliche Regeln:

- Schüler- und Lehrkraftflächen wirken wie ein Produkt.
- Unterschiede entstehen über Dichte, Werkzeuge und Kontext, nicht über
  verschiedene Designwelten.
- `Diagnostik` und `Live` bleiben außerhalb der ersten visuellen Welle, müssen
  später aber dieselbe Sprache übernehmen.

## 3. Shell

### 3.1 Grundstruktur

Die Produktoberfläche folgt dieser Reihenfolge:

1. `TopBar`
2. `Workspace`
3. `Dialog`, `Popover` oder `InlineEdit`

Zusätzliche globale Navigationsleisten sind nicht erlaubt.

### 3.2 Top-Bar

Die Top-Bar ist technisch-präzise und kontrastreich.

Regeln:

- klare Objektkanten statt weicher Flächen
- aktiver Navigationszustand bleibt typografisch markiert
- Primärnavigation ist textbasiert
- Marke darf präsenter sein als zuvor
- Meta und Steuerung nutzen technische Kleinformate

### 3.3 Breadcrumbs

Für Lernende bleiben Breadcrumbs ein Primärelement.

Regeln:

- Schülerpfad bleibt `Lernraum -> Kurs -> Lerneinheit`
- Breadcrumbs sitzen im Lernfluss in der Top-Bar
- Breadcrumbs sind klein, technisch und klar lesbar
- Breadcrumbs enthalten keine Aktionen

### 3.4 Seitenkopf

Viele Seiten beginnen weiterhin direkt mit der Arbeit.

Regeln:

- kein Hero-Pattern
- Primäraktionen sitzen im Seitenkopf
- Sekundäraktionen bleiben sichtbar, aber schwächer
- Seitenkopf nutzt klare Kante und kompakte Meta-Zeile

## 4. Light und Dark

Light und Dark bleiben gleichrangig.

Regeln:

- beide Modi teilen exakt dieselbe Kompositionslogik
- Light ist off-white, dunkel konturiert und orange akzentuiert
- Dark ist tief, kontrastreich und technisch, nicht weich getönt
- neue Komponenten ohne definierte Dark-Regeln sind unvollständig

## 5. Farbe

Die Startpalette orientiert sich am Stitch-Designsystem `Gustav Logic`.

### 5.1 Light

- `--color-bg-base`: `#f9f9f9`
- `--color-bg-surface`: `#ffffff`
- `--color-bg-muted`: `#f3f3f4`
- `--color-bg-soft`: `rgba(255, 81, 47, 0.08)`
- `--color-text`: `#1a1c1c`
- `--color-text-muted`: `#5c5c5c`
- `--color-link`: `#b41f00`
- `--color-link-hover`: `#da3717`
- `--color-accent`: `#ff512f`
- `--color-accent-soft`: `rgba(255, 81, 47, 0.14)`
- `--color-border`: `#1b1b1b`
- `--color-line`: `rgba(27, 27, 27, 0.14)`
- `--color-success`: `#387f50`
- `--color-success-soft`: `rgba(56, 127, 80, 0.14)`
- `--color-warning`: `#8d5a00`
- `--color-warning-soft`: `rgba(141, 90, 0, 0.14)`
- `--color-danger`: `#ba1a1a`
- `--color-danger-soft`: `rgba(186, 26, 26, 0.14)`

### 5.2 Dark

- `--color-bg-base`: `#121212`
- `--color-bg-surface`: `#1a1a1a`
- `--color-bg-muted`: `#1d1d1d`
- `--color-bg-soft`: `rgba(255, 81, 47, 0.10)`
- `--color-text`: `#f0f1f1`
- `--color-text-muted`: `#c6c6c6`
- `--color-link`: `#ff866b`
- `--color-link-hover`: `#ffb4a4`
- `--color-accent`: `#ff512f`
- `--color-accent-soft`: `rgba(255, 81, 47, 0.20)`
- `--color-border`: `#f0f1f1`
- `--color-line`: `rgba(240, 241, 241, 0.18)`

### 5.3 Farbnutzung

- Orange markiert aktive Lernmomente und primäre Aktionen.
- Grün markiert Systemlogik, AI oder Erfolg.
- Linien und Rahmen bleiben monochrom, Akzente gezielt.
- Es gibt keine zonenspezifischen Farbwelten für Rollen.

## 6. Typografie

Konkrete Implementierungen dürfen leicht variieren, die Rollen sind
verbindlich.

Rollen:

- `Display Sans`
  - technisch, breit, präzise
  - für Titel, Phasenüberschriften und starke Einstiegsmomente
- `Reading Sans`
  - hoch lesbar und neutraler für längere Inhalte
- `Technical Mono`
  - für Kicker, Meta, Labels, Status, Breadcrumbs und Werkzeuge

Regeln:

- keine Serif als Leitmotiv
- Meta-Texte bevorzugt in Monospace/Technical-Sprache
- Headlines sind kompakt, kontrastreich und enger gesetzt
- UI-Labels dürfen häufiger uppercase erscheinen als bisher

## 7. Form, Raum und Bewegung

### 7.1 Spacing

Die bestehende Spacing-Skala bleibt erhalten:

- `--space-1`: `0.25rem`
- `--space-2`: `0.5rem`
- `--space-3`: `0.75rem`
- `--space-4`: `1rem`
- `--space-5`: `1.5rem`
- `--space-6`: `2rem`
- `--space-7`: `3rem`
- `--space-8`: `4rem`

### 7.2 Radius

Radien sind praktisch deaktiviert:

- `--radius-s`: `0`
- `--radius-m`: `0`
- `--radius-l`: `2px`
- `--radius-xl`: `4px`

Default-Regel:

- neue Komponenten starten mit `0px`
- Abweichungen brauchen Begründung

### 7.3 Flächen

- Interactive Objects erhalten klare Rahmen
- große Flächen bleiben ruhig und hell
- Tiefe entsteht primär über Kontrast und harte Schatten
- Standard-Schatten folgen dem Objektprinzip, nicht dem SaaS-Prinzip

### 7.4 Motion

- Motion bleibt subtil
- Hover und Fokus dürfen deutlicher und technischer reagieren
- kleine Translate-/Shadow-Verschiebungen sind erlaubt

## 8. UI-Sprache

Die UI-Sprache bleibt kurz, sachlich und direkt.

Zusätzliche Regeln:

- technisch-präzise statt pädagogisch-begleitend
- Actions eher knapp und objektartig
- Status- und Metatexte dürfen technischer klingen
- `accent` für Primäraktionen
- `quiet` für normale Sekundäraktionen
- `subtle` für kleine, nicht-dominante Nebenaktionen wie `Pausieren`,
  `Schließen` oder `Bearbeiten` in dichten UI-Kontexten

## 9. Accessibility

Accessibility ist Teil des Designvertrags.

Regeln:

- hohe Kontraste in Light und Dark
- klare Fokuszustände
- vollständige Tastaturbedienbarkeit
- semantische Struktur bleibt trotz technischer Stilrichtung erhalten

## 10. Komponentenfamilien der ersten Welle

Die bestehende Komponentenarchitektur bleibt erhalten.

Verbindliche Familien:

- `AppShell`
- `TopBar`
- `BreadcrumbBar`
- `PageActionHead`
- `ModeSwitch`
- `QuietList`
- `QuietListEntry`
- `AuthFrame`
- `TeacherGraphCommandBar`
- `GraphPhaseBand`
- `GraphModuleNode`
- `LearningResponseGroup`

## 11. Lernraum und Lerneinheit

### 11.1 Modi

- Die Modi heißen `Übersicht / Inhalte`
- Der Wechsel bleibt ein echter Moduswechsel
- Die Mistral-Task-Fläche ist der stilistische Primäranker

### 11.2 Übersicht

- Graph bleibt Phasen-zentriert
- Knoten sind harte, klar gerahmte Objekte
- aktiver Status ist orange
- gesperrte Zustände sind reduziert und monochrom

### 11.3 Inhalte

- Task-Fläche bleibt Fokusraum
- Bearbeitung bleibt inline
- Der Modultitel ist der klare Einstiegspunkt eines Moduls
- `MATERIALIEN` und `AUFGABEN` bleiben technische Marker, keine konkurrierenden
  Subheadlines
- Zwei Zeilen für lange Modultitel sind erlaubt; der Modulkopf wächst nicht
  beliebig
- Der Abstand vom Modulkopf zum ersten Abschnitt ist größer als der Abstand vom
  Abschnittslabel zu seinem Block
- Rückmeldung und Bewertung erscheinen als technische Disclosure-Familie
- kompakte Task-Zeilen im modularen Lernraum nutzen eine Vorschauzeile statt
  redundanter Status-/Titellabels
- Status wird primär über Balken und Tönung getragen
- Die vollständige Aufgabenstellung erscheint in der aktiven Detailansicht inline
- Pro Pane ist in der kompakten Task-Zeile genau eine Detailansicht aktiv
- `Meine Abgabe` und Bearbeitung sind pro Pane exklusiv und erneut klickbar
- Markdown im Schüler-Lernraum wird zentral über einen sanitizten GFM-Renderer
  ausgegeben
- Unterstützt werden mindestens: Überschriften, Fett, Kursiv, Listen,
  nummerierte Listen, Links, Tabellen, `<br>`
- Lernraum-spezifische Overrides unter `.learning-unit-content-shell` gehören in
  den finalen Designsystem-Layer in `frontend/src/lib/styles/design-system.css`,
  nicht nur in `app.css`, damit Surface-, Spacing- und Typografie-Regeln im
  Lernraum wirksam bleiben

## 12. Auth und Preview

- Auth gehört sichtbar in dieselbe Produktsprache
- `/ui-lab` ist die interne Referenzfläche
- `/ui-lab` muss Shell, Task-Sprache, Graph-Sprache, Auth und Theme-Wechsel
  gleichzeitig zeigen

## 13. Verbotene Alt-Muster

- weiche SaaS-Radien
- warm-editoriale Blau/Papier-Sprache
- diffuse Schatten
- pillige Modusumschalter als Default
- generische Card-Haufen ohne klare Objektlogik
