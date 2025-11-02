# Plan: Teaching‑Live Security Hardening (Detail‑Endpoint)

Ziel: Datenabfluss verhindern und Konsistenz zum API‑Vertrag herstellen.

Änderungen
- Endpunkt `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`:
  - Strenge Relation: `task ∈ unit ∈ course` (404 bei Verstoß)
  - Kein direkter Tabellen‑Fallback mehr; nur SECURITY‑DEFINER Helper
  - Einheitliche Owner‑Headers: `Cache-Control: private, no-store`, `Vary: Origin`
- SQL‑Helper: Signatur erweitert (`p_unit_id`) und Relation in SQL überprüft
- OpenAPI: `released_at` mit `format: date-time`; `additionalProperties: false`; 204‑Headers ergänzt
- Makefile: Geheimnisse nicht mehr ins Log echo’n

Tests
- Neuer Test `test_teaching_live_detail_relation_guard.py`: 404, wenn Task nicht zur Unit gehört
- Bestehende Contract‑/Delta‑Tests weiter grün

Risiken & Rollback
- Migration ersetzt Funktionssignatur: Konsumenten sind nur der Web‑Adapter (angepasst). Rollback durch Re‑Create der alten Signatur möglich.

