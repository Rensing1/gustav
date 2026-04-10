# Plan: Mistral-Redesign auf bestehendem UI-System

## Ziel

GUSTAV behält die bereits eingeführte Komponentenarchitektur, stellt aber den
gesamten visuellen Vertrag auf die neue Mistral-Richtung aus Stitch um.
Kanonische Referenz ist Projekt `7234666190356643774`, primär der Screen
`GUSTAV Task Redesign - Mistral Style Base`, sekundär
`GUSTAV Graph-Übersicht - Mistral Style Base`.

## Leitentscheidungen

- Kein Architektur-Reset; vorhandene UI-Bausteine bleiben bestehen.
- `docs/DESIGN.md` wird stark überarbeitet, nicht nur punktuell geflickt.
- Die neue Richtung ist plattformweit:
  - off-white / schwarz / orange
  - harte Kanten
  - technische Meta-Sprache
  - Monospace-Akzente
- `/ui-lab` bleibt die interne Referenz- und Abnahmefläche.

## Umsetzung

1. Vertrag umstellen
   - `docs/DESIGN.md` auf Mistral-Sprache, Tokens, Typografie und Verbote
     umschreiben.
   - Warm-editoriale Blau/Papier-Regeln entfernen.

2. Globale Stilbasis umstellen
   - `design-system.css` auf Mistral-Tokens umstellen.
   - Fonts, Radius, Schatten, Buttons, Header, Listen und Auth-Hülle anpassen.

3. Systembausteine redesignen
   - `BreadcrumbBar`, `PageActionHead`, `ModeSwitch`, `QuietList`,
     `AuthFrame`, `LearningResponseGroup`, `TeacherGraphCommandBar`
     visuell an die neue Sprache angleichen.
   - Graph-Bausteine über zentrale Stilregeln mitziehen.

4. Preview-Route als Referenz vervollständigen
   - `/ui-lab` zeigt Shell, Task-Sprache, Graph-Sprache, Commandbar, Auth und
     Theme-Wechsel im neuen Stil.

5. Kernflächen nachziehen
   - zuerst Shell und gemeinsame Bausteine
   - danach Schülerpfad und Lehrkraft-Lerneinheit
   - `Diagnostik` und `Live` später

## Abnahme

- `docs/DESIGN.md` und `/ui-lab` widersprechen sich nicht.
- Light und Dark folgen derselben Mistral-Logik.
- Graph- und Task-Flächen wirken wie eine Familie.
- `npm test` und `npm run check` im `frontend` bleiben grün.
