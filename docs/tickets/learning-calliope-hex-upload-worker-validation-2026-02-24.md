# Ticket: Calliope HEX - Upload/Submit und Worker-Validierung inkonsistent

**Status:** abgeschlossen

**Abschluss-Hinweis (2026-03-14):**
Die dokumentierten Hotfixes sind im aktuellen Repo-Stand vorhanden; die
relevanten Calliope-Regressionen wurden erneut ausgefuehrt und bleiben gruen.

## Summary
Bei mehreren Schuelerabgaben fuer `Task.kind=calliope` trat ein zweistufiges Problem auf:
1. Upload funktionierte, aber Submit scheiterte teilweise an strikter HEX-Validierung.
2. Nach Submit-Soft-Fail wurden Abgaben zwar persistiert, aber im Worker teils weiter
   als `vision_failed` mit `vision_last_error=invalid_hex_file` markiert.

Dieses Ticket dokumentiert Ursache, umgesetzte Hotfixes und verbleibende Follow-ups.

## Impact
- Lernende konnten Abgaben teilweise nicht final einreichen.
- Nachgelagerte Analyse endete in Teilen mit Fehlerstatus statt Feedback.
- Fuer Lehrkraefte wirkte der Statusverlauf inkonsistent (persistiert, aber failed).

## Reproduktion (PII-frei)
1. In einer Calliope-Task eine `.hex` Datei hochladen.
2. Submit ausloesen.
3. Vor Hotfix:
   - entweder `400` auf Submit,
   - oder spaeter `analysis_status='failed'`, `error_code='vision_failed'`,
     `vision_last_error='invalid_hex_file'`.
4. Nach Hotfix:
   - Submit wird nicht mehr durch die beiden bekannten Codes blockiert,
   - Worker endet fuer neue Faelle in `completed` (normal oder soft-complete Hinweis).

## Root Cause
### Submit-Pfad
- Die Validierung im API-Submit-Pfad war fuer bestimmte reale HEX-Exporte zu streng.
- Details `invalid_hex_file` und `missing_makecode_source` wurden als harte `400` behandelt.

### Worker-Pfad
- Der HEX-Parser nutzte striktes UTF-8-Decoding fuer eingebetteten MakeCode-Source-Text.
- Einzelne ungewoehnliche Byte-Sequenzen fuehrten dadurch zu Verwerfen des Markers und
  final zu `invalid_hex_file`.
- Der Worker behandelte diese Details als terminalen Permanent-Fehler (`vision_failed`).

## Implementierter Hotfix (Ist-Stand)
1. **API Submit soft-fail**
   - Datei: `backend/web/routes/learning.py`
   - `invalid_hex_file` und `missing_makecode_source` blockieren Submit nicht mehr fuer Calliope.

2. **Parser tolerant bei UTF-8**
   - Datei: `backend/storage/makecode_hex_validation.py`
   - Fallback von UTF-8 strict auf UTF-8 mit `errors=\"replace\"`.
   - Metadaten zur Transparenz: `decode_mode`, optional `decode_replacements`.

3. **Worker soft-complete fuer irrecoverable HEX**
   - Datei: `backend/learning/workers/process_learning_submission_jobs.py`
   - Fuer Calliope HEX + Detail `invalid_hex_file`/`missing_makecode_source`:
     - kein `vision_failed`,
     - stattdessen `completed` mit Hinweis-Feedback und minimalem `analysis_json`.

## Acceptance Criteria
1. Neue problematische Calliope-HEX-Abgaben werden nicht mehr im Submit mit `400`
   auf die beiden bekannten Codes geblockt.
2. Neue problematische Calliope-HEX-Abgaben enden im Worker nicht mehr als
   `vision_failed` auf diesen Codes.
3. Nicht-Calliope-Dateitypen (z. B. Bild/PDF/SB3) behalten ihr bestehendes Fehlerverhalten.

## Verification Checklist (Ops)
1. `docker compose ps` zeigt `web` und `learning-worker` healthy.
2. Eine vorher auffaellige Calliope-HEX-Abgabe neu einreichen.
3. In DB pruefen:
   - kein frischer `failed` Datensatz mit `vision_last_error='invalid_hex_file'`,
   - stattdessen `completed` (normal oder soft-complete).
4. Logs pruefen:
   - web: `calliope_hex_validation_soft_fail ...`
   - worker: `Calliope HEX vision soft-fail completion ...`

## Risks
- Stark korruptes HEX-Material kann als `completed` mit Hinweis enden, ohne vollstaendige
  Kriterienanalyse.
- Das ist bewusst als Betriebsstabilitaets-Tradeoff fuer den laufenden Unterricht gesetzt.

## Follow-ups
1. Regressionstests fuer malformed UTF-8 in eingebettetem HEX-Source-Payload ergaenzen.
2. Optional Teacher-UI Kennzeichnung fuer `completed_soft_fail` einfuehren.
3. Monitoring auf Haeufigkeit von `decode_mode=utf8_replace` zur Langzeitbewertung.
