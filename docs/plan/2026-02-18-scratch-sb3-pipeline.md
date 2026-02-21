# Plan: Scratch `.sb3` Upload + automatische Auswertung (Evidence → DSPy Feedback)

Datum: 2026-02-18  
Status: Implemented (SB3-only Pipeline + `scratch.evidence.v2`)

## Kontext / Problem
Scratch-Abgaben werden in GUSTAV aktuell als **Visual Tasks** behandelt (Upload-only), typischerweise als **Screenshots** der Scratch-Blöcke.
Das ist für eine kriterienorientierte, strukturierte Auswertung unzuverlässig (OCR/Visual Parsing, wenig deterministisch).

Ziel ist daher: **Scratch-Abgaben sollen als `.sb3` eingereicht werden**. `.sb3` ist ein ZIP-Archiv, dessen `project.json` den relevanten Programmzustand (Targets, Blocks, Variablen, Broadcasts, Kostüme, etc.) enthält.

## Zielbild (MVP)
- Lehrkraft erstellt `Task.kind=scratch`.
- Schüler können bei Scratch-Tasks **nur** `.sb3` hochladen (Upload-only; keine Screenshots/keine Textabgabe).
- API validiert `.sb3` bereits beim `POST .../submissions`:
  - kein ZIP → `400 invalid_sb3_archive`
  - ZIP ohne `project.json` → `400 missing_project_json`
- Worker-Pipeline bleibt bestehen:
  - **statt OCR** erzeugt ein deterministischer Extractor aus `project.json` einen **Markdown Evidence-Report** (`scratch.evidence.v2`)
  - DSPy Feedback bewertet Kriterien **ausschließlich** anhand dieses Evidence-Reports (`student_text_md`)

## User Story
Als Informatiklehrkraft möchte ich Scratch-Abgaben als `.sb3` auswerten lassen, damit ich kriterienorientiertes, nachvollziehbares Feedback in gleichbleibender Qualität erhalte und keine Screenshots mehr manuell prüfen muss.

## BDD-Szenarien (Given/When/Then)
1. Scratch-Upload-only UI  
   Given `Task.kind=scratch`  
   When ein Schüler die Task-Seite öffnet  
   Then sieht er nur ein Upload-Feld für `.sb3`.

2. Upload-Intent erlaubt SB3  
   Given `Task.kind=scratch`  
   When Upload-Intent mit `mime_type=application/x.scratch.sb3` angefragt wird  
   Then Response enthält `accepted_mime_types=["application/x.scratch.sb3"]`.

3. Submission akzeptiert SB3  
   Given `Task.kind=scratch`  
   When `POST .../submissions` mit `kind=file` + SB3-Metadata kommt  
   Then Response `202`, Submission `analysis_status=pending`.

4. Submission lehnt Screenshots ab  
   Given `Task.kind=scratch`  
   When `POST .../submissions` mit `kind=image` kommt  
   Then Response `400 invalid_input` (Upload-only: sb3).

5. Security: invalid archive  
   Given Datei mit `.sb3`-Endung ohne ZIP-Signatur  
   When `POST .../submissions`  
   Then `400 invalid_sb3_archive`.

6. Security: missing `project.json`  
   Given valides ZIP ohne `project.json`  
   When `POST .../submissions`  
   Then `400 missing_project_json`.

7. Worker: Evidence → Feedback  
   Given eine gültige Scratch-Submission  
   When der Worker den Job verarbeitet  
   Then `text_md` enthält `scratch.evidence.v2`, `analysis_json` ist `criteria.v2`, `feedback_md` folgt dem 2-Absatz-Contract.

## Contract-first: OpenAPI Änderungen (`api/openapi.yml`)
- `Task.kind` enum: `native|h5p|visual|scratch`
- Neues Schema `ScratchTaskConfig` (MVP: leeres Objekt)
- `Task`, `TaskCreate`, `TaskUpdate`: optionales Feld `scratch` (mutually exclusive zu `h5p`/`visual`)
- Learning Upload-Intents: SB3 MIME dokumentieren
- Learning Submissions (file): MIME enum erweitert (`application/pdf` + `application/x.scratch.sb3`)
- Neue 400 detail codes: `invalid_sb3_archive`, `missing_project_json`

## Datenbank / Migration (Supabase)
- Constraint `unit_tasks_kind_check` erweitert um `scratch`.
- Keine zusätzlichen Scratch-spezifischen Spalten im MVP.

## Evidence Format (Versioniert)
Format: Markdown, Schema-Tag in erster Zeile.

### `scratch.evidence.v1` (MVP)
Enthält (Legacy / nur zur Referenz):
- Projekt-Metadaten (Targets, Block-Counts)
- pro Target/Sprite: opcodes (Counts), Variablen/Listen/Broadcasts (stabil sortiert)

Limitation:
- Für viele kriterienorientierte Aufgaben ist v1 **nicht zuverlässig genug**, weil
  Abläufe/Sequenzen, Kontrollfluss und Parameterwerte (z.B. Richtung/Größe) nicht
  ausreichend sichtbar sind.

### `scratch.evidence.v2` („reliable evidence“ — erforderlich für zuverlässige Auswertung)
Ziel: Evidence muss die Programmlogik so darstellen, dass ein LLM Kriterien **evidenzbasiert**
und **reproduzierbar** prüfen kann (ohne Screenshot/OCR).

`scratch.evidence.v2` enthält:
- Projekt-Index: Targets, Variablen/Listen/Broadcasts, Kostüme/Sounds (pro Target)
- **Scripts als Outline** pro Target (Hat-Block → next-Kette; stabil sortiert; optional x/y)
- **Kontrollstrukturen** explizit (Loops/If/Else; SUBSTACKs eingerückt)
- **Parameterwerte** sichtbar (z.B. `SIZE`, `DIRECTION`, Kostüm-/Broadcast-Optionen, Variablen-Namen)
- **My Blocks / Procedures**: Definitionen (proccode), Calls, Argumente (soweit statisch darstellbar)
- **Clones**: create-clone / start-as-clone / delete-this-clone (falls genutzt)
- **Truncation-Hinweis** (falls Evidence wegen Größenlimits abgeschnitten werden muss), inkl. Gründen/Zählern

Wichtig:
- Evidence ist **deterministisch** (kein LLM) und **bounded** (Längenlimits).
- User-Strings (Sprite-Namen, Variablen-Namen, Broadcast-Namen) werden escaped und gekürzt (Prompt-Injection Hardening).

## Guidance: Kriterien + KI-Kontext (CustomGPT → „auswertbar“ formulieren)
Damit die automatische Auswertung zuverlässig klappt, müssen Kriterien und Kontext zur Evidence-Form passen:

Kriterien (Do):
- Kriterien als **prüfbare Programmstruktur** formulieren (Scripts/Sequenzen/Blocks), z.B.
  „Beim Start gibt es ein Script mit `event_whenflagclicked`, das …“
- Alternativen explizit erlauben (Rotation **oder** Kostümwechsel; Sequenz **oder** Schleife; etc.)
- Wenn etwas zwingend über Namen identifizierbar sein muss (Sprite/Kostüm/Broadcast), dann das
  als **Aufgaben-Nebenbedingung** festlegen („Sprite heißt …“) — sonst ist es heuristisch.

Kriterien (Don't):
- Keine rein visuellen/UX-Kriterien ohne statische Belege (z.B. „sieht schön aus“).
- Keine impliziten Laufzeitannahmen, die sich aus `project.json` nicht belegen lassen.

KI-Kontext (Pflicht-Hinweis):
- Das LLM darf ausschließlich Evidence als Beleg verwenden (student_text_md).
- Wenn Evidence als `truncated: true` markiert ist oder notwendige Infos fehlen: **nicht raten**,
  sondern als „nicht belegbar“ bewerten und erklären.

## Security / Hardening
- ZIP Bomb Schutz: max entries, max uncompressed bytes, max `project.json` bytes.
- Keine Extraktion auf Dateisystem (nur Lesen in-memory).
- Keine Logs mit Studentendaten oder kompletten Evidence-Reports.

## Update (2026-02-19): SB3-Validation Download (TLS / `app.localhost`)
In lokalen Setups ist `SUPABASE_PUBLIC_URL` oft `https://app.localhost` (Caddy Reverse Proxy mit lokaler CA).
Signed Download URLs werden im Storage-Adapter **auf diese Public-Base umgeschrieben** (für Browser korrekt).

Problem:
- Server-seitige Validierung (SB3 `project.json`) läuft **im Container** und lädt Bytes via `httpx`.
- `httpx` vertraut der lokalen Caddy-CA nicht → `CERTIFICATE_VERIFY_FAILED`.
- Ergebnis: `_load_storage_bytes_for_validation()` liefert `None` → `503 sb3_validation_unavailable` → UI-Submit endet in „Request failed“.

Fix (dev = prod, sicher):
- Beim server-seitigen Download (Validation) wird — falls die presigned URL auf den Public-Host zeigt —
  **scheme/host/port auf `SUPABASE_URL` umgeschrieben**, Pfad + Query bleiben unverändert.
- Dadurch wird der interne Supabase-Gateway (typisch `http://supabase_kong_…:8000`) genutzt, ohne TLS-CA-Probleme.

Nebenwirkung/UX:
- Die SSR-Submit-Route liefert bei erwartbaren Validierungsfehlern absichtlich non-2xx zurück, damit HTMX `detail.successful=false`
  bleibt (u.a. um Draft-Clearing zu vermeiden). Das UI zeigt dann sonst den generischen Toast „Request failed“.
- Client-seitig wird bei `htmx:responseError` jetzt ein vom Server geliefertes `HX-Trigger.showMessage` bevorzugt.

## Update (2026-02-20): Schüler-UI — Evidence lesbarer darstellen (Typografie/Outline)
Ziel: `scratch.evidence.v2` soll **für Schüler** weniger wie ein Logdump wirken, ohne das Evidence-Format zu verändern.

Umsetzung (minimal-invasiv):
- SSR: Evidence-Markdown wird beim Rendern als `<div class="scratch-evidence">…</div>` gekapselt, wenn der Text mit `# scratch.evidence.` beginnt.
- CSS: Styles sind dadurch scoped:
  - Schema-Zeile (`# scratch.evidence.v2`) wird visuell ausgeblendet (bleibt im Text für Pipeline/Debug).
  - Überschriften kompakter; Listen in Monospace; Script-Block-Listen (`h4 + ul`) als Panel mit klarer Einrückung für Substacks.

Test:
- `backend/tests/test_learning_ui_scratch_evidence_rendering.py` stellt sicher, dass nur Scratch-Evidence den Wrapper erhält.

Detail:
- Für verschachtelte Kontrollstrukturen (`control_forever` mit SUBSTACK) wird in Script-Zeilen bewusst **kein**
  `white-space: pre-wrap` verwendet, damit HTML-Whitespace/Newlines aus dem Markdown-Renderer nicht als „extra Zeile“
  sichtbar werden.

## Tests (pytest)
- OpenAPI Contract Tests: Scratch in enums + error codes vorhanden.
- Teaching API: Erstellen von Scratch-Tasks setzt `kind=scratch`.
- Learning API:
  - Upload-Intent für scratch → SB3 only
  - Create-Submission für scratch:
    - akzeptiert valid SB3
    - reject image/text
    - invalid zip/missing project.json
- Adapter/Worker: `local_vision` SB3 branch erzeugt Evidence-Markdown ohne DSPy/OCR.
