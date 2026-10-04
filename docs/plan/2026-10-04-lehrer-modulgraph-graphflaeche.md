# Graph-first-Lehreransicht für den Modulgraphen

## Status

Die erste Graph-first-Fassung und die zweite Nachbesserung zur echten Graph-first-Arbeitsfläche wurden am 2026-10-04 umgesetzt. Die zweite Nachbesserung wurde im lokalen Browser visuell freigegeben und anschließend durch die gezielten Visualtests sowie das verpflichtende Feature-Gate bestätigt.

Die ursprüngliche Bestandsaufnahme zeigte, dass bei 1024 × 768 die eigentliche Graphfläche erst nach rund 42 Prozent der Bildschirmhöhe begann. Mit ausgewählter Phase war in der früheren visuellen Referenz nur die Phasenüberschrift sichtbar; die Modulkarten lagen unterhalb des Viewports.

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

## Nachbesserung: skalierte iPad-Darstellung

Die visuelle Prüfung mit der iPad-Air-Emulation bei angezeigten 1180 × 820 zeigte weiterhin einen zu hohen Seitenkopf. Die laufende Browseroberfläche meldet in dieser skalierten Darstellung intern 1311 × 911 CSS-Pixel. Damit verfehlt sie die ursprüngliche Kompaktregel `max-height: 900px` knapp: Der Seitenkopf belegt 214 Pixel, der Graph beginnt erst nach rund 41 Prozent der Viewporthöhe und erhält nur rund 57 Prozent.

**Gegeben** die skalierte iPad-Air-Darstellung mit einem effektiven CSS-Viewport von 1311 × 911 beziehungsweise 911 × 1311, **wenn** die Lehrkraft den Modulgraphen öffnet oder die Orientierung wechselt, **dann** wird derselbe kompakte Graphkopf wie auf dem unskalierten iPad verwendet, die redundante sichtbare „Lernweg“-Zeile entfällt und die Canvasfläche belegt im Querformat mindestens 65 Prozent der Viewporthöhe.

Automatisierter Nachweis: Der authentifizierte `@feature-acceptance`-Test `frontend/e2e/teacher-graph-viewport.spec.ts` bildet zusätzlich beide effektiven Orientierungen nach und misst Kopf- und Canvasgeometrie, horizontalen Überlauf sowie die visuelle Ausblendung der redundanten Überschrift. Die nachfolgenden Prüfungen bei 1024 × 768 und 768 × 1024 bleiben bestehen.

Die Nachbesserung erweitert ausschließlich die responsive Kompaktzone des vorhandenen Seitenkopfs. API-Vertrag, Datenhaltung, Berechtigungen, Graphkoordinaten und Kamerapersistenz bleiben unverändert.

### Ergebnis der Nachbesserung

- In der realen skalierten iPad-Air-Ansicht bei effektiv 1311 × 911 beginnt der Graph nun nach rund 33 statt 41 Prozent der Viewporthöhe. Die Canvasfläche wächst von rund 57 auf 65,7 Prozent; die redundante Überschrift ist visuell ausgeblendet und bleibt für Hilfstechnologien erhalten.
- Der Acceptance-Test ist mit Querformat, Hochformat, Auswahl, Inspector und Kamerapersistenz in Chromium und WebKit erfolgreich.
- Die vollständige Frontend-Suite ist mit 842 Tests sowie den Richtlinienprüfungen für Buildausgabe und CSS-Kompatibilität erfolgreich; der Produktionsbuild ist ebenfalls erfolgreich.
- Das verpflichtende Gesamt-Gate wurde im gemeinsamen Arbeitsbaum erneut gestartet, dort aber vor den Tests von einem gleichzeitig entstehenden, fachfremden Datenbank-Testinventar gestoppt. Der isolierte Wiederholungsversuch bestätigte die Architektur-, Vertrags-, Inventar-, Lieferketten- und Containerprüfungen; die vollständige Backend-Suite ist wegen pfadgebundener Bestandsprüfungen nicht aus einer temporären Kopie ausführbar. Der gezielte Feature-Nachweis bleibt davon unberührt und ist grün.

## Zweite Nachbesserung: echte Graph-first-Arbeitsfläche

Die erneute visuelle Prüfung auf einem iPad Mini zeigt, dass die bisherige Verdichtung nicht weit genug geht: Bei effektiv 1137 × 853 CSS-Pixeln beginnt der Graph erst nach rund 34 Prozent der Viewporthöhe und erhält nur rund 64 Prozent. Ursache sind drei übereinanderliegende Höhenanteile: die globale Navigation, der äußere Breadcrumb-Kopf und der innere Kopf mit einer eigenen Werkzeugzeile.

### User Story

Als Lehrkraft möchte ich auf dem iPad mindestens vier Fünftel des Viewports für den Modulgraphen nutzen, damit die erste Phase mit ihren Modulen und der Beginn der zweiten Phase unmittelbar als zusammenhängender Lernweg erkennbar sind.

### BDD-Szenarien und Testzuordnung

**Gegeben** eine modulare Lerneinheit bei 1024 × 768 oder effektiv 1137 × 853, **wenn** die Lehrkraft den Modulgraphen öffnet, **dann** beginnt die Canvasfläche spätestens nach 20 Prozent der Viewporthöhe, belegt mindestens 80 Prozent der Höhe und zeigt die erste Phase samt Modulen sowie den Beginn der zweiten Phase ohne Scrollen.

Automatisierter Nachweis: `frontend/e2e/teacher-graph-viewport.spec.ts` misst Canvasanteil, Canvasoberkante und sichtbare Graphknoten im vollständigen authentifizierten Browserablauf. Der Komponentenvertrag für `TeacherGraphWorkspaceFrame` sichert die getrennten Grid-Bereiche für Kopf, Werkzeuge und Workspace.

**Gegeben** eine ausgewählte Phase oder ein ausgewähltes Modul, **wenn** die Kontextleiste erscheint, **dann** ersetzt sie die allgemeinen Graphwerkzeuge, ohne Canvasgröße oder Kameraposition zu verändern.

Automatisierter Nachweis: Komponentenvertrag für den Auswahlzustand sowie Geometrie- und Kameravergleich im Acceptance-Test.

**Gegeben** die immersive Lehrergraph-Route, **wenn** sie in einem kompakten Tablet- oder niedrigen Desktop-Viewport angezeigt wird, **dann** bleibt die vollständige globale Navigation in einer etwa 54 Pixel hohen Leiste erreichbar, der redundante äußere Breadcrumb entfällt und Titel, Statistik sowie Einheitenaktionen bilden eine kompakte Arbeitsleiste. Der vollständige Titel bleibt semantisch erhalten und wird nur visuell auf höchstens zwei Zeilen begrenzt.

Automatisierter Nachweis: Route- und Layoutverträge für `immersiveWorkspace` sowie der bestehende visuelle Lehrergraph-Test in Light und Dark.

**Gegeben** eine schwebende Werkzeug- oder Kontextleiste und einen geöffneten Inspector, **wenn** die Lehrkraft diese Bedienelemente nutzt, **dann** liegen sie vollständig innerhalb der Grapharbeitsfläche, verursachen keinen horizontalen Seitenüberlauf und verändern weder Canvasbreite noch Graphkoordinaten.

Automatisierter Nachweis: Bounds-, Überlauf-, Canvasbreiten- und Kameraprüfungen im Acceptance-Test.

**Gegeben** Hochformat, ein großzügiger Desktop oder ein Smartphone unter 721 Pixeln Breite, **wenn** die Lehrergraph-Ansicht geöffnet wird, **dann** bleiben das großzügige Desktopmodell beziehungsweise das gestapelte Smartphone-Modell samt bildschirmfüllendem Inspector erhalten.

Automatisierter Nachweis: bestehende Hochformatprüfungen im Acceptance-Test und die Lehrergraph-Visualtests für Desktop, Tablet und Smartphone.

### Umsetzung und Freigabereihenfolge

- Die Route setzt das interne Page-Data-Flag `immersiveWorkspace: true`. Nur im kompakten Tablet-/Low-Desktop-Bereich verdichtet dieses Flag die globale Navigation und blendet den redundanten äußeren Breadcrumb-Kopf aus.
- `TeacherGraphWorkspaceFrame` trennt Seitenkopf, Werkzeugleiste und Workspace in verständliche Grid-Bereiche. Im kompakten Bereich überlagert die Werkzeugleiste oben rechts den Canvas; bei einer Auswahl wird sie durch die bereits überlagernde Kontextleiste ersetzt.
- Kamera-, Persistenz-, Inspector- und Graphkoordinatenlogik bleiben unverändert. Der bestehende `vh`-Fallback vor `dvh` bleibt erhalten; CSS-Anchor-Positionierung und `:has()` werden nicht verwendet.
- API-Vertrag, Datenbank, Migrationen und RLS bleiben unverändert, weil ausschließlich die Darstellung einer bestehenden autorisierten Ansicht betroffen ist.
- Nach den gezielten Red-Green-Tests wird ausschließlich der lokale Frontend-Dienst neu gebaut und die reale Lerneinheit im geöffneten Browser gezeigt. Chromium/WebKit-Acceptance, vollständige Frontendtests, Visualtests und `make verify-feature FEATURE=teacher-graph-viewport` folgen erst nach der visuellen Freigabe.

### Abschlussnachweis der zweiten Nachbesserung

- Die neuen Komponenten- und Layoutverträge wurden zunächst rot ausgeführt und sind nach der minimalen Implementierung mit zehn gezielten Tests grün.
- Der lokale Frontend-Produktionsbuild war erfolgreich und der Frontend-Dienst wurde ohne Neuaufbau der übrigen Dienste aktualisiert. Die geöffnete reale Lerneinheit wurde anschließend visuell freigegeben.
- In der geöffneten iPad-Mini-Darstellung mit effektiv 1137 × 853 CSS-Pixeln ist die globale Navigation rund 55 Pixel hoch. Die Canvasfläche beginnt nach rund 15,1 Prozent des Viewports und belegt rund 83,0 Prozent seiner Höhe. Die allgemeinen Graphwerkzeuge liegen vollständig innerhalb des Canvas; ein horizontaler Seitenüberlauf tritt nicht auf.
- Die erste Phase mit ihren Modulen sowie der Beginn der zweiten Phase sind ohne vorheriges Scrollen sichtbar.
- Der gezielte Lehrergraph-Visualtest ist mit zwölf Referenzen für Desktop, Tablet und Smartphone in Light und Dark grün. Acht beabsichtigt geänderte Desktop-/Tablet-Referenzen wurden aktualisiert; die vier Smartphone-Referenzen blieben unverändert.
- `make verify-feature FEATURE=teacher-graph-viewport` ist erfolgreich: 3.114 Backendtests, 844 Frontendtests, 66 H5P-Tests, Produktionsbuild und der authentifizierte Lehrergraph-Acceptance-Test in Chromium und WebKit-iPad sind grün. Die Testdatenbereinigung meldet keine verbliebenen laufbezogenen Benutzer, Kurse, Einheiten, Sitzungen, Token oder H5P-Inhalte.
- Der globale Sammellauf `make test-visual-smoke` bestätigt den Lehrergraph-Fall, bleibt jedoch an elf fachfremden Bestandsfällen rot: drei Design-System-Fälle erhalten vom historischen Sammelziel keine verpflichtende Lauf-ID, zwei Auth-Fälle erwarten die deaktivierte Registrierungsseite und sechs weitere Fälle besitzen bereits abweichende Nicht-Graph-Referenzen. Diese fachfremden Referenzen und Tests wurden nicht verändert.
