# Plan: Registrierung-Domain-Whitelist auf eine Quelle der Wahrheit bringen

## Summary

- Problem: Die Self-Service-Registrierung verwendet aktuell zwei getrennte Konfigurationsquellen für dieselbe fachliche Regel.
- Die GUSTAV-App prüft optional `ALLOWED_REGISTRATION_DOMAINS`, während Keycloak im Realm-Export eine feste Regex für `@school.example` enthält.
- Dadurch kann es zu Drift zwischen App-Verhalten und IdP-Verhalten kommen. Die eigentliche Sicherheitsautorität liegt zwar bei Keycloak, aber die App kann widersprüchliche Vorab-Signale geben.
- Ziel dieses Folgelaufs ist eine eindeutige, dokumentierte Quelle der Wahrheit für erlaubte Registrierungsdomains, damit lokale Umgebung, Produktion und Realm-Import konsistent bleiben.

## Aktueller Stand

- App-/BFF-Seite:
  - `frontend/src/routes/register/+page.server.ts`
  - `frontend/src/lib/server/backend-auth.ts`
  - `backend/web/routes/auth.py`
  - Konfiguration über `ALLOWED_REGISTRATION_DOMAINS`
- IdP-Seite:
  - `keycloak/realm-gustav.json`
  - fester Regex im deklarativen User-Profile für `email`
- Wirkung:
  - App kann eine Domain akzeptieren, die Keycloak später ablehnt.
  - Oder die App lehnt früher ab, obwohl der IdP dieselbe Domain akzeptieren würde.
  - Bei direktem Aufruf der Keycloak-Registrierung ist ohnehin nur die IdP-Regel verbindlich.

## Umsetzungsvorschlag

- Primärentscheidung:
  - Keycloak bleibt die autoritative Sicherheitsregel für erlaubte Registrierungsdomains.
  - Die App darf nur eine nutzerfreundliche Vorprüfung sein, aber keine eigene abweichende Wahrheit pflegen.
- Bevorzugte Lösung:
  - Eine Quelle der Wahrheit definieren und daraus sowohl die App-Guardrail als auch die Realm-Regel ableiten.
  - Falls das kurzfristig nicht automatisiert werden kann, die freie App-Konfigurierbarkeit entfernen oder deutlich auf die feste Referenzdomain im Realm begrenzen.
- Konkrete Arbeitspakete:
  - Konfigurationsentscheidung dokumentieren: `ALLOWED_REGISTRATION_DOMAINS` bleibt synchronisierte Eingabe oder entfällt als frei konfigurierbare Regel.
  - Realm-Export und App-Doku angleichen, damit `school.example` im Repo nur noch Referenzwert und nicht stiller Gegenpol zur Env-Konfiguration ist.
  - Tests ergänzen, die Drift sichtbar machen:
    - App erlaubt Referenzdomain
    - App lehnt Fremddomain ab
    - Realm-Export enthält dieselbe Domain-Policy
    - Dokumentation beschreibt Keycloak ausdrücklich als autoritative Prüfschicht

## Testplan

- Python:
  - `backend/tests/test_auth_register_domain_whitelist.py`
  - `backend/tests/test_keycloak_realm_config.py`
- Dokumentations-/Contract-Checks:
  - Tests für `.env.example` und Referenzdokumentation, falls die Konfigurationssemantik geändert wird
- Abschluss:
  - `make verify`

## Annahmen

- Produktionsumgebungen können bereits abweichende erlaubte Domains wie `@gymalf.de` verwenden.
- Ein Realm-Neuimport darf diese produktive Policy nicht still auf `@school.example` zurücksetzen.
- Der Fix benötigt keine Datenbankmigration; betroffen sind Konfiguration, Realm-Export, Dokumentation und Tests.
