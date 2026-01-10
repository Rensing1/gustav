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
- **Klarstellung (embedded vs. standalone):**
  - Der *primäre* GUSTAV‑Flow nutzt den eingebetteten Player/Editor innerhalb normaler GUSTAV‑Seiten (SSR + externe JS‑Dateien, kein Inline‑JS).
  - In diesem eingebetteten Modus gilt für die Ausführung der H5P‑Skripte primär die **App‑CSP** der GUSTAV‑Seite. Die CSP des H5P‑Services ist hier **Defense‑in‑depth** (und wirkt v. a. auf Standalone‑HTML‑Seiten des H5P‑Services).
  - Das bedeutet: „Externe Requests blocken“ im eingebetteten Modus ist im Zweifel ein App‑CSP‑Thema; dieses Hardening‑Vorhaben härtet zusätzlich die H5P‑Service‑Antworten (insb. Debug‑HTML).

## Nicht‑Ziele (vorerst)
- Keine Library‑Whitelist/Governance auf CSP‑Ebene (das kommt später unter „Hardening“/Betrieb).
- Keine Feature‑Änderungen an H5P (nur Header/Policy, maximal kleinere Anpassungen an H5P‑Standalone‑Pages, falls nötig).
- Keine Lockerung der globalen App‑CSP.

## Sicherheitsmodell (MVP‑Kontext)
- **Trusted Content**: H5P Libraries/Packages werden als ausführbarer Code betrachtet. Import/Install bleibt im MVP teacher/admin‑only; die Standalone‑Debug‑UIs sind dennoch admin‑only.
- Schüler konsumieren nur kuratierten Content.
- Trotzdem: CSP soll verhindern, dass H5P (oder Libraries) „ungeplant“ externe Inhalte nachladen.
- **Betrieblich (Pilot)**: Standalone‑Debug‑Seiten (`/h5p/editor`, `/h5p/player`) sind **admin‑only**; Lehrkräfte arbeiten im Alltag über den eingebetteten Editor/Player in GUSTAV.

## Entscheidungen (bestätigt)
1) **Keine Third‑Party Ressourcen**: H5P‑Inhalte sollen grundsätzlich **keine** Third‑Party Ressourcen laden (keine externen Bilder/iframes, keine externen APIs).
   - „Extern“ meint: außerhalb der GUSTAV‑Deployment‑Origins. Im Embedded‑Modus ist das primär ein App‑CSP‑Thema (z. B. `connect-src` enthält ggf. `SUPABASE_PUBLIC_URL` als explizite Allowlist).
   - Für dieses Hardening‑Vorhaben gilt: H5P‑Service‑CSP ohne `*`, Default = `'self'` (+ `data:`/`blob:` wo nötig).
2) `/h5p/editor` ist **Debug‑UI** (admin‑only): Lehrkräfte arbeiten im Alltag über den **eingebetteten Editor** auf der Aufgaben‑Seite. Die Standalone‑Seite `/h5p/editor` bleibt nützlich für Admin‑Debug/Smoke, ist aber nicht der primäre Workflow.
3) `/h5p/player` ist ebenfalls **Debug‑UI** (admin‑only; Schüler nutzen den eingebetteten Player).
4) Debug‑UIs (`/h5p/editor`, `/h5p/player`) sind **nur für `admin`** erreichbar.

## BDD‑Szenarien (Given–When–Then)
### Baseline: Embedded Flow bleibt nutzbar (primär)
- Given ich bin als Lehrkraft eingeloggt, When ich eine H5P‑Aufgabe im GUSTAV‑UI bearbeite (eingebetteter Editor), Then funktioniert der Editor unter der bestehenden App‑CSP.
- Given ich bin als Schüler eingeloggt, When ich eine H5P‑Aufgabe im GUSTAV‑UI öffne (eingebetteter Player), Then funktioniert der Player (Assets, Interaktion, Scoring/finished‑Report) unter der bestehenden App‑CSP.

### Baseline: Debug‑Seiten bleiben nutzbar (sekundär)
- Given ich bin als Admin eingeloggt, When ich `https://app.localhost/h5p/editor` öffne, Then lädt die Debug‑Seite ohne CSP‑Fehler (keine geblockten Kern‑Scripts).
- Given ich bin als Admin eingeloggt, When ich `https://app.localhost/h5p/player` öffne, Then lädt die Debug‑Seite ohne CSP‑Fehler (keine geblockten Kern‑Scripts).
- Given ich bin als Lehrkraft oder Schüler eingeloggt, When ich eine der Debug‑Seiten öffne, Then erhalte ich `403`.
- Given ich bin nicht eingeloggt, When ich eine der Debug‑Seiten öffne, Then erhalte ich `401`.

### Datenschutz/Hardening: Externe Requests werden geblockt
- Given eine H5P‑Library versucht `fetch("https://example.com/...")`, When der Player/Editor läuft, Then blockiert die wirksame CSP den Request (connect/img/media/frame; embedded = App‑CSP, Debug‑Seite = H5P‑Service‑CSP).
- Given ein Paket enthält HTML mit `<script src="https://evil.example/...">`, When es gerendert würde, Then blockiert `script-src` das Laden.

### Keine unnötigen Freigaben
- Given wir benötigen keine Third‑Party Fonts/CDNs, Then sind `script-src/style-src/font-src/connect-src` auf `'self'` (plus `data:`/`blob:` wo nötig) begrenzt.

## Zielbild: CSP‑Policies (Entwurf)
Wir unterscheiden zwei Klassen von Responses:
1) **HTML‑Dokumente** (`/editor`, `/player`) → CSP ist relevant.
2) **JSON/Assets** (`/healthz`, `/auth/me`, `/player/model`, `/editor/model`, `/contents/*`, `/libraries/*`, `/core/*`, `/webcomponents/*`) → CSP ist unkritisch, aber wir können dieselbe Policy „mitliefern“ (schadet nicht).

### Policy‑Matrix (KISS): Default strikt + Debug‑HTML gezielt gelockert
Wichtig: Die Debug‑HTML‑Seiten (`/h5p/editor`, `/h5p/player`) enthalten aktuell Inline‑Skripte (und beim Editor zusätzlich ein Inline‑Importmap). Ein `script-src 'self'` ohne Ausnahme würde diese Debug‑Seiten sofort brechen.

Deshalb definieren wir zwei Policies:
1) **Default (strict)**: gilt für alle `/h5p/*` Antworten als Standard.
2) **Debug‑HTML (scoped exception)**: gilt **nur** für die Debug‑HTML‑Routes `/editor` und `/player`.

Ziel bleibt: **kein `*`**, **kein `unsafe-eval`**; `unsafe-inline` (für Skripte) – falls überhaupt – nur auf Debug‑HTML, nicht „global“.

#### 1) Default (strict) – Baseline‑Direktiven (für `/h5p/*`):
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

#### 2) Debug‑HTML (scoped exception) – nur für `/editor` und `/player`
Wie Default, aber:
- `script-src 'self' 'unsafe-inline'`
- weiterhin **kein** `unsafe-eval`
- Optional: `script-src-attr 'none'` (falls kompatibel; reduziert Event‑Handler‑XSS‑Oberfläche)

### Fallback (nur wenn wir es wirklich brauchen): `unsafe-eval` strikt scoped
Falls der Standalone‑Editor (`/h5p/editor`) oder bestimmte Libraries tatsächlich `Function(...)`/eval‑Äquivalente benötigen:
- `script-src 'self' 'unsafe-inline' 'unsafe-eval'` **nur** für die Editor‑Debug‑HTML‑Route (nicht global; nicht für `/player`).

Ziel bleibt: `unsafe-eval` im Player vermeiden.

## Vorgehen (Schrittfolge, KISS)
### Schritt 1: Policy‑Matrix implementieren (Default strikt, Debug‑HTML scoped)
- In `h5p-service/server.mjs` die CSP von Wildcards (`*`) auf Same‑Origin (`'self'`) + notwendige Schemes (`data:`/`blob:`) umstellen.
- Hinweis: Caddy strippt das Prefix `/h5p` → im H5P‑Service sind die relevanten Debug‑Routes `/editor` und `/player` (ohne Prefix).
- `unsafe-eval` entfernen (erstmal) und nur als strikt scoped Fallback vorsehen.
- `unsafe-inline` für Skripte **nur** auf den Debug‑HTML‑Routen (`/editor`, `/player`) erlauben (weil dort Inline‑Skripte/Importmap existieren), nicht global.
- Debug‑UIs `/h5p/editor` und `/h5p/player` auf **admin‑only** beschränken.

### Schritt 2: Manuelle Verifikation (embedded + Debug)
- Embedded (primär):
  - Teacher: H5P‑Aufgabe im GUSTAV‑UI bearbeiten (eingebetteter Editor).
  - Student: H5P‑Aufgabe im GUSTAV‑UI spielen (inkl. Reload/„Fortsetzen“).
- Debug (sekundär):
  - Admin: `https://app.localhost/h5p/editor` und `https://app.localhost/h5p/player` öffnen und Smoke prüfen.
- Browser Console: CSP‑Violations checken (insb. blocked scripts, blocked connect, blocked frame/worker).

### Schritt 3: Automatisierte Guards (TDD/Contract)
Neue Contract‑Tests (pytest, deterministisch, ohne Browser‑Automation):
- `backend/tests/test_h5p_csp_contract.py`
  - Source‑Guard (liest `h5p-service/server.mjs`): kein `*` in der Default‑CSP, kein `unsafe-eval` als Default.
  - Guard für die Policy‑Matrix: Debug‑HTML (`/editor`, `/player`) ist die **einzige** Stelle, an der `script-src` `unsafe-inline` enthält.
  - Guard für Access‑Control: Debug‑HTML (`/editor`, `/player`) ist **admin‑only** (nicht `teacher`‑only).
  - Optional: Fallback‑Guard erlaubt `unsafe-eval` nur strikt scoped (nur Editor‑Debug‑HTML).
- Optional (E2E, ohne Browser‑Automation): ein kleiner Test, der via HTTPS (`app.localhost`) die Header von `/h5p/editor` und `/h5p/player` abruft und die Policy‑Matrix im echten Response validiert.
- Optional (E2E): Guard für Debug‑Access‑Control: `admin` bekommt `200`, `teacher/student` bekommen `403`, unauthenticated bekommt `401`.

### Schritt 4: Optionaler Feinschliff
Wenn wir `unsafe-inline` auf Debug‑HTML perspektivisch loswerden wollen:
- **KISS‑Option**: CSP‑Nonce für Debug‑HTML einführen und die Inline‑Scripts/Importmap mit `nonce="..."` versehen → Debug‑HTML kann dann ohne `unsafe-inline` auskommen.
- Alternativ: Inline‑Scripts in `/h5p/editor` und `/h5p/player` in externe Dateien auslagern; Importmap bleibt eine offene Design‑Entscheidung (Inline‑Importmap vs. Hash‑Freigabe).
- Debug‑Seiten bleiben erhalten (admin‑only) und sind bewusst „Debug‑Only“ (kein Primary Workflow, keine Feature‑Versprechen).

## Done‑Definition
- CSP für `/h5p/*` enthält **kein** `default-src *` und kein `script-src *`.
- `unsafe-eval` ist **nicht** Teil der Default‑CSP (Fallback – falls nötig – nur strikt scoped auf Editor‑Debug‑HTML).
- `unsafe-inline` für Skripte ist – falls notwendig – **nur** auf Debug‑HTML (`/h5p/editor`, `/h5p/player`) erlaubt, nicht global.
- Der H5P‑Player funktioniert für die in GUSTAV genutzten auto‑scorbaren Typen (z. B. MultiChoice).
- Der H5P‑Editor funktioniert für Lehrkräfte (embedded). Die Debug‑Seite `/h5p/editor` bleibt nutzbar für Smoke/Debug.
- Debug‑Seiten `/h5p/editor` und `/h5p/player` sind **admin‑only**.
- Externe Requests sind standardmäßig geblockt (`connect-src/img-src/frame-src` ohne `*`).

## Offene Fragen (später, falls nötig)
1) Wollen wir Debug‑HTML langfristig ohne `unsafe-inline` betreiben? (erfordert Refactor der Inline‑Skripte und eine Entscheidung zur Importmap‑Strategie)
2) Brauchen wir irgendwo wirklich `unsafe-eval`? Ziel bleibt: niemals im Player; wenn zwingend, dann nur strikt scoped auf Editor‑Debug‑HTML.
