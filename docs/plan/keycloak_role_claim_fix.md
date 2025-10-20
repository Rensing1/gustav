# Keycloak Role Claim Fix – Implementation Plan

## Kontext
- Felix meldet, dass nach dem Legacy-Import der Rollen in Keycloak zwar korrekt gesetzt sind (`teacher` für `hennecke@gymalf.de`), die Web-App in der Sidebar aber weiterhin „Schüler“ anzeigt.
- Die Analyse zeigt: Unser Backend liest Rollen ausschließlich aus dem `realm_access.roles` Claim des **ID-Tokens** (`backend/web/main.py:708 ff.`). Weil der Client Scope `roles` in Keycloak diese Information nur ins **Access-Token** schreibt, landet in der Session (`app_sessions.roles`) der Fallback `["student"]`.

## Problemstellung
- Rollen fehlen im ID-Token → falsche Rollenerkennung in GUSTAV.
- Folge: Lehrer*innen sehen die Anwendung mit Schülerrechten, potenziell falsche Navigation oder Berechtigungen.

## Zielsetzung
1. Keycloak soll beim Login den Claim `realm_access.roles` auch im ID-Token bereitstellen.
2. Backend soll unverändert bleiben und sofort die korrekten Rollen (`teacher`, `student`, `admin`) erkennen.
3. Regressionen vermeiden: Bestehende Token-Claims (z.B. `gustav_display_name`) bleiben stabil.

## Nicht-Ziele
- Keine Änderungen am Backend-Rollen-Mapping oder an der Session-Logik.
- Keine Umstellung auf Access-Token-Auswertung.
- Kein Wechsel der Password- oder Importlogik.

## Lösungsidee
1. **Keycloak-Config erweitern**
   - Im Realm Scope `roles` (Client Scope ID `f5d7de15-084b-433c-9d1c-58767838aec0`) den Mapper „realm roles“ so anpassen, dass `id.token.claim = true`.
   - Alternativ (falls `roles` für andere Clients unverändert bleiben soll) einen dedizierten Client Scope für `gustav-web` anlegen, der denselben Mapper besitzt und `id.token.claim=true`.
   - Realm-JSON (`keycloak/realm-gustav.json`) aktualisieren, damit `start-dev --import-realm` dieselbe Konfiguration erzeugt.

2. **Skripte/Importer prüfen**
   - Sicherstellen, dass `backend/tools/legacy_user_import.py` keine zusätzlichen Anpassungen braucht (nur zur Einordnung im Plan).

3. **Tests**
   - Auf Anwendungsebene einen `pytest`-Test, der ein exemplarisches ID-Token mit `teacher`-Rolle simuliert und prüft, dass `/api/me` diese Rolle durchreicht (ggf. bestehende Tests erweitern).
   - E2E/Integration: Falls möglich, bestehenden `backend/tests_e2e/test_identity_login_register_logout_e2e.py` erweitern, damit er nach dem Login `realm_access.roles` im ID-Token erwartet.

4. **Verifikation**
   - Nach Anwendung der Realm-Änderung: manueller Login mit `hennecke@gymalf.de`, anschließend `/api/me` prüfen (Rollenausgabe).
   - DB-Prüfung `SELECT roles FROM public.app_sessions WHERE name='hennecke'` → Erwartung `["teacher"]`.

## Abhängigkeiten / Risiken
- Änderungen an `realm-gustav.json` müssen mit Keycloak-Neustart importiert werden (`--import-realm` auf frischer Datenbank oder manuelle Anpassung via Admin-Konsole).
- Vorsicht bei bestehender produktiver Instanz: Realm-Import überschreibt ggf. andere Anpassungen; der Plan berücksichtigt DEV-Umgebung.

## Zeitplan grob
1. Config-Änderung vorbereiten (30 min).
2. Tests anpassen/schreiben (45 min).
3. Manuelle Verifikation + Dokumentation (30 min).

