# Plan 2025-10-27 — Learning API hardening (cache headers, 403, schemas)

Context
- Student-seitige Endpunkte wurden eingeführt: `GET /api/learning/courses`, `GET /api/learning/courses/{course_id}/units`.
- Review ergab: fehlende 403 im Vertrag, Cache-Control-Beispiele inkonsistent, Schemas zu liberal.

User Story
- Als Schüler möchte ich meine Kurse und die Lerneinheiten sicher und datensparsam abrufen, damit keine schützensamen Daten im Cache landen und der Vertrag klar ausdrückt, wer zugreifen darf.

BDD
- Given ein eingeloggter Lehrer, When GET /api/learning/courses, Then 403 Forbidden.
- Given keine Session, When GET /api/learning/courses/{id}/units, Then 401.
- Given limit=500, When GET /api/learning/courses, Then 200 und niemals mehr als 50 Items.
- Given API Contract, When Client generiert wird, Then 403 ist dokumentiert und Responses tragen `Cache-Control: private, no-store`.

Kontrakt (OpenAPI)
- Ergänze 403 für beide Learning-Pfade.
- Setze Cache-Control Beispiele auf `private, no-store`.
- `additionalProperties: false` für `LearningCourse` und `UnitPublic`.

Tests (pytest)
- Ergänze Tests: non-student→403, units→401, clamp (limit≤50).

Implementierung
- API-Adapter: `_cache_headers()` auf `private, no-store`.
- UI: Seitentitel “Meine Kurse”.

Sicherheit
- RLS bleibt unverändert; nur Header-/Vertrags-Härtung. 404-Semantik bei Nicht-Mitgliedschaft bleibt.

Done-Kriterien
- Tests grün/skip bei fehlender DB, Vertrag konsistent, Changelog-Eintrag vorhanden.

