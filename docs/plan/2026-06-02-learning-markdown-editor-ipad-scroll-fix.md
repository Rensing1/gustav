# iPad-Scroll im Schüler-Markdown-Editor beheben

Status: umgesetzt; manuelle iPad-/WebKit-QA offen

## Umsetzungsergebnis

- Toast UI wird mit Pixelwerten initialisiert (`448px`/`352px`), damit die interne Höhenberechnung keine negativen Min-Höhen erzeugt.
- Der CSS-Override für `.toastui-editor-main` ist auf eine schrumpfbare Flex-Fläche ausgerichtet, und der editierbare Scrollcontainer hat Touch-Scroll-Regeln.
- Die Änderung betrifft nur den Svelte-Schülereditor und erfordert keine API-, OpenAPI-, Datenbank- oder Migrationsänderung.

## Zusammenfassung

Als Schüler möchte ich in der Markdown-Eingabe meiner Lösung auf dem iPad zuverlässig durch längere Texte scrollen können, damit ich längere Antworten bearbeiten und abgeben kann, ohne dass der Editor blockiert oder Text am unteren Rand unerreichbar wird.

Der Fix betrifft die aktuelle Svelte-Schüleransicht. Der Editor ist `MarkdownWysiwygEditor.svelte` mit Toast UI und wird sowohl im modularen als auch im linearen Lernraum über `LearningTaskCard.svelte` genutzt. Es gibt keine API-, OpenAPI-, Datenbank- oder Migrationsänderung.

## Kontext und wahrscheinliche Ursachen

- `MarkdownWysiwygEditor.svelte` initialisiert Toast UI mit `height: "28rem"` und `minHeight: "22rem"`.
- Toast UI dokumentiert `height` als z. B. `300px` oder `auto` und rechnet intern mit `parseInt(height) - 75`. Dadurch wird `28rem` als `28` interpretiert; die aktuelle Initialisierung erzeugt im echten Toast-UI-DOM `min-height: -47px` auf `.toastui-editor-ww-container > .toastui-editor`.
- Die `rem`-Werte sind deshalb der Hauptbefund: Toast UI bekommt gültige CSS-Strings, aber keine für seine interne Höhenrechnung geeigneten Pixelwerte.
- GUSTAV überschreibt zusätzlich in `frontend/src/lib/styles/app.css` `.learning-markdown-editor .toastui-editor-main` mit `min-height: 40rem`, obwohl Toast UI für `.toastui-editor-main` selbst `min-height: 0px` setzt. Dieser Override kann den ursprünglichen Initialisierungsfehler maskieren, aber auch verschärfen, weil die innere Flex-Fläche nicht mehr wie von Toast UI erwartet schrumpfen darf.
- Gleichzeitig setzt der äußere Host `.learning-markdown-editor__surface { overflow: hidden; }`. Wenn innere Editorhöhen und sichtbarer Rahmen auseinanderlaufen, kann Text am unteren Rand abgeschnitten wirken und Touch-Scroll auf iPad/Safari schwer greifen.
- In Split-View-Kontexten kommt zusätzlich eine verschachtelte Scrollstruktur hinzu: Pane-Stack scrollt außen, Toast UI/ProseMirror innen. Dafür fehlen aktuell explizite Touch-Scroll-Regeln wie `-webkit-overflow-scrolling: touch`.
- Falsifikationsnotiz: Die bestehenden Vitest-Komponententests für `LearningTaskCard` und `LearningSubmissionWorkspace` stubben `MarkdownWysiwygEditor.svelte` über `frontend/vitest.config.ts`; sie können die echte Toast-UI-Höhenlogik daher nicht abdecken.

## BDD-Szenarien

- Given ein Schüler öffnet eine native Textaufgabe auf einem iPad, When er mehr Text schreibt, als im Editor sichtbar ist, Then kann er im Editor vertikal scrollen und die letzten Zeilen erreichen.
- Given die Aufgabe ist im modularen Lernraum in einer kompakten Task-Zeile geöffnet, When der Schüler im Editor wischt, Then scrollt die Editor-Eingabe und nicht unkontrolliert der äußere Pane.
- Given dieselbe Aufgabe wird auf Desktop bearbeitet, When der Text länger als der Editor wird, Then bleibt die bisherige Desktop-Bedienung mit Maus, Trackpad und Tastatur erhalten.
- Given der Schüler nutzt Upload statt Text, When er den Upload-Modus öffnet, Then bleibt das Upload-Verhalten unverändert.

## Umsetzung

1. Red: Neuen fokussierten Contract-Test `frontend/src/lib/components/learning-unit/MarkdownWysiwygEditor.test.ts` anlegen.
   - Der Test liest `MarkdownWysiwygEditor.svelte` und schlägt fehl, solange Toast UI mit `height: "28rem"` oder `minHeight: "22rem"` initialisiert wird.
   - Der Test erwartet Toast-UI-kompatible Pixelwerte: `height: "448px"` und `minHeight: "352px"` als direkte Entsprechung zu 28rem und 22rem bei 16px Root-Font.
   - Zusätzlich kann ein kleiner jsdom-Test den echten `@toast-ui/editor` mit diesen Optionen initialisieren und absichern, dass `.toastui-editor-ww-container > .toastui-editor` nicht mehr `min-height: -47px`, sondern einen positiven Pixelwert erhält. Dieser Test muss die echte Editor-Komponente oder den echten Toast-UI-Konstruktor nutzen, nicht den bestehenden Vitest-Stub.
2. Red: CSS-Contract für `frontend/src/lib/styles/app.css` ergänzen.
   - Der Test schlägt fehl, solange `.learning-markdown-editor .toastui-editor-main` `min-height: 40rem` enthält.
   - Er erwartet `min-height: 0` für `.toastui-editor-main`, weil Toast UI diese Fläche als schrumpfbare Flex-Fläche verwendet.
   - Touch-Scroll-Regeln werden nur minimal geprüft: `overflow-y: auto` und `-webkit-overflow-scrolling: touch` auf dem tatsächlichen editierbaren Scrollcontainer reichen als erster Vertrag. `overscroll-behavior: contain` und `touch-action: pan-y` werden nur geplant, wenn die manuelle iPad-QA sie bestätigt.
3. Green: `frontend/src/lib/components/learning-unit/MarkdownWysiwygEditor.svelte` ändern.
   - `height: "28rem"` durch `height: "448px"` ersetzen.
   - `minHeight: "22rem"` durch `minHeight: "352px"` ersetzen.
   - Einen kurzen englischen Kommentar an der Option ergänzen: Toast UI parses these values as pixel numbers internally, so keep them in px.
4. Green: `frontend/src/lib/styles/app.css` ändern.
   - `min-height: 40rem` auf `.toastui-editor-main` entfernen und durch `min-height: 0` ersetzen.
   - Touch-Scroll-Regeln auf die tatsächlichen Toast-UI-/ProseMirror-Scrollcontainer setzen, aber knapp halten und nach manueller iPad-QA validieren.
5. Refactor: CSS-Selektoren knapp halten und nicht in Legacy-Textarea-Styles unter `backend/web/static/css/gustav.css` eingreifen.

## Testplan

- `cd frontend && npm test -- MarkdownWysiwygEditor.test.ts LearningTaskCard.test.ts LearningSubmissionWorkspace.test.ts LearningUnitContentWorkspace.test.ts 'routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts'`
- `cd frontend && npm run check`
- `make verify`
- Manuelle QA auf iPad/Safari oder iPad-WebKit: lange Lösung einfügen, im Editorkörper wischen, prüfen, dass letzte Zeilen erreichbar bleiben, Textauswahl und Cursorplatzierung weiterhin funktionieren und der Draft weiter in `text_body` abgegeben wird.

## Annahmen

- Der Bug betrifft die aktuelle Svelte-Schüleransicht, nicht die ältere serverseitige Textarea-UI.
- Ein reiner CSS-Fix reicht wahrscheinlich nicht; die Toast-UI-Initialisierung muss ebenfalls korrigiert werden.
- Der gemeinsame Editor wird in beiden relevanten Schüler-Kontexten verwendet, daher reicht ein Fix in `MarkdownWysiwygEditor.svelte` plus der zugehörige CSS-Override.
- Keine Dependency-Aktualisierung von `@toast-ui/editor`.
