# Plan: Teaching DSN Hardening & Auth Contract Updates

## Kontext
- Review ergab Sicherheitslücke: `backend/teaching/repo_db.py` fällt auch in Produktions-Umgebungen auf den bekannten Dev-DSN (`gustav_limited`) zurück.
- OpenAPI dokumentiert keine `429`-Antworten für Auth-Redirects, obwohl Rate-Limits aktiv sind; CSRF-Hinweise stehen teilweise an GET-Endpoints ohne Write-Operation.
- Dokumentation und `.env.example` sollen konsequent auf neue Login-Rollen und Dummy-Secrets verweisen.

## Ziele
1. DSN-Resolver im Teaching-Repo in Prod/Stage ohne explizite DSN scheitern lassen (kein Dev-Fallback).
2. OpenAPI-Vertrag aktualisieren:
   - `429`-Antworten und `Retry-After` für `/auth/login` & `/auth/forgot`.
   - `Vary: Origin` für CSRF-geschützte POST/PATCH-Endpoints.
   - CSRF-Hinweise nur bei Write-Operationen.
3. Tests ergänzen, die die neuen Vertrags- und Sicherheitsanforderungen abdecken.
4. `.env.example` und Referenz-Dokumente anpassen (Login-Rolle, Supabase-Hinweise).

## Deliverables
- Aktualisierte Python- und SQL-Dateien (nur wo notwendig).
- Erweiterte pytest-Suites (`test_openapi_*.py`, `test_teaching_repo_*`).
- Dokumentations-Updates (ENV-Beispiele, Security-Referenzen).

## Offene Fragen
- Keine; Umsetzung folgt bestehender Security-Governance.

