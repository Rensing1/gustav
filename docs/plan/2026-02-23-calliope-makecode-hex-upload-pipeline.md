# Plan: Calliope MakeCode `.hex` Upload + deterministische Evidence-Extraktion

Datum: 2026-02-23  
Status: Implemented (HEX-only Pipeline + `makecode.evidence.v1`)

Maintenance Update (2026-05-10): Prod-Hotfix gegen zu strikte HEX-Extraktion
- Kontext geprueft:
  - Submit-Validierung: `backend/web/routes/learning.py`
  - HEX-Parser: `backend/storage/makecode_hex_validation.py`
  - Evidence: `backend/makecode/hex_evidence_v1.py`
  - Worker-Adapter: `backend/learning/adapters/local_vision.py`
  - Worker-Erfolgspfad: `backend/learning/workers/process_learning_submission_jobs.py`
  - API-Vertrag: `api/openapi.yml`
- Abweichung vom urspruenglichen MVP:
  - `invalid_hex_file` und `missing_makecode_source` sind fuer Calliope-HEX keine harten Submit-Abbrueche mehr.
  - Die Lockerung ist strikt begrenzt auf `Task.kind=calliope`, `mime_type=application/x.makecode.hex`
    und genau diese zwei Extraktionsfehler.
  - Auth-, Storage-, Hash-, Groessen- und MIME-Pruefungen bleiben hart.
  - `makecode_source_too_large` bleibt ein harter Fehler.
- Begruendung:
  - Reale MakeCode-Exports koennen erfolgreich als Unterrichtsabgabe gespeichert werden, obwohl Source-Embedding
    nicht oder nicht vollstaendig extrahierbar ist. Die Plattform darf diese Abgaben nicht als Upload- oder
    Worker-Fehler behandeln.
- Umsetzung:
  - Submit loggt die zwei bekannten Extraktionsfehler nur noch als Soft-Fail.
  - Der Parser toleriert malformed UTF-8 in eingebetteten MakeCode-Daten per `errors="replace"` und haelt
    `decode_mode`/`decode_replacements` intern in `MakeCodeProject.meta` fest.
  - `local_vision` erzeugt fuer die zwei Soft-Faelle eine minimale `makecode.evidence.v1`-Fallback-Evidence.
  - Der Worker bleibt dadurch im normalen Erfolgspfad: Evidence -> Feedback-Adapter -> `completed` mit
    `feedback_md` und gueltigem `analysis_json`.
- Guardrails:
  - Die Fallback-Evidence enthaelt keine Code-Dateien (`### file:`), sondern markiert klar
    `extraction_status: source_unavailable` und den konkreten Fehlercode.
  - Das Feedback-LLM darf dadurch keine Codeanalyse vortaeuschen; es bewertet nur die transparente Evidence.
- TDD-Abdeckung:
  - Parser: malformed UTF-8 wird toleriert.
  - LocalVision: `invalid_hex_file` und `missing_makecode_source` liefern Fallback-Evidence.
  - API: Calliope-Submit akzeptiert beide Soft-Faelle (`202`), sofern Storage/Hash/Size/MIME stimmen.
  - Worker: Soft-Fall erreicht Feedback und endet `completed` ohne `vision_failed` (DB-Test; laeuft nur mit Test-DB).

Re-Verification (2026-03-14):
- `backend/tests/test_learning_calliope_hex_upload_only_api.py`
- `backend/tests/test_learning_ui_calliope_hex_upload_only.py`
- `backend/tests/test_openapi_calliope_hex_contract.py`

## Kontext / Problem
Schueler laden aktuell vor allem:
- Scratch: `.sb3` (upload-only) mit deterministischer Evidence-Extraktion.
- Visual Tasks: Bilder/PDFs (weniger deterministisch, mehr OCR/Visions).

Fuer Calliope mini (MakeCode Editor `makecode.calliope.cc`) ist das passende Abgabeformat typischerweise eine `.hex`-Datei.
Diese Datei enthaelt bei MakeCode (wenn "Source embedding" aktiv ist) neben dem Firmware-Image zusaetzliche Projekt-Metadaten
und die eigentlichen Projektdateien (z.B. `main.ts`, `main.py`, `pxt.json`, Blockly-XML).

Ziel: Calliope-Abgaben sollen wie Scratch upload-only sein, aber statt OCR soll aus der `.hex` deterministisch eine LLM-lesbare
Evidence entstehen.

## Zielbild (MVP)
- Lehrkraft erstellt `Task.kind=calliope`.
- Schueler koennen bei Calliope-Tasks **nur** `.hex` hochladen (upload-only; keine Screenshots/keine Textabgabe).
- API validiert die `.hex` bereits beim `POST .../submissions` (2026-05-10 aktualisiert):
  - Auth, Storage, Hash, MIME und Groesse bleiben harte Guards.
  - keine Intel-HEX-Struktur / Checksumme falsch -> Soft-Fallback-Evidence fuer Calliope-HEX
  - keine eingebetteten MakeCode-Quellen -> Soft-Fallback-Evidence fuer Calliope-HEX
  - Embedded Source zu gross -> `400 makecode_source_too_large`
- Worker-Pipeline bleibt bestehen:
  - statt OCR erzeugt ein Extractor aus den eingebetteten Dateien einen versionierten Markdown Evidence-Report (`makecode.evidence.v1`)
  - DSPy Feedback bewertet Kriterien ausschliesslich anhand dieses Evidence-Reports (`student_text_md`)

## User Story
Als Informatiklehrkraft moechte ich Calliope MakeCode-Abgaben als `.hex` einreichen lassen, damit ich deterministisches,
nachvollziehbares Feedback erhalte und keine Screenshots von Blockprogrammen mehr manuell interpretieren muss.

## BDD-Szenarien (Given/When/Then)
1. Calliope Upload-only UI  
   Given `Task.kind=calliope`  
   When ein Schueler die Task-Seite oeffnet  
   Then sieht er nur ein Upload-Feld fuer `.hex`.

2. Upload-Intent erlaubt nur HEX  
   Given `Task.kind=calliope`  
   When Upload-Intent mit `mime_type=application/x.makecode.hex` angefragt wird  
   Then Response enthaelt `accepted_mime_types=["application/x.makecode.hex"]`.

3. Submission akzeptiert HEX  
   Given `Task.kind=calliope`  
   When `POST .../submissions` mit `kind=file` + HEX-Metadata kommt  
   Then Response `202`, Submission `analysis_status=pending`.

4. Submission lehnt Bilder/Text ab  
   Given `Task.kind=calliope`  
   When `POST .../submissions` mit `kind=image` oder `kind=text` kommt  
   Then Response `400 invalid_input`.

5. Soft-Fall: invalid HEX
   Given Datei mit `.hex`-Endung ohne gueltige Intel-HEX Records/Checksum  
   When `POST .../submissions`  
   Then Response `202`; der Worker erzeugt Fallback-Evidence statt `vision_failed`.

6. Soft-Fall: missing embedded source
   Given gueltige Intel-HEX Datei ohne MakeCode Source Embedding  
   When `POST .../submissions`  
   Then Response `202`; der Worker erzeugt Fallback-Evidence statt `vision_failed`.

7. Worker: Evidence -> Feedback  
   Given eine gueltige Calliope-Submission  
   When der Worker den Job verarbeitet  
   Then `text_md` beginnt mit `# makecode.evidence.v1`.

## Contract-first: OpenAPI Aenderungen (`api/openapi.yml`)
- `Task.kind` enum erweitert: `...|scratch|calliope`
- Neues Schema `CalliopeTaskConfig` (MVP: leeres Objekt)
- `Task`, `TaskCreate`, `TaskUpdate`: optionales Feld `calliope` (mutually exclusive zu `h5p`/`visual`/`scratch`)
- Learning Upload-Intents: HEX MIME dokumentieren
- Learning Submissions (file): MIME enum erweitert (`application/pdf`, `application/x.scratch.sb3`, `application/x.makecode.hex`)
- Neue 400 detail codes:
  - `invalid_hex_file`
  - `missing_makecode_source`
  - `makecode_source_too_large`
- Neue 503 detail code:
  - `hex_validation_unavailable`

## Datenbank / Migration (Supabase)
- Constraint `unit_tasks_kind_check` erweitert um `calliope`.
- `learning_submissions.file.mime_type` enum/check erweitert um `application/x.makecode.hex`.
- Storage Bucket MIME-Allowlist erweitert, damit `.hex` im Upload ueber Supabase Storage akzeptiert wird.

## HEX -> Evidence (Deterministisch, bounded)
Quelle: MakeCode speichert embedded source in speziellen Records innerhalb der Intel-HEX Datei ("Source embedding").
Die embedded source besteht aus:
- Magic header
- JSON Header (`eURL`, `compression`, `headerSize`, ...)
- komprimierte Nutzdaten (typisch LZMA), die ein JSON-Objekt mit `files` enthaelt

Wichtig (Real-World):
- MakeCode Calliope Downloads nutzen fuer das Source-Embedding typischerweise Intel-HEX Records vom Typ `0x0E`.
- MakeCode Calliope Downloads koennen das Source-Embedding **nach** der Intel-HEX EOF-Zeile (`:00000001FF`) anhaengen.
  Der Parser darf deshalb nicht beim ersten EOF `break`en, sondern muss weiter nach Records scannen (Blank lines ignorieren).
- Unser Extractor muss daher neben normalen Data-Records (`0x00`) auch `0x0E` (und kompatibel `0x0D`) als scanbare Bytes
  behandeln, sonst wird faelschlich `missing_makecode_source` ausgeliefert, obwohl die Quellen vorhanden sind.

Evidence-Strategie (MVP):
- extrahiere `files` (bounded)
- rendere als versioniertes Markdown:
  - `# makecode.evidence.v1`
  - pro Datei: Name + Code-Fence mit gekapptem Inhalt
  - stabil sortiert, keine "smarten" Heuristiken (KISS, auditierbar)

UI-Strategie (Lesbarkeit):
- Schueleransicht (History): zeigt fuer Calliope **nicht** die komplette Evidence, sondern nur den relevanten Quelltext:
  `main.py` (Fallback: `main.ts`). Alle anderen Dateien (z.B. `pxt.json`) werden ausgeblendet.
- Lehrkraft-Ansicht (Live-Matrix Detail): nutzt die gleiche kompakte Darstellung fuer Calliope.
- Scratch Evidence wird in beiden Views mit einer CSS-scope Wrapperklasse gerendert (`.scratch-evidence`), damit die Darstellung
  konsistent bleibt.
- Fail-open Hardening: Wenn ein Text zufaellig mit `# makecode.evidence.v1` beginnt, aber kein gueltiges Evidence-Format enthaelt,
  wird er als normaler Markdown-Text gerendert (defense-in-depth gegen False Positives).

## Security / Hardening
- strikte Intel-HEX Parser/Checksum-Validierung bleibt im Parser erhalten; fuer Calliope-HEX werden die zwei bekannten
  Extraktionsfehler `invalid_hex_file`/`missing_makecode_source` aber als Fallback-Evidence weiterverarbeitet
- harte Groessenlimits (Input bytes, embedded source bytes, decompressed bytes, max file count, max per-file bytes)
- LZMA Decompression bounded (max output cap) gegen Zip/LZMA bombs
- `eURL` wird bewusst ignoriert: keine Host-Allowlist, keine Netzwerkzugriffe basierend auf `eURL`
- keine Dateisystem-Extraktion, alles in-memory
- stabil versionierte Evidence-Formate (nachvollziehbar, reproduzierbar)

## Relevante Implementierungsstellen (Code-Orientierung)
- HEX Validation/Extraction: `backend/storage/makecode_hex_validation.py`
- Evidence Rendering: `backend/makecode/hex_evidence_v1.py`
- Upload Policy: `backend/storage/learning_policy.py`
- Learning API: `backend/web/routes/learning.py`
- DB Guards: `backend/learning/repo_db.py`
- Worker Adapter: `backend/learning/adapters/local_vision.py`
- UI (SSR): `backend/web/main.py` (kompaktes Rendering fuer Calliope Evidence)
- UI (JS Fallbacks): `backend/web/static/js/gustav.js`
