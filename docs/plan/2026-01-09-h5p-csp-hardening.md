# Plan: CSP‑Hardening für `/h5p/*` (H5P‑Service) – minimal, robust, DSGVO‑freundlich

Related plans:
- Feature/Integration: `docs/plan/2025-12-15-h5p-integration.md`
- UI/Theming: `docs/plan/2026-01-08-h5p-ui-theming.md`

## Ziel (Warum)
Wir möchten die aktuell bewusst permissive Content‑Security‑Policy (CSP) des H5P‑Service **schrittweise** auf das **minimal notwendige** Maß reduzieren, ohne den H5P‑Editor/Player zu brechen.

Das ist wichtig, weil H5P (trotz „trusted content“ im MVP) im Browser **viel JavaScript** ausführt. Eine zu offene CSP vergrößert die Angriffsfläche für:
- XSS‑Ausnutzung über UI‑Randfälle
- Supply‑Chain‑Risiken (Libraries/Packages werden wie Code behandelt)
- unbeabsichtigte externe Requests (Datenschutz/DSGVO)

## Scope (Was genau wird gehärtet?)
**Nur** die CSP‑Header für den H5P‑Service (`/h5p/*` auf `app.localhost`), nicht die globale App‑CSP.

Aktueller Ist‑Zustand:
- `backend/web/main.py` setzt eine relativ strikte CSP für die GUSTAV‑Web‑App (dev: inline erlaubt, kein `unsafe-eval`).
- Der H5P‑Service setzt aktuell in `h5p-service/server.mjs` für **alle** Antworten eine sehr permissive CSP (`default-src * …`, `unsafe-inline`, `unsafe-eval`).

Wichtig für die Umsetzung:
- CSP wirkt **nur** auf Dokumente (HTML) – für JS/CSS‑Assets gilt die CSP der Seite, die sie lädt.
- Der H5P‑Editor läuft in einem **iframe** (Lumi `<h5p-editor>`). Deshalb müssen `frame-src`/`child-src`/`worker-src` realistisch gesetzt werden.

## Nicht‑Ziele (vorerst)
- Keine Library‑Whitelist/Governance auf CSP‑Ebene (das kommt später unter „Hardening“/Betrieb).
- Keine Feature‑Änderungen an H5P (nur Header/Policy, maximal kleinere Anpassungen an H5P‑Standalone‑Pages, falls nötig).
- Keine Lockerung der globalen App‑CSP.

## Sicherheitsmodell (MVP‑Kontext)
- **Trusted Content**: Alle Lehrkräfte (`teacher`, inkl. Admin) dürfen Libraries/Packages installieren.
- Schüler konsumieren nur kuratierten Content.
- Trotzdem: CSP soll verhindern, dass H5P (oder Libraries) „ungeplant“ externe Inhalte nachladen.

## Entscheidungen (bestätigt)
1) **Keine externen Ressourcen**: H5P‑Inhalte sollen grundsätzlich **keine** externen Ressourcen laden dürfen (keine externen Bilder/iframes, keine externen APIs). → CSP: Same‑Origin only.
2) `/h5p/editor` ist **Debug‑UI**: Lehrkräfte arbeiten im Alltag über den **eingebetteten Editor** auf der Aufgaben‑Seite. Die Standalone‑Seite `/h5p/editor` ist weiterhin nützlich für Debug/Smoke, aber nicht der primäre Workflow.

## BDD‑Szenarien (Given–When–Then)
### Baseline: Player & Editor bleiben nutzbar
- Given ich bin als Lehrkraft eingeloggt, When ich `https://app.localhost/h5p/editor` öffne, Then lädt der Editor ohne CSP‑Fehler (keine geblockten Kern‑Scripts).
- Given ich bin als Schüler eingeloggt, When ich eine H5P‑Aufgabe öffne, Then funktioniert der Player (Assets, Interaktion, Scoring/finished‑Report).

### Datenschutz/Hardening: Externe Requests werden geblockt
- Given eine H5P‑Library versucht `fetch("https://example.com/...")`, When der Player läuft, Then blockiert die CSP den Request (connect/img/media/frame).
- Given ein Paket enthält HTML mit `<script src="https://evil.example/...">`, When es gerendert würde, Then blockiert `script-src` das Laden.

### Keine unnötigen Freigaben
- Given wir benötigen keine Third‑Party Fonts/CDNs, Then sind `script-src/style-src/font-src/connect-src` auf `'self'` (plus `data:`/`blob:` wo nötig) begrenzt.

## Zielbild: CSP‑Policies (Entwurf)
Wir unterscheiden zwei Klassen von Responses:
1) **HTML‑Dokumente** (`/editor`, `/player`) → CSP ist relevant.
2) **JSON/Assets** (`/healthz`, `/auth/me`, `/player/model`, `/editor/model`, `/contents/*`, `/libraries/*`, `/core/*`, `/webcomponents/*`) → CSP ist unkritisch, aber wir können dieselbe Policy „mitliefern“ (schadet nicht).

### Vorschlag A (Startpunkt): striktes Same‑Origin, ohne `*`, ohne `unsafe-eval`
Diese Policy ist bewusst nah an der bestehenden App‑CSP, weil wir bereits wissen, dass Editor/Player im eingebetteten Modus damit funktionieren.

**Baseline‑Direktiven (für `/h5p/*`):**
- `default-src 'self'`
- `base-uri 'none'`
- `object-src 'none'`
- `form-action 'self'`
- `frame-ancestors 'self'`
- `script-src 'self'`
- `style-src 'self' 'unsafe-inline'`
  - Begründung: H5P und viele Libraries nutzen Inline‑Styles/Style‑Attribute.
- `img-src 'self' data: blob:`
- `font-src 'self' data:`
- `connect-src 'self'`
- `media-src 'self' data: blob:`
- `frame-src 'self' blob:`
- `worker-src 'self' blob:`
- Optional: `script-src-attr 'none'` (verhindert inline `onclick=`‑Handler)

### Vorschlag B (Fallback): `unsafe-eval` nur, wenn wir es wirklich brauchen
Falls der Standalone‑Editor (`/h5p/editor`) oder bestimmte Libraries tatsächlich `Function(...)`/eval‑Äquivalente benötigen:
- `script-src 'self' 'unsafe-eval'` **nur** für die Editor‑HTML‑Route (nicht global).

Ziel bleibt: `unsafe-eval` im Player vermeiden.

## Vorgehen (Schrittfolge, KISS)
### Schritt 1: „Minimaler Sprung“ (von `*` → `'self'`)
- CSP in `h5p-service/server.mjs` von Wildcards (`*`) auf `'self'` + `data:`/`blob:` umstellen.
- `unsafe-eval` entfernen (erstmal).
- `unsafe-inline` nur für `style-src` behalten (zunächst).

### Schritt 2: Manuelle Verifikation (Teacher + Student)
- Teacher: `https://app.localhost/h5p/editor` → Library installieren/Content laden/speichern.
- Student: eine H5P‑Aufgabe spielen (inkl. Reload/„Fortsetzen“).
- Browser Console: CSP‑Violations checken (insb. blocked scripts, blocked connect, blocked frame/worker).

### Schritt 3: Automatisierte Guards (TDD/Contract)
Neue Contract‑Tests (pytest, deterministisch, ohne Browser‑Automation):
- `backend/tests/test_h5p_csp_contract.py`
  - prüft, dass der CSP‑Header für `/h5p/editor` und `/h5p/player` **kein `*`** enthält
  - prüft, dass `default-src`/`script-src`/`connect-src` mindestens `'self'` enthalten
  - prüft, dass `unsafe-eval` **nicht** enthalten ist (oder nur für `/h5p/editor`, falls wir fallbacken)

### Schritt 4: Optionaler Feinschliff
Wenn wir `script-src 'self'` nicht halten können (z. B. wegen inline scripts auf `/h5p/editor`):
- Entweder: Inline‑Scripts in `/h5p/editor` in externe Dateien auslagern (damit `script-src` ohne `unsafe-inline` möglich wird)
- Oder (MVP‑pragmatisch): `script-src 'self' 'unsafe-inline'` **nur** auf `/h5p/editor`

## Done‑Definition
- CSP für `/h5p/*` enthält **kein** `default-src *` und kein `script-src *`.
- Der H5P‑Player funktioniert für die in GUSTAV genutzten auto‑scorbaren Typen (z. B. MultiChoice).
- Der H5P‑Editor funktioniert für Lehrkräfte (embedded). Die Debug‑Seite `/h5p/editor` bleibt nutzbar für Smoke/Debug.
- Externe Requests sind standardmäßig geblockt (`connect-src/img-src/frame-src` ohne `*`).

## Offene Fragen (später, falls nötig)
1) Müssen wir für `/h5p/editor` (Debug) temporär `script-src 'self' 'unsafe-inline'` zulassen, weil dort inline Module Scripts genutzt werden?
   - Ziel bleibt: Player ohne `unsafe-inline`/`unsafe-eval`. Wenn wir Inline brauchen, dann nur scoped auf Debug‑HTML.
