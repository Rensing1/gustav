# Einheitliche Lehrkraftkataloge

## User Story

Als Lehrkraft möchte ich, dass Kurs- und Lerneinheitenkatalog dieselbe räumliche und visuelle Sprache verwenden, damit sich der Wechsel zwischen Verwaltung und Authoring wie ein zusammenhängender Arbeitsbereich anfühlt.

## Gestaltungsvertrag

- Beide Kataloge verwenden die zur globalen Kopfzeile passende Inhaltsbreite von 80 rem.
- `PageActionHead`, Werkzeugleiste, Spaltenkopf und Datenzeilen folgen demselben vertikalen Rhythmus.
- Fachlich unterschiedliche Spalten bleiben erhalten; ihre Raster werden über gemeinsame Katalogvariablen definiert.
- Kursauswahl, Archivgruppierung und Lerneinheitenaktionen behalten ihr Verhalten.
- Unter 64 rem werden Werkzeugleisten kompakter; unter 48 rem werden Zeilen ohne horizontales Scrollen gestapelt.
- Light und Dark verwenden dieselbe Struktur und ausschließlich zentrale Designvariablen.

## BDD-Szenarien und Testzuordnung

**Given** eine Lehrkraft wechselt bei gleicher Fensterbreite zwischen Kursen und Lerneinheiten, **when** beide Kataloge geladen sind, **then** beginnen und enden Kopf, Werkzeugleiste und Liste an denselben horizontalen Positionen.

Automatisierung: berechneter Playwright-Browsertest und visuelle Referenzbilder bei Desktop, Tablet und Smartphone.

**Given** der Kurskatalog enthält aktive oder archivierte Kurse, **when** die Lehrkraft die Liste betrachtet, **then** besitzt sie wie der Lerneinheitenkatalog einen ruhigen Spaltenkopf und denselben Zeilenrhythmus.

Automatisierung: Routentest und visueller Browsertest.

**Given** die verfügbare Breite fällt unter 48 rem, **when** einer der Kataloge angezeigt wird, **then** werden Metadaten und Aktionen innerhalb der Zeile gestapelt und es entsteht kein horizontaler Überlauf.

Automatisierung: Browserstiltest und Referenzbild bei 390 × 844 Pixeln.

**Given** die Gestaltung wird später angepasst, **when** nur einer der Kataloge eigene globale Breiten- oder Zeilenwerte erhält, **then** schlägt der statische Designvertrag fehl.

Automatisierung: Vitest-Vertrag über gemeinsame Klassen, CSS-Variablen und den breiten Workspace-Modus.

## Schnittstellen

OpenAPI, Datenbank und fachliche DTOs bleiben unverändert. Die Änderung betrifft ausschließlich Svelte-Struktur, zentrale Lehrkraft-Styles, Dokumentation und visuelle Referenzen.
