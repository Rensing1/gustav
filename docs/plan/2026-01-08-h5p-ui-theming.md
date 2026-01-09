# Plan: H5P‑UI Theming (Native‑Look) – Dark/Light, GUSTAV‑Design‑Tokens

Related plan (Feature/Integration): `docs/plan/2025-12-15-h5p-integration.md`

## Goal
H5P‑Editor (Lehrer) und H5P‑Player (Schüler) sollen sich **optisch und ergonomisch** wie **native GUSTAV‑UI** anfühlen – inklusive **Dark/Light Theme**.

Das ist bewusst ambitionierter als das ursprüngliche „Option B minimal“: Wir akzeptieren, dass dafür **mehr CSS‑Overrides** notwendig sind. Trotzdem bleibt die Umsetzung KISS‑orientiert:
- **ein** Theme‑Stylesheet (token‑basiert) für Player + Editor
- **ein** JS‑Hook, der das Theme in den Editor‑iframe injiziert (weil H5P es sonst nicht zulässt)

## Ausgangslage (Ist)
- GUSTAV‑Theme‑Tokens liegen in `backend/web/static/css/gustav.css` (Rosé Pine Dawn / Everforest Dark Hard).
- H5P wird via Lumi Webcomponents eingebettet:
  - Teacher: `backend/web/static/js/h5p_task_editor.js` + `<h5p-editor>`
  - Student: `backend/web/static/js/h5p_task_player.js` + `<h5p-player>`
- Wichtig für Styling:
  - Lumi Webcomponents rendern **im Light‑DOM** (kein Shadow DOM).
  - H5P lädt **CSS/JS dynamisch in den `<head>`** (über `addStylesheets(...)` / `addScripts(...)`).
  - Deshalb gilt: **CSS‑Reihenfolge** ist entscheidend → das Theme muss *nach* H5P‑Core/Library‑CSS geladen werden, sonst „verliert“ es.
  - **Wichtig (Editor):** `<h5p-editor>` rendert die eigentliche Editor‑UI in einem **iframe** und lädt die Styles aus `editorModel.styles` bewusst **nicht** in den Parent‑DOM (upstream‑Kommentar: „styles don't really matter“). Ergebnis: GUSTAV‑CSS/Tokens im Parent wirken *nicht* in den Editor‑Controls – wir müssen das Theme **in den iframe injizieren**.

## Nicht‑Ziele (vorerst)
- Keine Neuentwicklung eines eigenen H5P‑Editors (wir bleiben beim H5P‑Editor selbst).
- Keine neuen Evaluation‑Modi: H5P bleibt auto‑scorable (siehe Integrationsplan).

## Design‑Prinzipien (aus `docs/UI-UX-Leitfaden.md`)
- Nur semantische Tokens verwenden (z. B. `--color-bg-surface`, `--color-primary`), keine Hard‑coded Farben.
- Fokus sichtbar lassen (`:focus-visible` → `--color-focus-ring`).
- 8‑px‑Raster: klare Abstände, keine „pixeligen“ Sonderfälle.
- Barrierefreiheit: Kontrast, Tastaturbedienung, keine Fokus‑Fallen.

## Entscheidungsstand
- **Dark/Light‑Adaptation ist Pflicht** (Theme folgt GUSTAV).
- Ziel ist **native wie GUSTAV** → wir nutzen:
  - ein token‑basiertes Theme‑CSS (Player + Editor),
  - plus einen Editor‑iframe Hook, damit das Theme im Editor zuverlässig greift.

## BDD‑Szenarien (Given–When–Then)
### Player (Schüler)
- Given ein Nutzer nutzt Light‑Theme, When er eine H5P‑Aufgabe öffnet, Then ist der Player visuell konsistent mit GUSTAV (Farben, Typografie, Buttons, Fokus).
- Given ein Nutzer nutzt Dark‑Theme, When er eine H5P‑Aufgabe öffnet, Then ist der Player dunkel (keine „weißen Blöcke“), Lesbarkeit/Kontrast bleibt erhalten.

### Editor (Lehrer)
- Given ein Lehrer nutzt Light‑Theme, When er eine H5P‑Aufgabe bearbeitet, Then sind die sichtbaren UI‑Rahmen/Controls konsistent mit GUSTAV (inkl. Fokus‑Stile).
- Given ein Lehrer nutzt Dark‑Theme, When er eine H5P‑Aufgabe bearbeitet, Then blendet die Editor‑Oberfläche nicht (Backgrounds/Buttons/Text passen).
- Given ein Lehrer toggelt Light↔Dark während der Editor offen ist, When das Theme in GUSTAV wechselt, Then wird das Theme im Editor‑iframe erneut angewandt (ohne Reload).

## Test‑Design (Red‑Green‑Refactor)
Da es sich primär um UI/CSS handelt, kombinieren wir:
1) **Deterministische API/Contract‑Tests** (pytest):
   - Player‑Model enthält die Theme‑CSS als *letzten* Eintrag in `styles`.
   - Theme‑CSS ist über `/h5p/...` erreichbar (HTTP 200, `text/css`).
   - Hinweis (TLS lokal): Requests muss dem Caddy‑Root‑CA vertrauen (siehe Appendix im Integrationsplan).
   - Editor‑Iframe Hook ist im Teacher‑JS vorhanden (Contract: Selector `.h5p-editor-iframe` + Theme‑Href).
2) **Manueller UI‑Check** (Akzeptanz):
   - Student‑Seite: eine H5P‑Aufgabe im Light/Dark Theme öffnen → Buttons, Hintergrund, Schrift, Fokus‑Ring prüfen.
   - Teacher‑Seite: H5P‑Editor öffnen → Controls + Fokus‑Ring prüfen.
   - Teacher‑Seite: Theme toggeln während der Editor offen ist → prüfen, dass der Editor nicht wieder „weiß“ wird.

## Implementierungsentwurf (Option B)
### 1) Ein Theme‑Stylesheet bereitstellen (Single Source of Truth)
- Neue Datei (Beispiel): `h5p-service/vendor/theme/h5p-gustav.css`
- Inhalt:
  - Base‑Overrides für `.h5p-content`, `.h5p-container`, `.h5p-iframe`, `.h5p-core-button`, typische H5P‑UI‑Buttons/Inputs.
  - Editor‑Fix für „weiße Inseln“: Upstream nutzt rekursiv verschachtelte `.content`‑Wrapper mit abwechselnd weißen/hellen Hintergründen → in Dark‑Mode extrem störend. Lösung: verschachtelte `.content`‑Wrapper transparent machen und nur die „eigentlichen“ Flächen (`.h5peditor-form`, `.group > .content`) token‑basiert einfärben.
  - Nur Tokens: `var(--color-bg-surface)`, `var(--color-text)`, `var(--color-border)`, `var(--color-primary)`, `var(--color-focus-ring)`, `var(--font-base)`.
  - Fokus: `:focus-visible { outline/box-shadow: ... }` (keine unsichtbaren Zustände).

### 2) Sicherstellen, dass das Theme‑CSS **nach** H5P‑CSS geladen wird
Entscheidung (Mechanismus A, robust):
- **Wir hängen die Theme‑CSS serverseitig im H5P‑Service an** (kein GUSTAV‑SSR‑`<link>`), weil H5P/Lumi CSS dynamisch in den `<head>` injiziert und SSR‑Links oft „zu früh“ kommen.
- Konkret:
  - `GET /player/model`: Theme‑CSS wird **als letzter `styles`‑Eintrag** angehängt.
  - `GET /editor/model`: Theme‑CSS wird **als letzter `styles`‑Eintrag** angehängt.
  - Das Theme‑Stylesheet wird als statische Datei unter `/h5p/theme/h5p-gustav.css` ausgeliefert.
    (Intern im Service: Route ohne Prefix `/theme/h5p-gustav.css`, da Caddy `/h5p` strippt.)
- Fallback (nur wenn A nicht reicht): Option C (library‑spezifische Overrides). Keine SSR‑Injection als „Workaround“.

### 2b) Editor‑Iframe Hook (KISS‑Erweiterung für Option B)
Problem: Der Editor rendert im iframe, daher wirkt Mechanismus A zwar für Player, aber im Editor nur sehr begrenzt.

Lösung (Option 1, GUSTAV‑seitig):
- In `backend/web/static/js/h5p_task_editor.js` nach dem `editorloaded`‑Event:
  - Theme‑CSS als `<link rel="stylesheet" href="/h5p/theme/h5p-gustav.css">` in den Editor‑iframe `<head>` einfügen (und als letztes Element halten).
  - **Alle** GUSTAV‑Design‑Tokens (CSS‑Variablen) aus `document.documentElement` auslesen und in `iframe.documentElement` setzen, damit `h5p-gustav.css` im iframe dieselben Werte bekommt wie die GUSTAV‑Seite (auch Spacing/Typografie).
  - Upstream‑Layout‑Constraints im iframe entfernen (z. B. `max-width: 960px`, harte Backgrounds), damit der Editor in der GUSTAV‑Karte „zu Hause“ ist.
  - Bei Theme‑Toggle (MutationObserver auf `document.documentElement[data-theme]`) erneut anwenden.
- Sicherheits-/Robustheitsprinzip: best‑effort – Fehler im Theming dürfen den Editor nicht brechen.

### 2c) CKEditor‑White‑On‑Focus (Rich‑Text‑Felder)
Beobachtung:
- Einige H5P‑Felder (z. B. „Question“) sind Rich‑Text und nutzen CKEditor.
- Beim Fokus wird das Feld „aktiv“ und wird upstream wieder sehr hell/weiß (unpassend im Dark‑Mode).
- Zusätzlich rendert CKEditor die eigentliche Text‑Fläche in einem **weiteren (nested) iframe** → normales CSS im Editor‑iframe reicht nicht.

Lösung:
- Theme‑CSS überschreibt die CKEditor‑„Chrome“‑Flächen (Toolbars/Rahmen) token‑basiert und verhindert den weißen Active‑State (`.h5peditor-widget-active`, `.cke_*`).
- Ein kleiner JS‑Hook themed das **nested CKEditor iframe** (Tokens kopieren + minimale Styles für `html/body`), und beobachtet DOM‑Änderungen, damit es auch beim späteren Initialisieren greift.

### 3) GUSTAV‑Wrapper‑Styles (klein, lokal)
- In `backend/web/static/css/gustav.css` nur die Container (`.h5p-task-player`, `.h5p-task-editor`) so stylen, dass sie wie Karten/Panels wirken (Spacing/Border/Radius), ohne H5P intern zu „zerlegen“.

## Risiken & Fallbacks
- Der H5P‑Editor ist ein Dritt‑UI (inkl. Hub + CKEditor) → ein „native“ Look braucht **viele** Overrides und ist bei Upstream‑Updates potentiell wartungsintensiv.
- Manche H5P‑Libraries bringen harte Farben/Inline‑Styles → es kann library‑spezifische Nacharbeit geben.

## Done‑Definition (für Option B)
- Player:
  - In Light/Dark ist die Fläche „GUSTAV‑surface“, Text/Buttons sind lesbar und konsistent.
  - Fokus‑Ring ist sichtbar und entspricht `--color-focus-ring`.
- Editor:
  - Sichtbare Controls wirken wie GUSTAV (Buttons/Input‑Ränder/Spacing/Fokus).
  - Dark‑Mode ist nutzbar (keine weißen Flächen, keine unlesbaren Texte).
