# Direkter Keycloak-Registrierungsstart

## Ausgangslage

GUSTAV leitet `/auth/register` derzeit an den normalen OIDC-Authorization-Endpunkt mit `kc_action=register` weiter. Die eingesetzte Keycloak-Version 24.0.5 behandelt `register` jedoch nicht als gültige Application Initiated Action und zeigt deshalb zuerst die Anmeldemaske. Der Fehler betrifft sowohl Kurseinladungen als auch die allgemeine Selbstregistrierung.

## User Story

Als noch nicht registrierter Lernender möchte ich nach der Eingabe meiner zulässigen Schul-E-Mail unmittelbar das Registrierungsformular sehen, damit ich mich ohne einen irreführenden Umweg über die Anmeldemaske registrieren und anschließend einer eingeladenen Klasse beitreten kann.

## BDD-Szenarien und automatisierte Tests

1. **Direkter Registrierungsstart**
   - Given ein nicht angemeldeter, noch nicht registrierter Lernender hat eine zulässige Schul-E-Mail eingegeben
   - When er „Registrieren“ auswählt
   - Then leitet GUSTAV direkt auf den Registrierungsendpunkt der eingesetzten Keycloak-Version weiter
   - And das Keycloak-Registrierungsformular ist unmittelbar sichtbar
   - And die Anmeldemaske wird nicht als notwendiger Zwischenschritt angezeigt.
   - Tests: Redirect-Vertrag in `frontend/src/lib/server/backend-auth.test.ts` und `backend/tests/test_auth_*.py`; echter `@feature-acceptance`-Rundlauf in `frontend/e2e/course-invite-registration.spec.ts`.
2. **Kurseinladung bleibt nach Registrierung erhalten**
   - Given ein Lernender öffnet eine gültige Kurseinladung und bestätigt den Beitritt
   - When er sich registriert und seine E-Mail-Adresse verifiziert
   - Then kehrt er zu `/invite/complete` zurück
   - And wird genau einmal Kursmitglied
   - And sieht anschließend den eingeladenen Kurs.
   - Test: bestehender `@feature-acceptance`-Rundlauf ohne Login-Fallback.
3. **Sicherheitsparameter bleiben erhalten**
   - Given GUSTAV startet einen Registrierungsfluss
   - When die Weiterleitungs-URL erzeugt wird
   - Then enthält sie weiterhin `state`, `nonce`, PKCE-Challenge, Client-ID und sichere Callback-URL
   - And eine zulässige `login_hint`-Adresse wird sicher kodiert weitergereicht
   - And das erlaubte interne Rücksprungziel wird nur im signierten Flow-Cookie gespeichert.
   - Tests: TypeScript- und Python-Vertragstests für URL und Flow-Zustand.
4. **Unzulässige Registrierung**
   - Given eine fehlende oder nicht freigegebene Schul-Domain
   - When die Registrierung gestartet wird
   - Then bleibt die bestehende Ablehnung mit `400 invalid_email_domain` unverändert
   - And es wird kein Registrierungsfluss bei Keycloak begonnen.
   - Tests: bestehende Domain-Whitelist-Tests.

## API-Vertrag

`GET /auth/register` bleibt unverändert öffentlich und behält Query-Parameter, Statuscodes und Sicherheitsheader. Contract-first wird lediglich präzisiert, dass die `302`- beziehungsweise `HX-Redirect`-Antwort auf Keycloaks OIDC-Registrierungsendpunkt `/realms/{realm}/protocol/openid-connect/registrations` zeigt. `kc_action=register` entfällt. `state`, `nonce`, PKCE, `login_hint` und das sichere interne Rücksprungziel bleiben erhalten.

## Datenmodell

Keine Schemaänderung und keine Supabase/PostgreSQL-Migration sind nötig. Die Korrektur betrifft ausschließlich die Wahl des Keycloak-Endpunkts.

## Umsetzung im Red-Green-Refactor-Ablauf

1. OpenAPI-Vertrag und Dokumentation des Zielverhaltens aktualisieren.
2. Redirect-Vertragstests auf den Registrierungsendpunkt umstellen und den Acceptance-Test so verschärfen, dass er direkt das Registrierungsformular verlangt. Die Tests müssen vor der Implementierung fehlschlagen.
3. Einen kleinen, gemeinsamen URL-Builder für den Keycloak-Registrierungsendpunkt ergänzen und in der aktiven SvelteKit-Auth-Bridge verwenden.
4. Die Python-Auth-Route auf denselben Vertrag ausrichten, damit beide vorhandenen Auth-Oberflächen konsistent bleiben.
5. Veraltete Dokumentation und Test-Fallbacks für `kc_action=register` entfernen.
6. Gezielte TypeScript-, Python- und E2E-Tests ausführen.
7. Da der Ablauf nutzerseitig ist, abschließend `make verify-feature` erfolgreich ausführen.

## Nicht enthalten

- Upgrade von Keycloak
- Wechsel auf das erst in neueren Keycloak-Versionen unterstützte `prompt=create`
- Änderungen an Registrierungspolicy, Domain-Whitelist, E-Mail-Verifikation oder Kurseinlösungslogik
