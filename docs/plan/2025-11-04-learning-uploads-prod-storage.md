# Learning: Prod‑taugliche, dauerhafte Upload‑Speicherung (Presigned URLs)

Datum: 2025-11-04
Autor: GUSTAV Team (Lehrer/Entwickler)
Status: In Umsetzung (Contract & Tests live; OpenAPI „method“ noch offen)

## Hintergrund & Ziel
Im MVP werden Uploads (JPG/PNG/PDF) über eine interne Dev‑Stub‑Route lokal abgelegt, primär zur Größen/Hash‑Verifikation. Für Produktion brauchen wir dauerhafte, sichere Speicherung über einen Objekt‑Storage mit kurzlebigen, signierten URLs (presigned PUT) und sauberem API‑Vertrag. Ziel ist eine robuste, DSGVO‑konforme Lösung, die den Traffic großer Dateien nicht durch die App schleust und klar getestetes Fehlverhalten (403/404/503) liefert.

Nicht‑Ziele:
- Vollständige OCR/Extraktion in diesem Schritt (Vision/Feedback bleibt entkoppelt).
- Öffentliche Buckets. Buckets bleiben privat; nur kurzlebige, signierte Links werden an Clients gegeben.

## Annahmen
- Storage‑Provider: Supabase Storage (S3‑ähnliche Semantik) mit Service‑Role‑Schlüssel serverseitig.
- Bereits vorhandenes Adapter‑Muster aus „Teaching“ wird 1:1 wiederverwendet (Protocol + Supabase‑Implementierung) — kein zweites Protokoll in Learning definieren; Import aus `backend/teaching/storage.py`.
- Frontend nutzt weiterhin den Flow: upload‑intent → PUT (oder provider‑spezifisch POST) → POST /submissions (storage‑Metadaten + sha256). Die konkrete HTTP‑Methode wird über `intent.headers` (und optional zukünftig `intent.method`) transportiert; default bleibt `PUT`.

## Repo‑Konsistenz & Architekturentscheidungen
- Adapter‑Wiederverwendung: ✅ `StorageAdapterProtocol`/`NullStorageAdapter` aus Teaching werden im Learning‑Router genutzt; Supabase‑Implementierung bleibt in `backend/teaching/storage_supabase.py`.
- Eine Quelle der Wahrheit für Limits/Patterns: ✅ gemeinsame Konstanten in `backend/storage/learning_policy.py`.
- Verifikation auslagern: ✅ `_verify_storage_object` delegiert an `backend/storage/verification.py`.
- Konfiguration bündeln: ❌ ENV‑Variablen werden aktuell direkt im Router gelesen, nicht zentral in `backend/web/config.py`.

## Umsetzungsstand (2025‑11‑04)
- API‑Vertrag: `StudentUploadIntent{Request,Response}` und Presign‑Pfad dokumentiert (inkl. 400/401/403/404/503, Cache/Vary‑Header).
- Backend: `create_upload_intent`, `_verify_storage_object`→Helper und Dev‑Stub implementiert; Presign liefert absolute URL, `REQUIRE_STORAGE_VERIFY` führt Retry‑Schleife aus.
- Tests: Pytests decken Happy Path, Validierung, CSRF, 503 und Contract ab; laufen grün.
- Doku: CHANGELOG und `docs/references/learning.md` beschreiben Upload‑Intent; Storage‑CORS‑Runbook erstellt (`docs/runbooks/storage_cors_supabase.md`).
- Offene Nacharbeiten: OpenAPI ggf. um `method`‑Feld ergänzen oder Feld aus Response entfernen.

## User Story
Als Schüler möchte ich Dateien (JPG/PNG/PDF) zuverlässig und sicher hochladen, damit meine Abgabe dauerhaft gespeichert ist und der KI‑Worker sie analysieren kann — ohne, dass große Dateien durch den App‑Server fließen.

Als Betreiber möchte ich, dass Uploads in einem privaten, produktionsfesten Speicher landen, mit klaren Limits, Audits und verständlichen Fehlern bei Misskonfigurationen.

## BDD‑Szenarien (Given‑When‑Then)
1) Happy Path
- Given ich bin Kursmitglied und die Aufgabe ist freigeschaltet
- When ich POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents mit kind=image|file, filename, mime_type, size_bytes und gültigem Origin sende
- Then erhalte ich 200 mit storage_key, absoluter presigned PUT url, headers (Content‑Type), expires_at
- And When der Browser die Datei auf die presigned url PUTtet und ich danach POST /submissions mit storage_key, mime_type, size_bytes, sha256 sende
- Then erhalte ich 202 und meine Historie zeigt Platzhaltertext/Feedback

2) CSRF
- Given ich rufe upload‑intents ohne Origin/mit fremdem Origin auf
- Then erhalte ich 403 { error: forbidden, detail: csrf_violation }

3) Sichtbarkeit/Mitgliedschaft
- Given ich bin nicht Mitglied oder die Aufgabe ist für mich nicht freigeschaltet
- When ich upload‑intents aufrufe
- Then erhalte ich 404 (kein Informationsleck)

4) Validierung
- Given ich sende GIF oder > Limit
- Then erhalte ich 400 (mime_not_allowed | size_exceeded)

5) Storage nicht konfiguriert
- Given kein Storage‑Adapter
- When ich upload‑intents aufrufe
- Then erhalte ich 503 service_unavailable

6) Finalisierung mit falschen Metadaten (optional strikt)
- Given HEAD ergibt size/hash‑Mismatch und REQUIRE_STORAGE_VERIFY=true
- Then POST /submissions → 400 invalid_*_payload

7) Dev‑Stub abgesichert
- Given ENABLE_DEV_UPLOAD_STUB=false (prod default)
- When PUT /api/learning/internal/upload-stub
- Then 404

8) Eventual Consistency (strict verify)
- Given das Objekt ist direkt nach dem Upload per HEAD kurz nicht sichtbar
- When REQUIRE_STORAGE_VERIFY=true
- Then erfolgt eine kurze Retry‑Schleife; bei weiterhin fehlender Sichtbarkeit → 400 invalid_*_payload mit detail=verify_timeout

## API‑Vertrag (Contract‑First)
- Beibehalten: `POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents`
  - Response 200: { intent_id, storage_key, url (absolute), headers, accepted_mime_types, max_size_bytes, expires_at } — **Anmerkung:** Implementierung liefert zusätzlich `method`; Vertrag muss ergänzt oder Feld entfernt werden.
  - Fehler: 400 invalid_input|mime_not_allowed|size_exceeded|invalid_uuid · 401 unauthenticated · 403 csrf_violation · 404 not_found · 503 service_unavailable
  - Sicherheitsheader: `Cache-Control: private, no-store`, `Vary: Origin`
- Dev‑Stub: `PUT /api/learning/internal/upload-stub` bleibt dokumentiert, aber mit klarer Dev‑Flag‑Anforderung `ENABLE_DEV_UPLOAD_STUB=true`; prod default OFF.

Ergänzungen in `api/openapi.yml`:
- Klarer Hinweis, dass `url` eine absolute, potenziell Cross‑Origin‑Adresse ist (CORS notwendig). 503‑Antwort explizit unter /upload‑intents.
- x-permissions: requiredRole=student; x-security-notes: Same‑Origin bei upload‑intents, RLS bei /submissions.
- `expires_at` ist „advisory“ (aus TTL berechnet); das tatsächliche Ablaufverhalten bestimmt der Storage‑Provider.
- Offene Entscheidung: `method` wird bereits in der Response geliefert; Frontend nutzt aktuell nur `headers`. Vertrag angleichen oder Feld entfernen.

## Datenbank/Migration
Option A (minimal, bevorzugt zunächst):
- Kein Schema‑Change; Bucket via ENV `LEARNING_STORAGE_BUCKET` (Default: `submissions`).

Option B (erweiterbar):
- `alter table app_learning_submissions add column storage_bucket text null check (storage_bucket ~ '^[a-z0-9][a-z0-9-]{1,62}$');`
- Audit‑Tabelle für Upload‑Intents: `app_learning_upload_intents_audit(id uuid pk, created_at timestamptz default now(), course_id uuid, task_id uuid, student_sub text, storage_key text, mime text, size_bytes int, expires_at timestamptz)`; RLS optional (teacher/operator).

Hinweise zur Wartbarkeit:
- Option B nur bei konkretem Bedarf aktivieren und mit Aufbewahrungsregeln (Retention) versehen; RLS strikt (nur Lehrkräfte/Operatoren). Bis dahin Protokollierung über Access‑Logs.

## Tests (Pytest, Rot → Grün)
- Contract/Behavior
  - upload‑intents 200: absolute URL + headers echo (mock StorageAdapter.presign_upload)
  - 503 bei NullStorageAdapter (Adapter‑Exceptions werden zu 503 gemappt, nicht 500)
  - 403 ohne/foreign Origin
  - 404 wenn nicht freigeschaltet/nicht Mitglied (reused UseCase‑Check)
  - 400 Grenzen für MIME/Größe
- Integration
  - intent → (simuliertes) PUT → finalize /submissions → 202 → Historie enthält Placeholder; Idempotency‑Header wie gehabt
- Verifikation
  - `_verify_storage_object` nutzt Adapter.head_object (size), Hash optional; `REQUIRE_STORAGE_VERIFY=true` erzwingt 400 bei Mismatch
  - Kurzzeit‑Retry auf HEAD (z. B. 1× nach ~150 ms) und detail=verify_timeout bei Persistenzfehlern
- Dev‑Stub Flag
  - ENABLE_DEV_UPLOAD_STUB=false → 404 auf internal/upload‑stub
  - ENABLE_DEV_UPLOAD_STUB=true → 200; weiterhin CSRF‑Schutz aktiv

Erweiterte Assertions:
- `url` ist absolut (http/https) und nicht relativ; `Vary: Origin` + `Cache-Control: private, no-store` stets gesetzt.
- `expires_at` ist ein gültiger ISO‑Zeitstempel in UTC; Test akzeptiert Advisory‑Charakter.

## Implementierungsplan (TDD)
1) Tests schreiben/erweitern (Rot)
- Neue Tests unter `backend/tests/test_learning_upload_intents_storage_adapter.py` (503/absolute URL/CSRF/404/400)
- Verifikations‑Tests für HEAD‑Pfad in `test_learning_submission_storage_verification.py`
- Dev‑Stub‑Flag‑Test in `test_learning_upload_stub_route.py`

2) Minimal‑Implementierung (Grün)
- Storage‑Adapter wiring (Learning)
  - In `backend/web/routes/learning.py`:
    - `LEARNING_STORAGE_BUCKET = os.getenv('LEARNING_STORAGE_BUCKET', 'submissions')` (Lesen zentral über `backend/web/config.py` bündeln)
    - `LEARNING_STORAGE_ADAPTER: StorageAdapterProtocol = NullStorageAdapter()`; `set_learning_storage_adapter()` für Tests (Protocol aus Teaching importieren)
  - TTL via `LEARNING_UPLOAD_INTENT_TTL_SECONDS` (Default 600)
- `create_upload_intent` anpassen
  - Statt lokaler Stub‑URL: `presign = LEARNING_STORAGE_ADAPTER.presign_upload(bucket=..., key=storage_key, expires_in=ttl, headers={'Content-Type': mime})`
  - Response `url = presign['url']` (absolut), `headers = presign.get('headers', {'Content-Type': mime})`
  - 503, wenn Adapter nicht konfiguriert oder Fehler `storage_adapter_not_configured` (enge try/except)
- `_verify_storage_object` erweitern
  - Wenn Adapter gesetzt: `head = adapter.head_object(bucket, storage_key)` → `content_length` prüfen; Hash optional (wenn verfügbar, sonst "skipped" wenn `REQUIRE_STORAGE_VERIFY!=true`); kurze Retry‑Schleife für Eventual Consistency
  - Fallback auf lokalen Pfad nur, wenn `STORAGE_VERIFY_ROOT` gesetzt und Dev‑Flow verwendet wird
- Dev‑Stub Feature‑Flag
  - `ENABLE_DEV_UPLOAD_STUB` aus ENV; wenn false → Route antwortet 404 (Default: false). Weiterhin Same‑Origin‑Pflicht.

3) Refactor & Doku
- Prägnante Docstrings (Absicht, Parameter, Berechtigungen) in den betroffenen Handlern
- CHANGELOG: API‑/Security‑Abschnitt ergänzen
- Docs: Kurzer Leitfaden „Storage CORS konfigurieren“ unter `docs/runbooks/storage_cors_supabase.md` (allow PUT/HEAD/OPTIONS von App‑Origin, allow Content‑Type, expose ETag)
- Constants/Config: Gemeinsame Limits und Patterns in einem Modul bündeln und in Teaching/Learning verwenden.

## Frontend
- `backend/web/static/js/gustav.js` nutzt bereits `intent.url` und `intent.headers`; keine Änderung nötig.
- Robustheit: `intent.headers` strikt verwenden; perspektivisch optional `intent.method` unterstützen (ohne Breaking Change). `expires_at` nur als Anzeige/Hinweis nutzen.
- UX‑Verbesserungen (separat): Submit‑Button bis Abschluss des PUT deaktivieren, Fortschritt/Fehler inline.

## Worker (Lernen)
- Kurzfristig keine Änderung erforderlich, da Submissions weiterhin über DB/Queue fließen und Placeholder generiert werden.
- Optional: Für echte OCR später Bytes via kurzlebiger presigned GET oder Service‑Client lesen (nicht Teil dieses Plans).

## Betrieb & Sicherheit
- CORS am Storage: App‑Origin erlauben, Methoden: PUT/HEAD/GET; Header: Content‑Type; Expose: ETag
- Secrets: `SUPABASE_SERVICE_ROLE_KEY` nur serverseitig; in prod Fail‑Fast wenn Dummy (bereits durch config‑Guard)
- Größen‑/MIME‑Limits konsistent in API/Frontend/Tests
- Rate‑Limits/Abuse‑Schutz: Intent‑Erstellung und Stub‑PUT drosseln (Proxy‑Schicht oder App‑Middleware)
- Aufräumen: Job/Script zum Löschen verwaister Objekte (>24h ohne Submission) als Folgeaufgabe
- Finalisierungsfenster: Best‑Effort‑Ablehnung sehr alter Intents beim Finalize (z. B. > 60 Minuten) — nur Advisory, Storage‑TTL ist maßgeblich.

## Rollout
1) OpenAPI aktualisieren (503/absolute URL/Flags/Security‑Notes)
2) Tests implementieren → rot
3) Adapter‑Wiring + Intent‑Handler + Verifikation + Flag → grün
4) Compose/K8s: Supabase‑Vars setzen (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`), `LEARNING_STORAGE_BUCKET=submissions`, `LEARNING_UPLOAD_INTENT_TTL_SECONDS=600`
5) Storage‑CORS konfigurieren (PUT von App‑Origin erlauben)
6) Smoke‑Test: intent → PUT (per curl) → finalize → Historie; Logs des Workers beobachten
7) Rate‑Limit konfigurieren (Reverse‑Proxy) für Intent/Stub‑Pfade

## Definition of Done (DoD)
- Alle neuen Tests grün; bestehende Upload‑/Contract‑Tests bleiben grün
- Upload‑Intents liefern absolute presigned URL; 503/403/404/400 korrekt
- Dev‑Stub in prod abgeschaltet (ENABLE_DEV_UPLOAD_STUB=false); in dev optional aktivierbar
- Doku/CHANGELOG aktualisiert; Security‑Header konsistent
- Verifikation stabil (inkl. kurzer Retry), klare Fehlermeldungen (`verify_timeout`, `invalid_*_payload`)

## Risiken / Offene Punkte
- Hash‑Verifikation ist bei vielen Storage‑Backends nicht zuverlässig via HEAD/ETag möglich → optional und per Flag erzwingbar
- CORS‑Fehlkonfiguration führt zu Frontend‑Fehlern trotz korrekter Serverantwort → eigener Leitfaden + Checks
- Orphaned objects: Aufräumtask nötig, wenn Finalisierung ausbleibt
- Supabase‑Semantik: `create_signed_upload_url` kann provider‑spezifisch POST statt PUT erfordern — Response liefert bereits `method`; OpenAPI/Frontend müssen konsistent bleiben.
- Einheitliche Limits/Patterns müssen in beiden Kontexten (Teaching/Learning) gemeinsam gepflegt werden — Zentralisierung in Config zwingend nachziehen.

## Nächste Schritte (konkret)
- [x] OpenAPI‑Anpassung schreiben
- [x] Pytest‑Fälle (503/absolute URL/CSRF/404/400/HEAD‑Verifikation/Dev‑Stub‑Flag)
- [x] Minimal‑Implementierung Learning‑Router (Adapter‑Wiring, Intent, Verifikation)
- [x] Doku & CHANGELOG
- [x] Runbook `docs/runbooks/storage_cors_supabase.md`
- [x] Constants/Limits zentralisieren und in beiden Routen nutzen
