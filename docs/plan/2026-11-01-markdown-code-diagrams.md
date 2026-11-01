# Markdown und Mermaid

Status: umgesetzt und geprüft. Stand: 2026-11-01.

## User Stories und Entscheidungen

Als Lehrkraft oder Schüler möchte ich Code mit unverändertem Inhalt, Einrückungen und Zeilenumbrüchen lesen und bearbeiten. Ausdrücklich mit `mermaid` markierte Blöcke möchte ich in vollständigen Markdown-Ansichten und der bestehenden PDF-Druckfassung grafisch sehen.

Rohes HTML wird als Text angezeigt; `<br>` bleibt außerhalb von Code ein Zeilenumbruch. Tiptap, Markdown-Speicherung und WeasyPrint bleiben bestehen. Keine Editorvorschau oder neuen Editorbedienelemente, keine Datenbankmigration. Die nachfolgende Vereinfachung ersetzt den ursprünglichen Verzicht auf einen neuen API-Endpunkt. Der vorhandene PDF-Vertrag wird zuerst dokumentiert.

## Umsetzung: Red–Green–Refactor

1. Renderer- und Editorregressionen zuerst schreiben und rot nachweisen. Globale HTML-Löschung und Platzhalter entfernen; parserbasierte Break-Regel, `<pre>` und gemeinsame Codegestaltung ergänzen.
2. Gemeinsame MarkdownContent-Komponente ergänzen und alle vollständigen Markdown-Ausgaben einschließlich Strukturansichten anbinden. Diagramme über den gemeinsamen Renderer als PNG laden; Quelltext und Fehlerfallback erhalten. Mermaid-Konfiguration aus Inhalten darf Sicherheits- und Themevorgaben nicht überschreiben.
3. Eng begrenzten internen Node-/Chromium-Dienst ergänzen. Nur autorisierte Diagrammtexte werden vor Start des isolierten WeasyPrint-Prozesses gesammelt gerendert. Geprüfte PNGs werden als In-Memory-Assets übergeben. Syntax-/Größenfehler ergeben Hinweis und Quelltext, technische Fehler bleiben PDF-Fehler. Gemeinsames Gesamtzeitbudget, begrenzte Parallelität, Abbruch räumt Chromium auf. Keine externen Ressourcen, Datenpersistenz oder Inhaltslogs.

## BDD und automatisierte Zuordnung

| Given – When – Then | Tests |
| --- | --- |
| Code enthält Leerraum und HTML – er wird angezeigt – Inhalt bleibt erhalten und inert. | markdown.test.ts, markdown-security.test.ts |
| Mermaid wird im Editor eingegeben, geändert und gespeichert – erneutes Öffnen erhält Inhalt und Sprachkennung. | tiptap-markdown-editor.test.ts, markdown-code-diagrams.spec.ts |
| Markierte und unmarkierte Blöcke werden angezeigt – ausschließlich Mermaid wird grafisch. | MarkdownContent.test.ts |
| Quelle/Theme ändern sich während des Renderns – nur aktuelle Ergebnisse erscheinen. | MarkdownContent.test.ts |
| Diagramme erscheinen auf Desktop/iPad – Hell/Dunkel bleiben lesbar ohne Seitenüberlauf. | markdown-code-diagrams.spec.ts, Chromium/WebKit |
| Eingabe ist ungültig/manipuliert – verständlicher Fallback und Sicherheitsgrenzen greifen. | Mermaid-Laufzeit-/Diensttests, PDF-Adaptertests |
| Lehrkraft lädt PDF – Diagramme und übrige Inhalte sind korrekt. | PDF-Adaptertests, markdown-code-diagrams.spec.ts und visuelle PDF-Prüfung |
| Zugriff ist unberechtigt – keine Inhalte gelangen zum Renderer. | bestehende Teaching-Print-API-/DB-Tests |

Repräsentative Renderfixtures prüfen alle eingebundenen Mermaid-Typen; ausführliche Browserinteraktion prüft Sequenz- und Flussdiagramme. Mindestens ein `@feature-acceptance`-Test prüft echte Editorinteraktion, Server, Datenhaltung, Lernendenansicht und PDF-Download.

## Abschluss

Vor Browserprüfungen `make local-ca-status`. Gates: `make verify-feature FEATURE=markdown-code-diagrams`, `make docker-validate`, gezielter Abhängigkeitsaudit. Vorhandene Buildgrößen- und Safari-15.3-Grenzen bleiben bestehen. Bestehende uncommittete Modulgrapharbeiten werden erhalten. Kein Push ohne ausdrücklichen Auftrag.

## Vereinfachung nach Review (2026-11-01)

Felix hat den gemeinsamen Renderer für Browser und PDF ausdrücklich beauftragt. Die Codeformatierung wird zuerst gezielt abgeschlossen. Die Browserbibliothek Mermaid, ihre ELK-Aliase, der Grammatikumbau und die manuelle Chunkaufteilung entfallen vollständig. Alle 37 nativen Diagrammtypen verbleiben im internen Dienst.

Eine gemeinsame Python-Anbindung prüft die vom Dienst erzeugten PNGs. Die vorhandene PDF-Anbindung verwendet diese Bilder weiter. Neu kommt ein authentifizierter, same-origin-geschützter Batch-Endpunkt `POST /api/markdown/diagrams` für Lehrkräfte und Schüler hinzu (Contract-first). Er nimmt Diagrammquelltexte und das Farbschema entgegen, liest keine Datenbankinhalte und persistiert nichts. Größen-, Ausgabe- und Parallelitätsgrenzen schützen den Renderer. Der Browser zeigt ausschließlich PNGs an; vollständige Markdown-Strukturen werden über Parser-Tokens mit deklarativen Svelte-Diagrammteilen dargestellt. Quelltext bleibt bei Fehlern und während des Ladens sichtbar. Veraltete HTTP-Ergebnisse werden verworfen.

Tests: bestehende Code-/Editorregressionen zuerst; anschließend API-Tests für Authentifizierung, Rollen, CSRF, Grenzen und korrekte Fehlerzuordnung, gemeinsame PNG-Adaptertests und Komponententests für Batch-Ausgabe, Quelltext, Fehler und Theme-/Quelltextwechsel. Alle Typen werden mit kleinen Renderfixtures geprüft. Der authentifizierte Rundlauf konzentriert sich auf tatsächliches Bearbeiten/Speichern, Codeformatierung, Sequenz-/Flussdiagramm, Fehlerfall und PDF-Download. Das bisherige Merkmal „genau ein SVG je Diagramm“ entfällt, weil verschachtelte SVGs zulässige Mermaid-Ausgabe sind und der Browser künftig Bilder erhält. Unverändert: gezieltes Feature-Gate, bestehende Buildgrenzen und Safari-Basis.

Die neuen API-Tests benötigen keine Datenbank, weil dieser Endpunkt weder gespeicherte Inhalte liest noch schreibt. Die echten Berechtigungen und das Speichern von Material werden im authentifizierten Browser-Rundlauf und den bestehenden Print-API-/DB-Tests geprüft.

## Nachweise des vereinfachten Endstands

- Codeformatierung zuerst: 21 gezielte Frontend- und sechs Python-Renderer-Tests bestanden. Tiptap behält seine bestehende Implementierung; Codeinhalt und Sprachmarkierung bleiben erhalten.
- `make verify-feature FEATURE=markdown-code-diagrams`: erfolgreich. 3.235 Backendtests bestanden, 48 übersprungen; 939 Frontendtests bestanden. Typprüfung, normaler Build, Import-/Architektur-/API-Verträge, Inventare und Runtime-Image-Prüfung bestanden.
- Authentifizierter Rundlauf: Chromium und WebKit mit vollständigem iPad-Profil bestanden. Tatsächliche Editor-Eingabe, Speichern, erneutes Öffnen, Lernendenansicht, Hell/Dunkel, Codeformatierung, Inhaltsfehler und PDF-Download geprüft. Alle 37 nativen Mermaid-Typen liefern im gemeinsamen Renderer PNGs.
- `make local-ca-status`: lokale CA vertraut. `make docker-validate`: erfolgreich.
- `npm audit --omit=dev --audit-level=low` jeweils in `frontend/` und `diagram-renderer/`: keine Befunde. Die vorhandenen sechs Low-Befunde in Frontend-Entwicklungsabhängigkeiten sind davon nicht umfasst. Die bestehende transitive Laufzeitabhängigkeit Undici wurde gezielt von 7.29.1 auf 7.30.1 korrigiert.
- Renderer-Richtlinie separat mit `node --test diagram-renderer/*.test.mjs` geprüft. PDF über Poppler gerendert und visuell geprüft: Diagramme, Fehlerhinweis und eingerücktes HTML-Beispiel vollständig und lesbar.

Mermaid und die 97 zwischenzeitlich hinzugefügten Browser-Abhängigkeiten wurden aus dem Frontend entfernt. `frontend/vite.config.ts` entspricht wieder dem bestehenden Repository-Stand; es gibt keine Grammatiktransformation, Mermaid-ELK-Aliase oder manuelle Mermaid-Chunkaufteilung. Mermaid bleibt vollständig im gemeinsamen internen Dienst. Keine Datenbankmigration und keine neuen Editorbedienelemente.
