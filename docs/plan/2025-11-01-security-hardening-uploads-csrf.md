# Plan: Security hardening for uploads & CSRF (2025‑11‑01)

## Ziel
- DSGVO/Least‑Privilege: Verhindere DSN‑Leaks im Legacy‑Import.
- CSRF: In Produktion strikte Same‑Origin‑Policy für Submissions erzwingen.
- API‑Klarheit: 404 für Upload‑Intents dokumentieren (Task nicht sichtbar/gefunden).

## Änderungen
- scripts/import_legacy_backup.py: Entferne DSN‑Log/Reportfeld, Hinweis im Code.
- backend/web/routes/learning.py: In PROD immer `_require_strict_same_origin` bei POST /submissions.
- api/openapi.yml: 404‑Response für POST /upload‑intents mit Cache/Vary‑Headern.

## Tests (TDD)
- OpenAPI: 404 für Upload‑Intents vorhanden.
- Submissions: Idempotency‑Key Regex (negativ/positiv).
- Submissions: PROD erfordert Origin/Referer.

## Risiken / Rollback
- Minimaler Blast‑Radius (Learning‑Routes, Import‑Script, OpenAPI). Rollback via Revert.

## Done Criteria
- Pytests grün/übersprungen gemäß DB‑Verfügbarkeit, OpenAPI‑Tests grün.
- CHANGELOG und Migration‑Doku aktualisiert.
