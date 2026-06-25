# Plan: Schülereditor für Tabellen und robuste Textabgaben härten

Status: umgesetzt
Stand: 2026-06-12

## Kontext

Schüler können Textlösungen aktuell in `MarkdownWysiwygEditor.svelte` erfassen. Der Editor nutzt bereits Toast UI, blendet aber die vorhandene Tabellenfunktion aus. Gerade Tabellen sind für strukturierte Lösungen wichtig und sollen ohne Markdown-Syntax bedienbar sein. Gleichzeitig werden bekannte Robustheitsprobleme behoben: fehlender Fallback, unklare Submit-Synchronisierung, inkonsistente Draft-Speicherung, dünne Tests und Renderer-Kompatibilität.

## User Story

Als Schüler möchte ich in meiner Lösung einfach eine Tabelle erstellen und bearbeiten können, ohne Markdown-Syntax kennen zu müssen, damit ich strukturierte Antworten zuverlässig abgeben kann.

## BDD-Szenarien

1. **Tabelle einfügen**
   - Given ich bearbeite eine Textlösung,
   - When ich den Tabellenbutton im Editor nutze,
   - Then kann ich eine Tabelle einfügen und Zellinhalte im WYSIWYG-Editor bearbeiten.

2. **Aktuelle Tabelle absenden**
   - Given ich habe eine Tabelle erstellt oder bearbeitet,
   - When ich Rückmeldung einhole oder endgültig abgebe,
   - Then enthält `text_body` den aktuellen Markdown-Stand inklusive Tabelle.

3. **Fallback bei Editor-Fehler**
   - Given Toast UI kann nicht geladen werden oder JavaScript fällt vor der Initialisierung aus,
   - When ich eine Lösung schreibe,
   - Then steht ein normales Textfeld mit `name="text_body"` zur Verfügung.

4. **Sitzungsbezogener Entwurf**
   - Given ich schreibe eine Lösung,
   - When ich die Seite innerhalb derselben Browsersitzung neu lade,
   - Then wird der Entwurf wiederhergestellt.

5. **Keine dauerhafte lokale Speicherung**
   - Given ich schließe die Browsersitzung,
   - When ich später neu starte,
   - Then bleiben keine alten Schülerantworten aus `localStorage` erhalten.

## Technische Entscheidung

Wir wechseln nicht sofort zu Milkdown. Toast UI enthält bereits Tabellenfunktionen inklusive deutscher Oberfläche, Kontextmenü und Markdown-Serialisierung. Ein Milkdown-Crepe-Wechsel würde viele zusätzliche Abhängigkeiten und unnötige Features einführen. Für das konkrete Ziel ist zuerst eine kleine, gut getestete Härtung des bestehenden Editors angemessen.

## Umsetzung

- Toolbar im Schülereditor um `table` erweitern, aber Bild-Upload, Codeblöcke, LaTeX und unnötige Funktionen deaktiviert lassen.
- Ein echtes `<textarea name="text_body">` als Fallback rendern. Nach erfolgreichem Toast-UI-Mount wird es als Fallback verborgen und ein Hidden-Input trägt den aktuellen Wert.
- Beim `submit`- und `formdata`-Event den aktuellen `editor.getMarkdown()`-Wert synchron in den Formularwert schreiben.
- Drafts in `LearningSubmissionWorkspace` und `LearningTaskCard` auf `sessionStorage` vereinheitlichen.
- Toast-UI-Typisierung verbessern, soweit ohne größere Umstrukturierung möglich.
- Renderer-Tests absichern, dass Tabellen-Markdown sicher und stabil über `renderMarkdown()` sichtbar wird.

## Review-Nachtrag

- Alte Drafts aus der früheren `localStorage`-Implementierung werden beim Lesen und Schreiben eines Textentwurfs gelöscht. Sie werden bewusst nicht migriert, weil Schülerantworten nicht dauerhaft auf dem Gerät verbleiben sollen.
- Das No-JS-Fallback-Textarea rendert vorbelegte Werte aus dem `value`-Prop bereits vor Client-Effects. Dadurch bleibt `text_body` auch bei serverseitig vorbelegten Antworten oder Validierungsfehlern ohne erfolgreichen Toast-UI-Mount erhalten.

## Review-Nachtrag 2

- Sitzungsbezogene Textentwürfe werden zusätzlich nach `SessionBootstrapUser.sub` getrennt. Dadurch kann ein Entwurf von Schüler A in derselben Browsersitzung nicht bei Schüler B im gleichen Kurs und in derselben Aufgabe auftauchen.
- Alte unscoped Draft-Keys werden aus `sessionStorage` und `localStorage` entfernt. Ohne bekannte Lernendenkennung bleibt der Editor nutzbar, persistiert aber keinen Entwurf.

## API, DB und Migration

Es gibt keine OpenAPI-Änderung, keine Supabase/PostgreSQL-Migration und keine geplante Backend-Änderung. Der bestehende Vertrag bleibt `text_body` als Markdown-Text.

## Testplan

- Red-Green-Refactor für `MarkdownWysiwygEditor.test.ts`: Tabellenbutton vorhanden, Bildbutton nicht vorhanden, Fallback-Textarea vorhanden, Submit-Sync schreibt den aktuellen Markdown.
- Renderer-Test für Tabellen-Markdown und Sanitizing-Grenzen.
- Komponententests für sitzungsbezogene Drafts in beiden Schüleransichten.
- Gezielte Frontend-Tests: `npm test -- MarkdownWysiwygEditor markdown LearningSubmissionWorkspace LearningTaskCard`.
- Nachgelagerte manuelle QA auf Touch/WebKit: Tabelle einfügen, Zellen editieren, Zeile/Spalte ergänzen, scrollen und absenden.

## Akzeptanzkriterien

- Schüler können Tabellen über die sichtbare Toolbar einfügen.
- Eine unmittelbar vor dem Klick geänderte Tabelle wird vollständig in `text_body` übertragen.
- Ohne erfolgreichen Editor-Mount bleibt eine nutzbare Texteingabe vorhanden.
- Entwürfe werden nur sitzungsbezogen gespeichert.
- Entwürfe werden innerhalb der Sitzung nach Lernendem getrennt.
- Alte dauerhaft gespeicherte `localStorage`-Entwürfe werden entfernt.
- Bestehende Markdown-Ausgabe bleibt sanitizt und rendert Tabellen als Tabelle.

## Umsetzungsergebnis

- Tabellen-Toolbar, No-JS-/Mount-Fallback, Submit-Synchronisierung, sitzungsbezogene Drafts, lernendenbezogene Draft-Trennung und Markdown-Tabellen-Rendering sind umgesetzt.
- Keine OpenAPI-, Backend- oder Datenbankänderung.
