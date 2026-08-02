# Kontrastreiches Produktdesign dauerhaft wiederherstellen

## Ausgangslage

Beim Aufteilen des früheren Designsystem-Stylesheets wurden die neuen kontrastreichen Tokens vor `app.css` geladen. Die dort verbliebenen älteren globalen Variablen überschreiben deshalb Farben, Schriften, Radien und Schatten. Das Ergebnis ist eine unbeabsichtigte Mischung aus neuen Komponenten und dem weicheren Vorgängerdesign.

## User Story

Als Lehrkraft oder lernende Person möchte ich GUSTAV auf allen Seiten in einer einheitlichen, kontrastreichen Gestaltung verwenden, damit Bedienelemente klar erkennbar sind und sich die Oberfläche verlässlich anfühlt.

Als Entwickler möchte ich globale Designwerte genau an einer Stelle ändern und beabsichtigte sichtbare Änderungen anhand stabiler Referenzen prüfen können, damit spätere Designanpassungen keine unbemerkten Kaskadenfehler verursachen.

## BDD-Szenarien

### Einheitliche Designquelle

**Gegeben** sind mehrere fachlich getrennte Stylesheets, **wenn** das globale Layout geladen wird, **dann** importiert es genau einen Designsystem-Einstiegspunkt mit einer ausdrücklich benannten Layer-Reihenfolge.

**Gegeben** sind globale Farb-, Schrift-, Abstands-, Radius- und Schatten-Tokens, **wenn** die Stylesheets geprüft werden, **dann** werden diese Tokens ausschließlich in `theme-tokens.css` deklariert.

**Gegeben** sind komponentenspezifische Variablen wie Authentifizierungs- oder Lernraum-Tokens, **wenn** die Token-Eigentümerschaft geprüft wird, **dann** dürfen sie in ihrem fachlichen Stylesheet verbleiben, solange sie kein globales Design-Token überschreiben.

### Kontrastreiche Gestaltung

**Gegeben** ist das helle Theme, **wenn** die Oberfläche gerendert wird, **dann** verwendet sie Off-White und Weiß, dunkle Konturen, rote Akzente, eckige Bedienelemente sowie harte versetzte Schatten.

**Gegeben** ist das dunkle Theme, **wenn** die Oberfläche gerendert wird, **dann** bleiben Kontraste, rote Akzente, Konturen und harte Schatten erhalten.

**Gegeben** sind Überschriften und Fließtexte, **wenn** ihre berechneten Stile geprüft werden, **dann** verwenden Überschriften Space Grotesk und Fließtexte Inter.

**Gegeben** sind Navigation, Buttons, Formulare, Karten, Tabellen und Dialoge, **wenn** unterschiedliche Produktoberflächen geöffnet werden, **dann** folgen sie derselben kontrastreichen Formsprache und enthalten keine wieder eingeführten weichen globalen Tokens.

### Visuelle Regression

**Gegeben** ist das interne UI-Labor, **wenn** es in Light und Dark sowie in Desktop- und Mobilgröße gerendert wird, **dann** entspricht es den freigegebenen Screenshot-Baselines.

**Gegeben** sind geladene Webfonts und mögliche Animationen, **wenn** ein Referenzbild aufgenommen wird, **dann** wartet der Test auf die Schriften und deaktiviert Bewegungen für ein deterministisches Ergebnis.

**Gegeben** ist eine beabsichtigte Designänderung, **wenn** Referenzbilder aktualisiert werden, **dann** geschieht dies über einen ausdrücklichen Befehl und die Änderungen werden visuell geprüft.

## Technischer Vertrag

- `frontend/src/lib/styles/index.css` ist der einzige globale CSS-Einstiegspunkt.
- Die Kaskade lautet: `reset`, `tokens`, `base`, `typography`, `primitives`, `learning`, `teaching`, `auth`, `overrides`.
- `theme-tokens.css` besitzt alle globalen `--color-*`, `--font-*`, `--space-*`, `--radius-*` sowie `--color-shadow`-Definitionen für Light und Dark.
- Fachliche Stylesheets konsumieren diese Variablen und dürfen nur eindeutig fachlich benannte lokale Variablen ergänzen.
- `data-theme="light|dark"` bleibt unverändert.
- OpenAPI, Datenbank, fachliche DTOs, UI-Texte und Interaktionen ändern sich nicht.

## Test- und Abnahmestrategie

1. Statische Designvertragstests zunächst fehlschlagen lassen.
2. Zentralen Einstiegspunkt und Token-Eigentümerschaft minimal herstellen.
3. Berechnete Browserstile und UI-Labor-Snapshots ergänzen.
4. Startseite, Lerneinheiten, Aufgabeneditor, Lernraum, Diagnostik, Live und Authentifizierung stichprobenartig prüfen.
5. `make verify` sowie den visuellen Browser-Gate ausführen.
