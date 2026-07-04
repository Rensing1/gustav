# Security Baseline

Status: Draft
Owner: Produktverantwortlicher
Local checks: `make harness-minimum`, `make test-db-security`
CI status: `make harness-minimum` läuft über `.github/workflows/harness-minimum.yml`
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich während des Harness-Refactors

## Zweck
Dieses Dokument bündelt die Sicherheitsgrenzen, die im Harness sichtbar und später hart automatisiert werden.

## Harte PR-1-Signale
- Public-Repo-Hygiene und keine Secrets/PII.
- Unsichere Produktionsdefaults sind blockierend.
- Unauthentifizierter Zugriff auf geschützte APIs bleibt getestet.
- OpenAPI-Sicherheits- und Cache-Control-Verträge bleiben sichtbar.
- Privacy-Logging darf keine sensiblen Inhalte verlieren.
- Testumgebung und DB-required Guards bleiben eindeutig.

## Harte PR-2-Signale
- Browser-Writes ohne `Origin` und ohne `Referer` werden für Learning-Submission- und Teaching-Write-Baselines mit `csrf_violation` abgewiesen.
- Same-origin Learning- und Teaching-Writes bleiben erlaubt, wenn die fachlichen Vorbedingungen erfüllt sind.
- CSRF-Diagnoselogging redigiert `Referer`-Pfade und Query-Strings.
- Session-Cookies aus Auth-Callback und BFF-Session-Sync bleiben host-only, `HttpOnly`, `Secure` und `SameSite=lax`.
- `make test-db-security` ist der lokale harte Gate-Baustein für diese Regressionen.

## Harte PR-3-Signale
- `make test-db-security` setzt `REQUIRE_DB_TESTS=1`; DB-/RLS-Skips sind in diesem Gate keine akzeptierte Erfolgsbedingung.
- Unauthentifizierte, ungültige Bearer- und BFF-Cookie-only-Zugriffe bleiben negative Authz/Authn-Regressionen.
- Teaching-Live-Detail-Routen schützen fremde Kurs- und Submission-Daten über API- und Relation-Guard-Tests.
- Learning-RLS schützt studentische Sicht auf freigegebene Kurs-, Unit-, Section-, Material- und Task-Daten.
- Membership-Delete bleibt owner-gebunden: direkte RLS-Policy, Repository-Pfad und SECURITY-DEFINER-Helper dürfen Nicht-Owner nicht autorisieren.
- RLS-Helper behalten eingeschränkte EXECUTE-Privilegien; `PUBLIC` darf student-facing Helper nicht ausführen.

## Harte PR-4-Signale
- `make test-upload-llm-boundaries` schützt Upload-Intent-, Proxy-, Storage-Key-, Storage-Verifikations-, Content-Signatur-, Submission-Kind-, Feedback-/DSPy- und Privacy-Contracts.
- Uploads werden technisch begrenzt: Größe, MIME/Extension, erlaubte Hosts, Pfade, Header und Content-Signaturen bleiben fail-closed.
- Schüler-Submissions werden vor dem LLM nicht inhaltlich geprüft, nicht gefiltert, nicht normalisiert, nicht moderiert und nicht umgeschrieben.
- Das LLM erhält den originalen Schülerinhalt; technische Verpackung ist erlaubt, wenn sie keine semantische Änderung oder Vorbewertung einführt.
- Das gespeicherte Original bleibt unverändert. Logging darf keine sensiblen Inhalte, Roh-Submissions, Secrets oder Session-IDs ausgeben.

## Ausbaustufen
Supabase-Storage-, H5P-E2E- und OpenAI/Ollama-Smokes bleiben nach PR 4 als opt-in Integrationssignale sichtbar.
