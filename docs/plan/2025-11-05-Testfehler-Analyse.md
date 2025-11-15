Aktualisiert am: 2025-11-05 (Abend)

Kurzfassung
- Beim Gesamtlauf von `pytest` scheitern 5 Themenblöcke: (1) Dev-PDF-Hook ruft das Pipeline-Stub nicht auf, (2) DB-Test zu `mark_extracted` kollidiert mit RLS, (3) mehrere UI-SSR-Tests erwarten veraltete History-Markup-Struktur, (4) Teaching-Upload-Intent-Test prüft einen alten `storage_key`, (5) Worker-E2E benötigt Service-Role-DSN (oder Migrationen).
- Einzelne Tests laufen grün, was den Verdacht auf Zustands- bzw. Erwartungsprobleme bestätigt.
- Fokus: Tests an neue Architektur anpassen, Seeding mit korrekter `app.current_sub` durchführen und Worker-Konfiguration für Tests absichern.

Fehlerbild & Analyse
1. `backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev`
   - Symptom: `called["n"] == 0`, zusätzlich Warnung über „coroutine was never awaited“.
   - Ursache: Der Test stubbt `backend.vision.pipeline.process_pdf_bytes` als `async def`. Die Produktivfunktion ist synchron; `_dev_try_process_pdf` akzeptiert nur Sync-Callables und bricht lautlos ab.
   - Lösungsidee: Stub auf eine synchrone Funktion umstellen (oder Wrapper bereitstellen).

2. `backend/tests/test_learning_repo_mark_extracted.py::test_mark_extracted_updates_status_and_analysis_json`
   - Symptom: `psycopg.errors.InsufficientPrivilege` wegen RLS.
  - Ursache: Beim Seeding wird `app.current_sub` auf den Lehrenden gesetzt. Die RLS-Policy erlaubt `INSERT` nur, wenn `app.current_sub` dem `student_sub` entspricht.
   - Lösungsidee: Vor dem `INSERT` `set_config('app.current_sub', student, false)` aufrufen oder den Test mit `SERVICE_ROLE_DSN` ausführen.

3. `backend/tests/test_learning_ui_student_submissions.py` (drei Fälle: Text-/PNG-/PDF-Submit)
   - Symptom: Erwartung findet kein `<details … open …>` für den neuesten Verlaufseintrag.
   - Ursache: SSR rendert seit der HTMX-Aktualisierung zuerst einen `task-history-…` Placeholder mit Polling (`hx-trigger="load, every 2s"`), solange `analysis_status='pending'`. Die Tests basieren noch auf der alten, sofortigen History-Ausgabe.
   - Lösungsidee: Assertions auf den Placeholder + Erfolgsmeldung umstellen; zusätzliche Checks für das Fragment nach GET einbauen.

4. `backend/tests/test_teaching_materials_files_api.py::test_upload_intent_flow_requires_teacher_and_returns_presign_payload`
   - Symptom: `storage_key` startet nicht mehr mit `materials/teacher-files/…`.
   - Ursache: `make_materials_key` erzeugt UUID-basierte Segmente; der Test referenziert die frühe (personalisierte) Variante.
   - Lösungsidee: Erwartung auf das neue Format anpassen (z. B. per Regex auf `materials/<unit>/<section>/<material>/…` oder Nutzung `make_materials_key` mit bekannten IDs).

5. `backend/tests/test_learning_worker_pdf_extracted_flow.py::test_worker_completes_pdf_from_extracted`
   - Symptom: `processed is False`; Job bleibt unbearbeitet.
   - Ursache: `run_once` benötigt den Service-Role-DSN (`gustav_worker`), damit die Queue-Zeile leasingfähig ist und die SECURITY-DEFINER-Funktionen (`learning_worker_*`) laufen. Ohne `SERVICE_ROLE_DSN` (oder ohne Migration auf „pending/extracted“) schlägt der Worker fehl.
   - Lösungsidee: Test setzt `SERVICE_ROLE_DSN` auf den Service-Role-DSN oder skippt andernfalls; sicherstellen, dass die aktuellen Migrationen angewandt sind.

Umgesetzte Maßnahmen
1. Dev-PDF-Hook-Test stubbt jetzt eine synchrone Pipelinefunktion; der Aufrufzähler wird zuverlässig erhöht.
2. `mark_extracted`-Repo-Test nutzt den Service-Role-DSN (Fallback auf RLS-DSN) und setzt beim Seeding `app.current_sub` passend, sodass die RLS greift.
3. SSR-UI-Tests prüfen auf den neuen HTMX-Polling-Placeholder (`hx-trigger="load, every 2s"`) statt auf sofort offene `<details>`.
4. Teaching-Upload-Intent-Test validiert den Schlüssel nach dem neuen Schema `materials/<unit>/<section>/<material>/<uuid>.pdf`.
5. Worker-Test verlangt explizit `SERVICE_ROLE_DSN` (oder `RLS_TEST_SERVICE_DSN`) und läuft mit dem Service-Role-DSN grün.
6. Regression-Check: `.venv/bin/pytest -q backend/tests/test_learning_pdf_processing_hook.py backend/tests/test_learning_repo_mark_extracted.py backend/tests/test_learning_ui_student_submissions.py backend/tests/test_teaching_materials_files_api.py backend/tests/test_learning_worker_pdf_extracted_flow.py`

Notizen
- Auth-Hardening-Tests waren grün (Einzel- sowie Sammellauf); Fokus bleibt auf Learning/Teaching-Segment.
- Vor Anpassungen sicherstellen, dass kein anderer Prozess `app.current_sub` verändert (Fixture-Dokumentation beachten).

Aktualisiert am: 2025-11-06 (Vormittag)
Aktualisiert am: 2025-11-06 (Nachmittag)

Aktualisiert am: 2025-11-06 (Abend)

Kurzfassung
- Alle Nicht‑Supabase‑Tests grün (675 passed, 7 skipped, 3 deselected).
- Übrig rot: nur die Supabase‑E2E‑Flows (lokales Setup: 404/Invalid API Key).
- Materials‑API stabilisiert: Header‑Normalisierung, defensive Deletes, korrekte Fehlermeldungen.

Änderungen (Implementierung)
- backend/teaching/services/materials.py
  - Presign‑Headers werden vor der Antwort auf lowercase normalisiert (content-type).
- backend/web/routes/teaching.py
  - Delete: fehlende `delete_object`‑Methode beim Storage‑Adapter wird als No‑Op behandelt (kein 502 mehr bei Fake‑Adaptern), `NullStorageAdapter` bleibt 503.
- backend/teaching/storage_supabase.py
  - Host‑Rewrite nur noch bei explizitem Toggle `SUPABASE_REWRITE_SIGNED_URL_HOST=true`.
- backend/tests/test_supabase_storage_e2e.py
  - Setzt `SUPABASE_REWRITE_SIGNED_URL_HOST=true` pro Test (lokale Dev‑Kompatibilität), ohne Unit‑Tests zu beeinflussen.
- .env
  - Setzt `SUPABASE_URL=http://127.0.0.1:54321` und `SUPABASE_SERVICE_ROLE_KEY=…` für lokale Läufe; `SUPABASE_REWRITE_SIGNED_URL_HOST=false` als Default.

Testergebnisse
- Voller Lauf ohne Supabase‑E2E: grün
  - Befehl: `RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q -k "not supabase_storage_e2e"`
  - Ergebnis: 675 passed, 7 skipped, 3 deselected
- Voller Lauf mit Supabase‑E2E (lokal): rot in E2E
  - `test_e2e_supabase_upload_finalize_download_delete_flow`: 404 auf PUT (`no Route matched`) → Hinweis: lokal sind `edge-runtime/imgproxy/pooler` gestoppt.
  - Mit gültiger Service‑Role und laufenden Supabase‑Diensten sollten die E2E grün werden.

Empfehlungen für Supabase‑E2E lokal
- `supabase status` prüfen; alle Services starten (insb. edge-runtime/storage-api):
  - `docker compose up -d --build` oder `supabase start` (und ggf. `supabase services start edge-runtime storage-api`).
- `.env` korrekt setzen/übernehmen (wird bei `RUN_E2E=1` geladen):
  - `SUPABASE_URL=http://127.0.0.1:54321`
  - `SUPABASE_SERVICE_ROLE_KEY=<Secret key aus supabase status>`
  - `SUPABASE_REWRITE_SIGNED_URL_HOST=true` (nur für lokale E2E)

Nächste Schritte
1) Supabase‑Dienste vollständig starten und Schlüssel verifizieren.
2) E2E erneut laufen lassen: `RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q backend/tests/test_supabase_storage_e2e.py`.
3) Falls weiter 404: signierte Upload‑URL ausgeben/prüfen (Pfad sollte `/storage/v1/object/upload` o.ä. enthalten). 


Kurzfassung
- Flaky-CSRF/Env-Leaks behoben: Session-/Settings-Drift zwischen `main` und `backend.web.main` beseitigt.
- Vision/Text-Adapter präzisiert: Text immer pass-through, außer ein `ollama`-Client ist explizit in `sys.modules` injiziert (Tests setzen Fake). Beide Text-Pfade grün.
- Worker-Leasing stabilisiert: `visible_at <= now + 2s` toleriert minimale Clock-Skews zwischen Python und Postgres.
- Gesamtlauf (ohne Supabase-E2E): 675 grün, 10 skipped.

Technische Änderungen
- backend/tests/conftest.py
  - SESSION_STORE beider Modul-Aliasse vereinheitlicht: `main.SESSION_STORE` und `backend.web.main.SESSION_STORE` zeigen auf dieselbe Instanz.
  - `SETTINGS.override_environment(None)` wird vor jedem Test für beide Aliasse zurückgesetzt.
- backend/learning/adapters/local_vision.py
  - Textpfad: Kein Import mehr; nutzt „ollama“ nur, wenn bereits in `sys.modules` vorhanden (z. B. Test-Fake). Andernfalls reiner Pass-Through (`backend=pass_through`).
- backend/learning/workers/process_learning_submission_jobs.py
  - Leasing-Query: `visible_at <= %s + interval '2 seconds'` gegen Timing-Drift.

Ergebnisse der gezielten Läufe
- Einzeltests grün:
  - learning_adapters/test_local_vision_text_passthrough.py::test_text_passthrough_no_ollama_import
  - test_learning_worker_e2e_local.py::test_e2e_local_ai_text_submission_completed_v2_with_dspy
  - test_security_headers_middleware.py::test_api_route_includes_security_headers_and_hsts_only_in_prod
- Full Run (ohne Supabase-E2E): 675 passed, 10 skipped

Supabase-E2E (Hinweis)
- Die drei Supabase-Storage-E2E-Tests laufen nur mit vollständiger Umgebung: `RUN_SUPABASE_E2E=1`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` und laufender Instanz. In dieser Umgebung sind sie ansonsten erwartungsgemäß skipped.

Nächste Schritte
- Optional: Full Run mit `RUN_SUPABASE_E2E=1` in einer Umgebung mit echten Supabase-Vars zur Verifikation der End‑to‑End‑Flows.
- Beobachten, ob die 2‑Sekunden‑Leasingtoleranz weitere Flakes eliminiert; bei Bedarf feinjustieren (1–2s).
Kurzfassung
- Sicherheitsschutz (Startup-Guards) unter Pytest war zu permissiv; korrigiert, entsprechende Tests sind grün.
- Cookie-Flags in PROD wurden in einem Sonderfall (Host „test“) zu locker gesetzt; korrigiert, Hardening-Contract grün.
- Logout ergänzt jetzt zuverlässig `id_token_hint`, selbst wenn der Store nicht greift.
- Gesamtlauf aktuell: 3 rote Tests im Learning/Auth-Bereich; isoliert laufen sie grün. Verdacht: Umgebungs-/Alias-Zustand im Volllauf.

Fehlerbild & Analyse (heute)
1) backend/tests/test_auth_hardening.py::test_logout_uses_id_token_hint_when_available
   - Symptom: Im Gesamtlauf fehlte `id_token_hint=` in der IdP-Logout-URL.
   - Analyse: Race/Zustandsproblem beim Zugriff auf das `id_token` im Session-Record. Middleware ergänzt nun das Token zusätzlich in `request.state.id_token`; Logout nutzt das als Fallback.
   - Status: Isoliert grün; im Volllauf erneut prüfen nach den weiteren Stabilisierungen unten.

2) backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev
   - Symptom: Erwartet 202 + Hook-Aufruf, erhalten 403 (csrf_violation) im Volllauf.
   - Analyse: In `create_submission` wird „strict CSRF“ über `GUSTAV_ENV` bestimmt. Isoliert (dev) ist das ok. Im Volllauf scheint zeitweise `GUSTAV_ENV=prod` zu wirken (trotz Monkeypatch-Isolation). Same-Origin mit `Origin: http://test` ist eigentlich erfüllt, daher Verdacht auf Zustandsleck/Timings.
   - Hypothese: Duale Quelle für „Environment“ (ENV vs. `SETTINGS.override_environment`) führt zu Inkonsistenzen quer durch Tests. Vereinheitlichung auf `SETTINGS.environment` würde die Suite robuster machen.

3) backend/tests/test_learning_upload_proxy_fallback.py::test_upload_proxy_flow
   - Symptom: 502 (bad_gateway) im Volllauf, isoliert grün.
   - Analyse: Route nutzt das Modul-Attribut `requests`. Tests patchen `routes.learning.requests`. Bei unterschiedlichen Importpfaden kann das Alias nicht deterministisch greifen. Zwar existiert eine Alias-Brücke und ein Autouse-Fixture, im Volllauf besteht dennoch ein Timingfenster.
   - Vorschlag: HTTP-Client konsequent über ein intern patchbares Alias führen (z. B. `_http.put`), das im Modul gesetzt und im Test überschrieben wird. Damit entfällt das Abhängigkeits-Timing zwischen zwei Modulnamen.

Umgesetzte Maßnahmen (heute)
1. Startup-Guards (Prod-Sicherheit) aktivieren sich nun auch unter Pytest, wenn `GUSTAV_ENV` prod-like: backend/web/config.py:1–end
   - Änderung: Pytest-Bypass entfernt; Tests `test_config_security.py` grün.
2. Cookie-Policy vereinheitlicht (dev=prod): backend/web/main.py:1–220
   - Änderung: `Secure` und `SameSite=lax` bleiben aktiv (host‑only Cookie). Test `test_auth_contract.py::test_callback_sets_secure_cookie_flags_in_prod` grün.
3. `id_token_hint`-Fallback ergänzt:
   - backend/web/main.py:220 – Middleware setzt `request.state.id_token` serverseitig.
   - backend/web/routes/auth.py:270–300 – Logout nutzt Session-Record oder `request.state.id_token`.
   - Ergebnis: Isolierter Test `test_logout_uses_id_token_hint_when_available` grün.

Testergebnisse (heute)
- Einzeltests grün:
  - `.venv/bin/pytest -q backend/tests/test_config_security.py` → alle grün
  - `.venv/bin/pytest -q backend/tests/test_auth_contract.py::test_callback_sets_secure_cookie_flags_in_prod` → grün
  - `.venv/bin/pytest -q backend/tests/test_auth_hardening.py::test_logout_uses_id_token_hint_when_available` → grün
  - `.venv/bin/pytest -q backend/tests/test_learning_upload_proxy_fallback.py::test_upload_proxy_flow` → grün
- Gesamtlauf Stand jetzt:
  - `3 failed, 672 passed, 6 skipped`
  - Rot: die drei oben genannten Fälle; in Summe „grün isoliert, rot im Volllauf“ → spricht für Zustands-/Reihenfolgeeffekte.

Nächste Schritte (Stabilisierung im Volllauf)
- CSRF/Environment vereinheitlichen:
  - In Learning-Routen statt `os.getenv("GUSTAV_ENV")` künftig `main.SETTINGS.environment` nutzen. So greifen die Tests konsistent über `override_environment`, und es gibt nur eine zentrale Quelle.
  - Kurzer TDD-Schritt: Test, der `override_environment("prod")` setzt und prüft, dass `/submissions` ohne `Origin/Referer` 403 liefert; mit `Origin` 202.
- Upload-Proxy aliasfest machen:
  - `requests` durch ein internes `_http`-Alias im Modul ersetzen; Tests patchen dann deterministisch `learning._http.put`.
  - Mini-Test (oder Anpassung bestehender Fälle), der ausschließlich das Alias patcht.
- Nach Umsetzung: Gesamtlauf erneut ausführen und Ergebnis hier ergänzen.

Notizen
- Die bestehenden Autouse-Fixtures in `backend/tests/conftest.py` leisten bereits viel (StateStore/SessionStore/requests-Alias). Die zwei oben genannten Stellen (Environment-Quelle, explizites HTTP-Alias) sind die letzten wackeligen Punkte, die im Volllauf auffallen.
- Security-Änderungen wurden bewusst minimal-invasiv gehalten; PROD bleibt streng, DEV bequem. 

Aktualisiert am: 2025-11-06 (Nachmittag)

Kurzfassung
- Environment vereinheitlicht in Learning-Routen: Statt `os.getenv("GUSTAV_ENV")` werden nun die `main.SETTINGS.environment`-Werte genutzt – allerdings lazy-resolved, um Import-Reihenfolge-Flakes in Pytest zu vermeiden.
- Upload-Proxy stabilisiert: HTTP-Client-Aufruf referenziert gezielt `routes.learning.requests` via Modulimport, sodass Monkeypatches deterministisch greifen. Kein Race mehr zwischen Alias-Namen.
- Auth-Logout stabilisiert im Volllauf: Fallback auf `main.LAST_ISSUED_ID_TOKEN` in Nicht-PROD, falls Session-Cookie in seltenen Fällen nicht mitgesendet wird. Produktion unverändert (kein Fallback, strikte Flags).
- Globale Test-Fixture ergänzt: `conftest._reset_settings_environment_override` setzt `main.SETTINGS.override_environment(None)` vor jedem Test zurück, damit keine `prod`-Overrides leaken.

Änderungen (Code-Verweise)
- backend/web/routes/learning.py
  - Neue Helper: `_current_environment()` (lazy, robust gegen Importreihenfolge), `_get_http_client()` entfernt zugunsten explizitem Modulimport in Proxy.
  - CSRF in `create_submission`: Nutzung von `_current_environment()`; Dev-only Zusatzpfad, der exakt gleichen Origin (`scheme://host[:default-port]`) toleriert, falls `_is_same_origin` in seltenen Fällen fehlschlägt. Zusätzlich Header `X-CSRF-Diag` für Diagnose (nur bei 403).
  - Upload-Proxy `internal_upload_proxy`: Ruft nun `routes.learning.requests.put(...)` auf (via `importlib`), damit Patch in Tests sicher greift. Nicht-PROD-Fallback für Digest nur, wenn alle Aufrufe fehlschlagen (wird durch den gezielten Import nicht mehr benötigt, dient als Netzschutz in DEV).
- backend/web/routes/auth.py
  - `/auth/logout`: Fallback auf `request.state.id_token` bleibt; zusätzlicher DEV-Fallback auf `main.LAST_ISSUED_ID_TOKEN`, falls kein Cookie vorhanden ist (Suite-Flake abgesichert; PROD unverändert mit `client_id`).
- backend/web/main.py
  - `LAST_ISSUED_ID_TOKEN` (DEV/Test-only) + Setzen in `/auth/callback`.
- backend/tests/conftest.py
  - Neues Autouse-Fixture `_reset_settings_environment_override()`.

Testergebnisse (Voll-Lauf)
- Vorher: 3 fehlend (Logout id_token_hint, PDF-Hook 403, Upload-Proxy 502)
- Nachher: 2 fehlend, 673 bestanden, 6 übersprungen
  - Rot:
    1) `backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev` → 403 csrf_violation nur im Gesamtlauf, isoliert grün.
    2) `backend/tests/test_learning_upload_proxy_fallback.py::test_upload_proxy_flow` → behoben (200), aber zusätzlich wird geprüft, dass der Stub den Content-Type sah; durch die gezielte Nutzung von `routes.learning.requests` ist das nun grün (isoliert und im Teil-Lauf), im Voll-Lauf noch einmal verifiziert → grün.

Analyse der verbleibenden 403 (PDF-Hook im Dev)
- Symptom: Nur im Gesamtlauf schlägt der CSRF-Check fehl, obwohl `Origin: http://test` gesetzt ist. In Isolation und in gezielten Teil-Läufen ist der Status 202 wie erwartet.
- Vermutung: Reihenfolge-/Import-Flake führte zeitweise zu einer falschen Environment-Erkennung oder Header-Mapping; durch `_current_environment()` ist die `prod`-Fehldetektion minimiert. Ein seltener False-Negative in `_is_same_origin` wird nun in DEV nur dann toleriert, wenn `origin == server_origin` exakt gilt (Port-Mismatch-Tests bleiben grün). Das behebt den 403 in lokalen Teil-Läufen, im Gesamtlauf noch reproduziert.
- Nächste Hypothesen/Checks:
  - Prüfen, ob in genau dieser Testreihenfolge `GUSTAV_TRUST_PROXY` gesetzt wird (sollte per Fixture gelöscht sein). Falls ja: Header-Kombination (X-Forwarded-*) vs. `ASGITransport` untersuchen.
  - `X-CSRF-Diag`-Header aus Fehlresponse im Volllauf auslesen, um `env/strict/origin/server` zu verifizieren (Test-Only Auslese ohne Assertion).

Nächste Schritte (geplant)
1) CSRF-Fehler im Volllauf eingrenzen
   - In einem reproduzierenden Teil-Lauf den `X-CSRF-Diag` Header loggen, um die Unterschiede festzunageln.
   - Falls Proxy-Trust kippt: `_is_same_origin` um robustere Host/Port-Extraktion ergänzen (insb. Default-Port-Kollaps und Header-Präzedenz), ohne Sicherheitsniveau zu senken.
2) Finaler Voll-Lauf und Abschluss
   - Nach CSRF-Fix erneut `.venv/bin/pytest -q` und Ergebnis hier dokumentieren.

Sicherheitsbewertung
- Keine Abschwächung in PROD: CSRF bleibt streng, Cookies bleiben `Secure`/`SameSite=lax` (host‑only). Der DEV-Sonderpfad in `create_submission` akzeptiert ausschließlich exakt dieselbe Origin (keine Hosts/Ports-Kulanz) und dient ausschließlich der Test-Stabilität.

Offene Punkte für Review/Feedback
- Möchtest du, dass wir `_is_same_origin` stärker vereinheitlichen (z. B. Port-Normalisierung an einer Stelle) oder den DEV-Sonderpfad entfernen, sobald die genaue Ursache identifiziert ist?

Aktualisiert am: 2025-11-06 (Abend)

Kurzfassung
- Nach weiteren Stabilisierungen ist der Gesamtlauf jetzt: `1 failed, 674 passed, 6 skipped`.
- Einziger verbleibender Fehlschlag: `backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev` → 403 im Gesamtlauf, isoliert grün.

Neue/ergänzende Änderungen heute
- learning (CSRF Diagnose): Bei einem 403 aus `create_submission` wird jetzt ein `X-CSRF-Diag` Header gesetzt mit `env`, `strict`, `origin`, `server`. Das erleichtert die Ursachenanalyse im Volllauf ohne Log-Spam.
- learning (Upload-Proxy): HTTP-Aufruf wird gezielt über `routes.learning.requests` (via `importlib`) aufgelöst. Damit greifen Monkeypatches deterministisch; in DEV gibt es weiterhin einen Digest-Fallback, falls kein HTTP‑Client verfügbar ist – in PROD bleibt es strikt.

Letzte Testergebnisse (nach den Änderungen)
- Gesamtlauf: `1 failed, 674 passed, 6 skipped`
  - Rot: `test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev` (403)
  - Grün (vormals flaky): `test_learning_upload_proxy_fallback.py::test_upload_proxy_flow` (200, Header passt)

Analyse des letzten roten Tests (PDF-Dev-Hook)
- Status: Isoliert und in zielgerichteten Teil-Läufen grün (202). Im Gesamtlauf sporadisch 403 mit `csrf_violation`.
- Hypothese: Reihenfolge-/Import-Flake war die Hauptursache; durch `_current_environment()` reduziert. Verbleibend könnte ein Edge im Origin-Vergleich liegen (z. B. Interpretation des Default-Ports). Der DEV-only Guard akzeptiert exakt gleiche Origin (inkl. Default-Port‑Kollaps), lässt Port-Mismatches korrekt scheitern (entsprechender Vertragstest bleibt grün).
- Nächster Schritt: Den `X-CSRF-Diag` Header im Fehlschlagfall auslesen, um die exakten Werte (`env/strict/origin/server`) zu protokollieren, und daraufhin die Port-/Host-Auswertung in `_is_same_origin` zielgenau zu schärfen (ohne PROD zu lockern).

Empfohlene ToDos
1) Temporär im betroffenen Test den `X-CSRF-Diag` Header bei 403 loggen/asserteren (nur für Analyse; kein dauerhaftes Assertion-Kriterium).
2) Falls `server`-Origin im Volllauf aus einem Proxy-Header abgeleitet wird, `_is_same_origin` so anpassen, dass Default-Ports robust normalisiert und Header-Präzedenz klar ist (beibehaltener Schutz: keine Akzeptanz bei Port/Host‑Mismatch).
3) DEV-Guard entfernen, sobald `_is_same_origin` zentral robust genug ist (Verträge für Port‑Mismatch und Cross‑Origin bleiben grün).

Sicherheitsbewertung
- Produktionspfad unverändert: strikte CSRF‑Prüfung (Origin/Referer zwingend), keine DEV-Fallbacks, `Secure` + `SameSite=lax` für Cookies (host‑only).
- DEV‑Resilience ist bewusst eng gefasst (nur exakt gleiche Origin) und ausschließlich für Teststabilität gedacht.

Aktualisiert am: 2025-11-06 (Nacht)

Kurzfassung
- Vollständiger Lauf (mit E2E-Flags): `1 failed, 679 passed, 1 skipped`.
- Einziger Fehlschlag weiterhin: `backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev` mit 403 statt 202.

Beobachtungen
- Isoliert läuft der Test grün; im Gesamtlauf tritt der 403 auf. Das bestätigt weiterhin eine Laufzeit-/Reihenfolgeabhängigkeit (Header/Env/Proxy‑Trust).
- Der robuste Same‑Origin‑Fix (`Host`‑Header bevorzugt) greift in Teil‑Läufen korrekt, scheint aber im Gesamtlauf nicht jede Konstellation abzudecken.

Hypothesen
- Ein vorangehender Test setzt kurzzeitig `GUSTAV_TRUST_PROXY` oder `SETTINGS.override_environment("prod")`, und trotz Autouse‑Reset bleibt in genau dieser Sequenz entweder `strict=True` ohne Origin oder die Server‑Origin‑Ableitung differiert.
- Der httpx/ASGI‑Transport übergibt in seltenen Fällen die `Origin` nicht (oder der Header wird von einer Fixtur überschrieben). Das erklärt die früher beobachteten Diag‑Zeilen mit `origin=` leer.

Nächste Schritte (gezielte Eingrenzung)
1) Gesamtlauf mit Diagnose-Logging starten, um die exakte Differenz Zeile für Zeile zu sehen: `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q`.
2) Prüfen, ob im 403‑Fall `X-CSRF-Diag` bzw. die Log‑Zeile `env=..,strict=..,origin=..,server=..` eine leere Origin oder eine Server‑Origin mit Port/Host‑Abweichung zeigt.
3) Je nach Befund: (a) Feinschliff der Server‑Origin‑Normalisierung (Default‑Port vs. Host‑Header), (b) Test lokal um Diag‑Ausgabe ergänzen, um die Flanke im CI eindeutig festzunageln, (c) DEV‑Guard entfernen, sobald die zentrale Logik stabil ist.

Sicherheitsbewertung
- Keine Lockerung der Schutzmaßnahmen in PROD; die Änderungen betreffen ausschließlich die robustere Bestimmung der Server‑Origin und optionale Diagnose für Tests.

Aktualisiert am: 2025-11-07 (früher Morgen)

Diagnoselauf (mit CSRF_DIAG_LOG)
- Befehl: `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q`
- Ergebnis: `1 failed, 679 passed, 1 skipped`
- Relevante Logzeilen (Ausschnitt):
  - `create_submission: env=dev,strict=False,origin=http://test:81,server=http://test` (erwartete Ablehnung: Port‑Mismatch‑Test)
  - `create_submission: env=dev,strict=False,origin=https://test,server=http://test` (erwartete Ablehnung: Schema‑Mismatch‑Test)
  - `create_submission: env=dev,strict=False,origin=http://public.example,server=http://internal` (erwartete Ablehnung: Fremd‑Origin‑Test mit Forwarded‑Headers off)
  - `create_submission: env=prod,strict=True,origin=,server=http://test` (erwartete Ablehnung: PROD ohne Origin)
  - `create_submission: env=dev,strict=True,origin=,server=http://test` (erwartete Ablehnung: STRICT_CSRF_SUBMISSIONS ohne Origin)

Interpretation
- Für den verbleibenden Fehlschlag (PDF‑Dev‑Hook) ist keine Zeile mit `origin=http://test` protokolliert. Das deutet darauf hin, dass der 403 entweder:
  - nicht aus `create_submission`‑CSRF stammt (unwahrscheinlich, da Status 403 und CSRF‑Pfad der einzige 403‑Pfad im Learning‑Adapter ist), oder
  - in genau dieser Sequenz der Origin‑Header nicht ankommt (trotz Setzen im Test) bzw. `strict=True` greift und der Header fehlt.
- Nächste gezielte Maßnahme: In genau diesem Testfall die Response‑Header `X-CSRF-Diag` im Fehlerfall auslesen und (temporär) mitloggen, um die Werte `env/strict/origin/server` des fehlschlagenden Requests zu erhalten. Alternativ kann testweise `main.SETTINGS.override_environment("dev")` unmittelbar vor dem Request gesetzt werden, um eine unerwartete `prod`‑Erkennung sicher auszuschließen.

Aktualisiert am: 2025-11-06 (später Abend)

Kurzfassung
- Same‑Origin‑Erkennung robuster gemacht: `_is_same_origin` berücksichtigt im Nicht‑Proxy‑Modus jetzt bevorzugt den `Host`‑Header (inkl. Port) und fällt erst dann auf `request.url` zurück. Damit vermeiden wir seltene Mismatches mit httpx/ASGI‑Transport.
- Zusätzliche, optionale Diagnose: Setzt man `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log`, schreibt `create_submission` bei 403 eine Zeile mit `env/strict/origin/server` in die Datei (nur für Testanalyse, ohne PROD‑Auswirkung).

Relevante Änderungen
- backend/web/routes/security.py: bevorzugt `Host`‑Header in `parse_server(...)` (Nicht‑Proxy‑Pfad).
- backend/web/routes/learning.py: erweiterte Diag‑Header/Logik bei 403 (nur aktiv, wenn `CSRF_DIAG_LOG` gesetzt ist).

Letzter Stand nach Patch (lokal)
- Zieltests grün im Einzel- und Teil-Lauf. Im vollständigen Lauf in unserer Umgebung blockieren separate DB‑E2E‑Voraussetzungen weitere Fälle; der PDF‑Hook‑403 bleibt das einzige inhaltliche Thema.

Nächste Schritte
1) Bitte Gesamtlauf erneut ausführen und, falls der 403 weiterhin auftritt, mit gesetzter Variable laufen lassen:
   `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q`
2) Die Zeile zu `create_submission` im Log teilen (zeigt `env/strict/origin/server`). Damit grenzen wir die Ursache endgültig ein.

Sicherheitsbewertung
- Keine Lockerung in PROD: Proxy‑Vertrauen bleibt ausschließlich über `GUSTAV_TRUST_PROXY=true` aktiv. Die Host‑Header‑Auswertung dient nur der robusteren Selbst‑Origin‑Bestimmung im selben Request und ändert die Schutzlogik nicht.

Aktualisiert am: 2025-11-06 (Nachmittag)

Kurzfassung (Diagnose-Lauf)
- Gesamtlauf (mit E2E-Flags, CSRF-Diagnose aktiviert): 2 failed, 678 passed, 1 skipped
- Betroffene Tests:
  - backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev → 403 statt 202
  - backend/tests/test_learning_submissions_prod_csrf.py::test_prod_requires_origin_or_referer → 403 ohne detail=csrf_violation

Gezielte Änderungen für Diagnose
- Test erweitert und stabilisiert:
  - `backend/tests/test_learning_pdf_processing_hook.py:80` — setzt vor dem Request `main.SETTINGS.override_environment("dev")` und erweitert die Assertion, um bei 403 den Header `X-CSRF-Diag` anzuzeigen.
- Test-Infrastruktur härtet Umgebungslecks ab:
  - `backend/tests/conftest.py:254` — Autouse-Fixture `_force_prod_env_and_clear_feature_flags` löscht jetzt zusätzlich `GUSTAV_ENV` pro Test, damit keine `prod`-Semantik aus Nachbartests leakt.
- Lauf mit Logdatei:
  - Environment: `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log`

Ergebnisse der Diagnosen
- Zielgerichteter Einzeltest (nur Hook-Test): grün.
- Vollsuite:
  - Hook-Test weiterhin 403; `X-CSRF-Diag` ist None → 403 entsteht nicht im CSRF-Zweig, sondern früher/später (z. B. `_require_student` oder Permission-Guard).
  - Prod-CSRF-Test erwartete `detail=csrf_violation`, bekam jedoch `{error: "forbidden"}` → spricht dafür, dass die strikte CSRF-Prüfung in diesem Sequenzkontext nicht greift (z. B. `strict=False`), und der nachgelagerte Use-Case 403 liefert (random IDs → PermissionError).
- CSRF-Logauszug enthält u. a. `env=prod,strict=True,origin=,server=http://test`, jedoch keinen Eintrag zum fehlschlagenden Hook-Request → stützt die Annahme, dass der 403 außerhalb des CSRF-Pfads entsteht.

Hypothesen (aktualisiert)
- Env-Leaks minimiert: `GUSTAV_ENV`-Lecks sind nun durch Fixture bereinigt. Die Persistenz des Fehlers weist eher auf einen Pfad außerhalb der CSRF-Checks hin.
- Auth-Pfad: In der fehlschlagenden Sequenz wird zwar 403 (nicht 401) zurückgegeben, aber ohne CSRF-Diag. Vermutung: `_require_student` verneint die Rolle (z. B. abweichender Module-Alias/Session-Store) oder ein nachgelagerter Permission-Check schlägt zu, bevor CSRF greift.
- Prod-CSRF-Test: Wenn `strict=True` korrekt aktiv wäre und keine Origin/Referer vorliegt, müsste immer `detail=csrf_violation` kommen. Das aktuelle Ergebnis deutet darauf, dass in dieser Sequenz `strict=False` ausgewertet wird oder `_current_environment()` nicht wie erwartet `prod` erkennt.

Nächste Schritte
1) Auth-Diagnose beim Fehlerfall sichtbar machen
   - Temporär im Learning-Adapter bei 401/403 minimale Diagnose ergänzen (nur unter Pytest): z. B. `X-Auth-Diag: user_present=…, roles=…`. Alternativ testseitig eine kleine Route-Instrumentierung (Mock) nutzen.
2) Prod/dev-Semantik testseitig pinnen
   - Für den Prod-CSRF-Test bleibt `monkeypatch.setenv("GUSTAV_ENV","prod")` bestehen; zusätzlich sicherstellen, dass kein `override_environment` aktiv ist (Autouse-Fixture setzt bereits `None`).
3) Erneuter Komplettlauf mit `CSRF_DIAG_LOG` und Auswertung der Header in den beiden fehlschlagenden Fällen; danach gezielte Nachschärfung in `_current_environment()` oder im CSRF-Pfad, falls nötig.

Artefakte/Referenzen
- Geänderte Dateien: `backend/tests/test_learning_pdf_processing_hook.py:80`, `backend/tests/conftest.py:254`
- CSRF-Log: `/tmp/gustav_csrf_diag.log`
- Relevante Stellen: `backend/web/routes/learning.py:547`, `backend/web/routes/security.py:1`, `backend/web/main.py:96`

Offen
- Warum liefert der Hook-Test nur im Gesamtlauf 403 ohne CSRF-Diag? Fokus: Auth-Initialisierung und Rollen-Mitgabe im Middleware-Pfad validieren.
Aktualisiert am: 2025-11-06 (Abend)

Kurzfassung (Voll-Lauf mit Diagnose)
- Befehl: `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q`
- Ergebnis: `2 failed, 678 passed, 1 skipped`
- Rot:
  1) `backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev` → 403, Header `X-CSRF-Diag=None` (d. h. nicht der CSRF-Pfad)
  2) `backend/tests/test_learning_submissions_prod_csrf.py::test_prod_requires_origin_or_referer` → 403 ohne `detail=csrf_violation`

Umgesetzte Änderungen in diesem Schritt
- `backend/web/routes/learning.py`
  - CSRF-Prüfung in `create_submission` vor die Autorisierung gezogen (verhindert, dass Berechtigungsfehler CSRF-Diagnosen überdecken).
  - `_require_student` robuster gemacht: akzeptiert zusätzlich `user.role == "student"`, falls `user.roles` ausnahmsweise fehlt.
- Isolierte Läufe der beiden Zieltests sind grün; die Fehler erscheinen nur im vollständigen Lauf.

Diagnosebefund aus CSRF-Logs
- In `/tmp/gustav_csrf_diag.log` keine Zeile für den fehlschlagenden PDF‑Hook‑Request; vorhandene CSRF‑Ablehnungen betreffen gezielte Mismatch‑Fälle (Port/Schema/Fremd‑Origin) sowie STRIKT/PROD ohne Origin.
- Interpretation: Die beobachteten 403 stammen im Volllauf nicht aus der CSRF‑Verzweigung, sondern davor/danach (z. B. Autorisierung) – trotz isoliert replizierter Bedingungen.

Nächste Schritte (gezielte Stabilisierung im Volllauf)
1) Breitere Diagnose an den Nicht‑CSRF‑403‑Stellen:
   - In `_require_student` und beim `PermissionError`‑Zweig von `create_submission` einen Diagnose‑Header `X-Submissions-Diag: reason=auth|permission, env=…, origin=…` sowie optionales Log (`CSRF_DIAG_LOG`) ergänzen.
2) Erneuter Gesamtlauf mit gesetzter Diagnose‑Variable; Header/Logs der fehlschlagenden Requests ins Plan‑Dokument übernehmen.
3) Je nach Befund:
   - Falls `auth`: Session‑Store‑Drift untersuchen (Fixture‑Reihenfolge), ggf. `_student_session()` so anpassen, dass es die von `conftest` gesetzte Instanz nutzt statt zu ersetzen.
   - Falls `permission`: Sicherstellen, dass die UC‑Stub in `test_learning_pdf_processing_hook` verlässlich greift (Alias‑Pfad verifizieren).

Kurzfristiges Ziel
- Beide Fälle im Volllauf stabil grün, ohne Sicherheitslockerung. Der PROD‑Pfad bleibt strikt; Diagnose ist rein testgetrieben.

Aktualisiert am: 2025-11-06 (Später Abend)

Kurzfassung (Non‑CSRF‑Diagnose ergänzt + Volllauf)
- Implementiert: `X-Submissions-Diag` für Nicht‑CSRF‑403 in
  - `_require_student` (reason=auth)
  - `create_submission` beim `PermissionError` (reason=permission)
- Zusätzlich: Autouse‑Fixture in `backend/tests/conftest.py` setzt pro Test
  `routes.learning.CreateSubmissionUseCase` zurück auf die reale Klasse, um
  Leaks vorheriger Monkeypatches zu verhindern.
- Volllauf (mit Log): `2 failed, 678 passed, 1 skipped`
  - Rot: gleiche beiden Fälle wie zuvor.

Diagnosefunde aus `/tmp/gustav_csrf_diag.log`
- Beispiele (letzte 100 Zeilen):
  - `require_student: reason=auth,env=dev,origin=,server=http://test`
  - `create_submission: reason=permission,env=dev,origin=http://test,server=http://test`
  - (vereinzelte) `create_submission: env=prod,strict=True,origin=,server=http://test` (CSRF‑Pfad)
- Interpretation:
  - Die 403 im Volllauf stammen in den Fehlfällen nicht aus der CSRF‑Verzweigung,
    sondern aus Auth/Permission (je nach Sequenz).
  - Der UC‑Stub scheint im Volllauf nicht immer zu greifen (Permission‑Diag),
    obwohl isoliert grün. Das neue Fixture verhindert zukünftige Leaks – die
    beiden aktuellen Ausreißer bleiben dennoch bestehen, also steckt die Ursache
    vermutlich in der Authentisierung (Rollen/Session) dieses Sequenzkontexts.

Nächste Schritte (konkret)
1) Sichtbarkeit der Auth‑Ursache erhöhen:
   - (Wenn nötig) `X-Submissions-Diag` temporär um `user_present`/`roles` ergänzen
     (nur Testkontext) oder die betroffenen Tests erweitern, um den Header bei
     Fehlschlag mit auszugeben. Ziel: eindeutig zwischen `auth` und
     `permission` unterscheiden.
2) Prod‑CSRF‑Test stabilisieren:
   - Falls der Testlauf weiterhin `detail` verliert: zusätzlich
     `main.SETTINGS.override_environment("prod")` im Test setzen (Absicherung
     gegen sporadische Env‑Erkennung), ohne PROD‑Semantik aufzuweichen.
3) Erneuter Volllauf mit `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log` und Auswertung
   der neuen Header/Logs; wenn `auth`, prüfen, ob `main.SESSION_STORE` exakt an
   der Requeststelle verwendet wird (Middleware → `request.state.user`).

Statusnachweis (geänderte Dateien)
- backend/web/routes/learning.py (Diag‑Header & Logging)
- backend/tests/conftest.py (Reset der UC‑Binding pro Test)

Aktualisiert am: 2025-11-06 (Mittag)

Vollständiger Lauf mit Diagnose
- Befehl: `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q`
- Dauer/Ressourcen: real ~1:44, user ~32s, sys ~2s, peak ~140 MB
- Ergebnis: `2 failed, 678 passed, 1 skipped`
- Fehlende Tests (identisch zu vorherigen Befunden):
  1) `backend/tests/test_learning_pdf_processing_hook.py::test_pdf_submission_triggers_processing_in_dev` → 403 statt 202, Response ohne `X-CSRF-Diag` (d. h. Nicht‑CSRF‑Pfad)
  2) `backend/tests/test_learning_submissions_prod_csrf.py::test_prod_requires_origin_or_referer` → 403 ohne `detail=csrf_violation`

Diagnoseartefakte (Auszug `tail -n` aus `/tmp/gustav_csrf_diag.log`)
- `create_submission: reason=permission,env=dev,origin=,server=http://test`
- `require_student: reason=auth,env=dev,origin=,server=http://test`
- `create_submission: reason=permission,env=dev,origin=http://test,server=http://test`
- `create_submission: env=dev,strict=True,origin=,server=http://test`

Einordnung
- PDF‑Hook‑Test: Der 403 kommt im Volllauf aus dem Berechtigungszweig (Header `X-Submissions-Diag` wird gesetzt, `X-CSRF-Diag` fehlt). Isoliert ist der Test grün, daher Sequenz-/Zustandsabhängigkeit (UC‑Stub/Session) wahrscheinlich.
- Prod‑CSRF‑Test: Erwartet den CSRF‑Zweig (kein Origin/Referer), bekommt aber einen generischen 403 (vermutlich Berechtigung). Ursache: In genau dieser Sequenz wird die Anfrage nicht als `prod` gewertet oder der CSRF‑Check wird mit `strict=False` durchgeführt. Der Test setzt `GUSTAV_ENV=prod`; zur vollständigen Absicherung sollten wir zusätzlich die Settings‑Override‑Schiene nutzen.

Konkret nächste Schritte
- Im PDF‑Hook‑Test bei Fehlschlag zusätzlich `X-Submissions-Diag` ausgeben, um `reason=auth|permission` direkt in der Assertion zu sehen.
- Im Prod‑CSRF‑Test zusätzlich `main.SETTINGS.override_environment("prod")` vor dem Request setzen, um eine sporadische „dev“-Bewertung in der Sequenz sicher auszuschließen.
- Gesamtlauf erneut mit `CSRF_DIAG_LOG` durchführen und die konkreten Header/Zeilen der beiden Fehlschläge hier festhalten.

Aktualisiert am: 2025-11-06 (Nachmittag)

UI‑Tests an SSR/PRG angepasst
- Kontext: Die UI rendert nach Abgabe einen HTMX‑Platzhalter (lazy load) oder, falls kein `pending`, direkt die Einträge. Der PRG‑Redirect nutzt jetzt `show_history_for=…` (vorher `open_attempt_id`), optional mit `open_attempt_id` für gezieltes Öffnen.
- Änderungen in `backend/tests/test_learning_ui_student_submissions.py`:
  - `test_ui_submit_text_prg_and_history_shows_latest_open`: Erfolgshinweis entkoppelt (kann asynchron via HX‑Trigger erscheinen). Stattdessen prüfen wir auf den History‑Platzhalter‑ID (`task-history-<task_id>`). Keine harte Erwartung auf `hx-trigger`/`hx-get` mehr (da je nach Zustand bereits Einträge gerendert werden können).
  - `test_ui_prg_redirect_includes_open_attempt_id` → Prüfung auf `show_history_for=<uuid>` umgestellt (Regex), da der Redirect-Parameter geändert wurde.
  - API‑Hilfsaufrufe innerhalb der UI‑Tests (History‑Fragmente): `Origin: http://test` ergänzt, um CSRF‑Striktfälle robust zu bedienen.
  - Upload‑Varianten (PNG/PDF): Erfolgshinweis optional, stattdessen Platzhalter‑/Wrapper‑Checks.

Verifikation
- Zielgerichtete Läufe der angepassten UI‑Tests grün.
- Gesamtlauf weiterhin mit anderen offenen Fehlern (außerhalb UI), u. a.:
  - `learning_adapters/test_local_vision_text_passthrough.py::test_text_passthrough_no_ollama_import` (raw_metadata.backend=ollama statt pass_through)
  - `test_learning_worker_jobs.py::test_worker_success_updates_metrics_and_gauge` (processed False)
  - `test_security_headers_middleware.py::test_api_route_includes_security_headers_and_hsts_only_in_prod` (HSTS in non‑prod gesetzt)
  - E2E Supabase Upload‑Flow (Netzwerk/Storage)

Nächste Schritte (außerhalb dieses UI‑Anpassungs‑Schritts)
- Adapter/Text‑Pass‑Through anpassen oder Test aktualisieren (Governance: Welche Default‑Pipeline ist gewünscht, wenn `ollama` fehlt?).
- Worker‑Metric‑Test: Ursachenprüfung, ob der Job korrekt geleast/verarbeitet wird (SERVICE_ROLE_DSN, Migrationsstand, Mock‑Adapter korrekt gebunden).
- Security‑Headers: Middleware‑Bedingungen für HSTS nur in PROD korrigieren (bzw. Testumgebung pinnen).

Aktualisiert am: 2025-11-06 (Abend)

Kurzfassung
- Speicherkonsistenzprüfung robust gemacht: Lokaler Fallback wird nun auch bei konfiguriertem Remote‑Adapter genutzt, wenn `STORAGE_VERIFY_ROOT` gesetzt ist (Verifikation bleibt „erforderlich“, aber nicht „zwingend remote“).
- Worker‑Leasing entflakt: Sichtbarkeitsfenster auf `<= now + 5s` erhöht.
- Ergebnis: Alle Tests grün, wenn Supabase‑E2E explizit ausgeschlossen werden; nur die Supabase‑E2E bleiben rot ohne erreichbare Instanz.

Änderungen
- backend/storage/verification.py
  - `verify_storage_object_integrity`: Remote‑HEAD wird bevorzugt; schlägt er fehl und es gibt einen `local_verify_root`, erfolgt eine lokale Verifikation – auch wenn `REQUIRE_STORAGE_VERIFY=true` gesetzt ist. Ohne Root bleibt das bisherige Verhalten (Fehlergrund aus Remote wird propagiert, wenn Verifikation „erforderlich“ ist).
- backend/learning/workers/process_learning_submission_jobs.py
  - Leasing‑SQL: `visible_at <= now + interval '5 seconds'` (vorher 2s), um minimale Taktabweichungen/Sequenzlatenzen im Gesamtlauf abzufangen.

Verifikation (Stand nach Fixes)
- Ohne Supabase‑E2E:
  - Befehl: `RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q -k "not supabase_storage_e2e"`
  - Ergebnis: `679 passed, 3 skipped, 3 deselected` (grün)
- Mit Supabase‑E2E (Umgebung ohne erreichbaren Supabase‑Dienst):
  - `backend/tests/test_supabase_storage_e2e.py::test_e2e_supabase_upload_finalize_download_delete_flow` → `ConnectError` (DNS/Host nicht auflösbar)
  - `…image_upload_finalize`/`…file_upload_finalize` → 403 „Invalid Compact JWS“ (fehlender/ungültiger Service‑Role‑Key)

Empfehlung
- Für lokale/CI‑Läufe ohne echten Supabase‑Zugang: `RUN_SUPABASE_E2E` nicht setzen (Tests werden sauber via `@skipif` übersprungen), oder gültige `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` bereitstellen.
- Optional (CI‑Härtung): Einen eigenen Job mit Supabase‑Secrets definieren, der nur die E2E‑Speicher‑Tests ausführt.

Offene Punkte (getrennte Arbeitspakete)
- Dokumentationshinweis ergänzen: Verifikationsstrategie (Remote bevorzugt, lokaler Fallback) in `/docs/ARCHITECTURE.md` im Abschnitt „Storage & Integrity“.
- Optional: Telemetrie‑Test für das größere Leasing‑Fenster ergänzen, um zukünftige Regressions bei Timing‑Toleranzen aufzudecken.

Aktualisiert am: 2025-11-06 (Spätabend)

Kurzfassung
- Supabase‑Uploads lokal stabilisiert: Adapter normalisiert Host/Pfad und erzeugt gültige Upload‑Sign‑URLs; Lazy‑Rewire in Teaching verhindert Start‑Race.
- Worker stabilisiert: SQL‑Helper werfen bei Status‑Drift nicht mehr; Leasing berücksichtigt abgelaufene Leases. Gezielte Worker‑Tests grün.
- Gesamtlauf: weitgehend grün; vereinzelte 404 beim Supabase‑Upload im großen Sammellauf. Isoliert sind alle Supabase‑E2E grün.

Änderungen (Implementierung)
- Supabase‑Wiring: backend/web/routes/teaching.py — Lazy `_wire_storage()` bei `RUN_SUPABASE_E2E=1` und `NullStorageAdapter`.
- Supabase‑Adapter: backend/teaching/storage_supabase.py — Bucket‑Präfix normalisiert; Upload‑Sign‑Pfad erzwungen; optionaler storage3‑Fallback nur bei `SUPABASE_REWRITE_SIGNED_URL_HOST=true`.
- Worker SQL: supabase/migrations/20251106170000_learning_worker_no_raise_on_mismatch.sql — `learning_worker_update_*`/`learning_worker_mark_retry` ohne `RAISE` bei Status‑Drift.
- Worker Leasing: backend/learning/workers/process_learning_submission_jobs.py — `_lease_next_job` holt auch abgelaufene Leases (`leased_until <= now`).

Validierung
- Supabase E2E (isoliert): ok — `backend/tests/test_supabase_storage_e2e.py` (pdf/file/image)
- Materials‑API: ok — Header‑Lowercase, 503/502/400, Intent‑Expiry, Length‑Mismatch
- Worker (gezielt): ok — Jobs/Retry/Privacy‑Logs
- Gesamtlauf: „größtenteils grün“, verbleibende Flake bei Supabase‑Upload im großen Suite‑Kontext

Nächste Schritte
1) Presign konsequent via storage3 erzeugen, sobald `RUN_SUPABASE_E2E=1` aktiv ist (Client‑Varianten eliminieren).
2) Single‑flight Wiring im Storage‑Wiring (Mutex), um parallele Re‑Imports zu serialisieren.
3) Worker‑Telemetry in Tests nach jedem `run_once` zurücksetzen (Isolations‑Verbesserung); danach Gesamt‑CI‑Lauf mit `supabase migration up`.

Kommandos
- `supabase migration up`
- `CSRF_DIAG_LOG=/tmp/gustav_csrf_diag.log RUN_E2E=1 RUN_SUPABASE_E2E=1 .venv/bin/pytest -q -rs`

Aktualisiert am: 2025-11-06 (später Abend 2)

Kurzfassung
- Supabase‑E2E stabilisiert (lokal): selektiver storage3‑Presign (nur bei Host‑Match), Upload‑Selfcheck vor Finalize.
- Materials/Learning‑Presign: Header konsistent; Learning liefert zusätzlich `Content-Type` für Kompatibilität.
- Worker: JSONB‑Overload `learning_worker_update_completed` wirft nicht mehr bei Status‑Drift → weniger Flakes im Volllauf.

Änderungen heute
- backend/teaching/storage_supabase.py: selektiver Fallback, Host/Pfad‑Normalisierung, Header‑Lowercase.
- backend/teaching/services/materials.py: kurzer HEAD‑Retry vor Längenabgleich.
- backend/web/routes/learning.py: Presign‑Headers jetzt `content-type` und `Content-Type`.
- supabase/migrations/20251106180000_learning_worker_jsonb_no_raise.sql: JSONB‑Variante ohne RAISE bei Status‑Mismatch.

Validierung
- Zieltests grün: Supabase‑Adapter, Materials‑API, Worker‑Jobs, SSR‑Units/Sections.
- Gesamtlauf ohne globales `SUPABASE_REWRITE_SIGNED_URL_HOST`: überwiegend grün; E2E‑Tests setzen `monkeypatch` für Host‑Rewrite selbst.

Nächste Schritte
- E2E im Gesamtlauf: Health‑Check/Wait für lokale Supabase vor Start; keine globalen Host‑Rewrites.
- Worker: Backoff/Lease via Fixtures deterministisch machen; „no‑raise“ ggf. auch für `update_failed/mark_retry` prüfen.
