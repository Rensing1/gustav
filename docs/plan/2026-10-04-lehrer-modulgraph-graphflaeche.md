# Graph-first-Lehreransicht für den Modulgraphen

## Status

Am 2026-10-04 umgesetzt und durch das verpflichtende Feature-Gate bestätigt. Die Bestandsaufnahme zeigte, dass bei 1024 × 768 die eigentliche Graphfläche erst nach rund 42 Prozent der Bildschirmhöhe begann. Mit ausgewählter Phase war in der früheren visuellen Referenz nur die Phasenüberschrift sichtbar; die Modulkarten lagen unterhalb des Viewports.

## User Story

Als Lehrkraft möchte ich den Modulgraphen auf dem iPad unmittelbar mit Phase und Modulen sehen, damit ich den Lernweg ohne vorheriges Scrollen oder manuelles Nachjustieren überblicken und planen kann.

Die bestehende Seite wird standardmäßig graphzentriert. Ein zusätzlicher Vollbildmodus ist nicht Bestandteil dieser Änderung.

## BDD-Szenarien und Testzuordnung

**Gegeben** eine modulare Lerneinheit auf einem iPad im Querformat bei 1024 × 768, **wenn** die Lehrkraft die Seite öffnet, **dann** sind die erste Phase und ihre vorhandenen Module ohne Scrollen sichtbar und die Graphfläche belegt mindestens 60 Prozent der Viewporthöhe.

Automatisierter Nachweis: neuer authentifizierter `@feature-acceptance`-Test `frontend/e2e/teacher-graph-viewport.spec.ts` in Chromium und im Projekt `webkit-ipad`.

**Gegeben** eine ausgewählte Phase, **wenn** die Kontextleiste erscheint, **dann** bleibt die Graphfläche gleich groß und der fokussierte Graphinhalt sichtbar.

Automatisierter Nachweis: Komponentenvertrag für `TeacherGraphWorkspaceFrame` sowie derselbe Feature-Acceptance-Test mit gemessener Canvasgeometrie.

**Gegeben** eine geöffnete Eigenschaften-Seitenleiste, **wenn** sie geöffnet oder geschlossen wird, **dann** bleibt die Canvasbreite unverändert und die Kamera wird nicht unbeabsichtigt zurückgesetzt.

Automatisierter Nachweis: vorhandener Ablauf in `teacher-graph-module-actions.spec.ts` und ergänzende Prüfung im neuen Viewport-Test.

**Gegeben** der Wechsel zwischen 1024 × 768 und 768 × 1024, **wenn** sich die Orientierung ändert, **dann** bleiben Auswahl, Phase, Module und Graphsteuerung ohne horizontalen Seitenüberlauf erreichbar.

Automatisierter Nachweis: Orientierungswechsel im neuen Feature-Acceptance-Test.

**Gegeben** ein Desktop-Viewport und ein Smartphone unter 721 px, **wenn** dieselben Ansichten geöffnet werden, **dann** bleiben das großzügige Desktop- beziehungsweise bestehende mobile Bedienmodell ohne Regression erhalten.

Automatisierter Nachweis: vorhandene visuelle Smoke-Tests für Desktop, Tablet und Smartphone in Light und Dark sowie gezielte Komponentenverträge.

**Gegeben** eine manuell verschobene oder gespeicherte Kamera, **wenn** nur eine Kontextaktion ausgeführt wird, **dann** bleibt diese Kamera erhalten; nur Auswahlfokus, Gesamtansicht oder Orientierungswechsel richten sie neu aus.

Automatisierter Nachweis: vorhandener Feature-Acceptance-Test für Graphaktionen sowie gezielte Tests der Graphsteuerung.

## Umsetzung

- `TeacherGraphWorkspaceFrame` erhält eine zusammenhängende graphzentrierte Rahmenstruktur. Auf Tablets und niedrigen Desktop-Viewports werden Seitenkopf und Graphwerkzeuge kompakter dargestellt.
- Die sichtbare, redundante Beschriftung „Lernweg“ entfällt nur in dieser kompakten Darstellung. Die barrierefreie Toolbar-Bezeichnung `Graphwerkzeuge` bleibt erhalten.
- Die Auswahlleiste liegt ab 721 px Breite als Overlay im Graphen. Auf kleineren Viewports bleibt sie im Dokumentfluss, damit das vorhandene gestapelte Smartphone-Layout und der bildschirmfüllende Inspector unverändert funktionieren.
- Die Graphhöhe wird weiterhin aus der real verbleibenden Viewporthöhe berechnet. Ein `vh`-Fallback steht vor der modernen `dvh`-Regel für Safari 15.3.
- Die initiale Kamera wartet auf stabile Knoten- und Canvasmaße. Ohne Auswahl wird die erste Phase einschließlich ihrer Module fokussiert, mit Auswahl das gewählte Element. Ein Orientierungswechsel richtet nach dem Layoutwechsel neu aus; gewöhnliche Kontext- und Inspectoraktionen verändern die Kamera nicht.
- Inspector, Auswahlleiste und Graphsteuerung verändern weder Canvasbreite noch fachliche Graphkoordinaten.

## API, Datenhaltung und Sicherheit

Die Änderung betrifft ausschließlich Svelte-Komponenten, CSS und clientseitige Graphdarstellung. `api/openapi.yml`, Supabase/PostgreSQL, Migrationen und RLS-Policies bleiben unverändert. Es entstehen keine neuen Datenflüsse, Berechtigungen oder personenbezogenen Daten.

## Verifikation

1. Komponenten- und Kameratests zunächst fehlschlagen lassen.
2. Minimalen Layout- und Kameracode implementieren, bis die gezielten Tests grün sind.
3. Code auf verständliche Verantwortlichkeiten, Safari-15.3-Fallbacks, Fokusführung und unerwünschte Kamera-Resets prüfen und vereinfachen.
4. Visuelle Referenzen bei Desktop, Tablet und Smartphone in Light und Dark prüfen und bei beabsichtigten Änderungen aktualisieren.
5. `make test-visual-smoke` ausführen und vorhandene fachfremde Blocker dokumentieren; `make verify-feature FEATURE=teacher-graph-viewport` erfolgreich ausführen.

## Ergebnis

- `make verify-feature FEATURE=teacher-graph-viewport`: erfolgreich; darin 3.067 Backendtests, 830 Frontendtests, Produktionsbuild, Architektur- und Vertragsprüfungen sowie der neue Acceptance-Test in Chromium und WebKit.
- Der gezielte Lehrergraph-Visualtest für Desktop, Tablet und Smartphone in Light und Dark ist erfolgreich; zwölf beabsichtigt geänderte Referenzbilder wurden geprüft und aktualisiert.
- Der globale Aufruf `make test-visual-smoke` bleibt außerhalb dieses Features rot. Der bestehende Sammelbefehl setzt die inzwischen verpflichtende Testlauf-ID und lokale Node-CA nicht. Ein entsprechend isolierter Gesamtlauf zeigte zusätzlich bereits abweichende Nicht-Graph-Referenzen und eine veraltete Erwartung an die deaktivierte Registrierungsseite. Der Lehrergraph-Fall selbst war in diesem Lauf grün; fachfremde Referenzen wurden nicht verändert.
