# Ticket: Keycloak Error-/Info-Templates werfen 500 bei fehlendem `pageRedirectUri`

Status: offen  
Prioritaet: hoch  
Betroffene Umgebung: Produktion (`app.school.example`, `id.school.example`)  
Erstellt am: 22. Maerz 2026

## Kurzfassung

Die seit laengerer Zeit beobachteten Probleme bei Anmeldung, Registrierung, Verifizierung und Passwort-Reset sind im aktuellen Produktionsstand nicht nur UX-/Redirect-Themen, sondern enthalten einen konkreten Laufzeitfehler im ausgerollten Keycloak-Theme:

- In mehreren Error-/Expired-/Info-Pfaden bricht das Rendering der GUSTAV-Keycloak-Templates mit einer FreeMarker-Exception ab.
- Sichtbare Folge fuer Nutzer sind echte Keycloak-`500`-Seiten bzw. kaputt wirkende Fehlerseiten statt sauberer GUSTAV-Recovery-Seiten.
- Parallel bleibt mindestens ein Required-Action-/Reset-Pfad bestehen, der auf ein unpassendes IdP-Ziel (`.../realms/gustav/account/`) zurueckfaellt.

Das Problem besteht damit weiterhin, aber in einer praeziseren Form als in den frueheren Tickets: Nicht nur fehlende Templates oder ungehardete Backlinks, sondern ein Null-/Missing-Context-Bug in den inzwischen vorhandenen Templates selbst.

## Kontext / Vorgeschichte

Verwandte abgeschlossene Tickets / Plaene:

- `docs/tickets/keycloak-registration-verify-email-pages-fallback-with-language-overlay-2026-02-10.md`
- `docs/tickets/keycloak-registration-verify-intermittent-language-overlay.md`
- `docs/tickets/keycloak-password-reset-page-not-themed.md`
- `docs/tickets/keycloak-registration-error-backlink-hardening-2026-03-05.md`
- `docs/plan/2026-02-23-keycloak-error-pages-themed.md`
- `docs/plan/2026-03-05-keycloak-backlink-hardening.md`

Diese Aenderungen haben den Theme-Stand erweitert (`error.ftl`, `login-page-expired.ftl`, `info.ftl`, gemeinsamer Resolver fuer Ruecksprungziele), aber die jetzige Analyse zeigt, dass genau diese Haertung in bestimmten Keycloak-Kontexten selbst abstuerzt.

## Beobachtetes Nutzerbild

Aus der aktuellen Rueckmeldung und den Laufzeitdaten ergeben sich konsistente Symptome:

- Anmeldung/Registrierung/Passwort-Reset liefern gelegentlich Fehlercodes.
- Nutzer landen auf seltsamen oder kaputt wirkenden Seiten statt auf einer sauberen GUSTAV-Recovery-Seite.
- Im Reset-/Required-Action-Umfeld treten unpassende Ruecksprungziele in den IdP-Bereich auf.

## Technische Ursache

Der gemeinsame Resolver in
`keycloak/themes/gustav/login/_gustav_error_components.ftl`
ist nicht robust gegen fehlendes `pageRedirectUri`.

Betroffene Stellen:

- `keycloak/themes/gustav/login/_gustav_error_components.ftl`
- `keycloak/themes/gustav/login/error.ftl`
- `keycloak/themes/gustav/login/login-page-expired.ftl`
- `keycloak/themes/gustav/login/info.ftl`

Der Resolver wird in den Templates mit einem Default (`pageRedirectUri=(pageRedirectUri!"")`) aufgerufen, scheitert aber zur Laufzeit dennoch in Keycloak-Fehlerpfaden mit:

- `InvalidReferenceException: The following has evaluated to null or missing: pageRedirectUri`

Dadurch entstehen echte Serverfehler waehrend des Renderns von:

- `error.ftl`
- `login-page-expired.ftl`
- `info.ftl`

## Produktions-Evidenz (sanitiert)

Zeitraum der Auswertung: **15. Maerz 2026 bis 22. Maerz 2026**

### 1) Template-Fehler im laufenden Keycloak

Im Zeitraum wurden in den Keycloak-Logs gezaehlt:

- `437` fehlgeschlagene Renderings von `error.ftl`
- `4` fehlgeschlagene Renderings von `login-page-expired.ftl`
- `2` fehlgeschlagene Renderings von `info.ftl`

Die zugehoerigen FreeMarker-Fehler referenzieren wiederholt:

- `pageRedirectUri [in template "error.ftl"]`
- `pageRedirectUri [in template "login-page-expired.ftl"]`
- `pageRedirectUri [in template "info.ftl"]`

### 2) Sichtbare HTTP-500-Auswirkungen am IdP

Im selben Zeitraum wurden fuer `id.school.example` **209 HTTP-500-Antworten** beobachtet.

Hauefig betroffene Pfade:

- `/realms/gustav/login-actions/registration` (`124x`)
- `/realms/gustav/login-actions/authenticate` (`70x`)
- `/realms/gustav/protocol/openid-connect/auth` (`6x`)
- `/realms/gustav/login-actions/action-token` (`5x`)
- `/realms/gustav/login-actions/required-action` (`4x`)

Interpretation:

- Das Problem betrifft nicht nur einen exotischen Sonderfall, sondern vor allem Login-/Registrierungs-Fehlerpfade.
- Verify-/Reset-/Required-Action-Pfade sind in kleinerer, aber relevanter Zahl ebenfalls betroffen.

### 3) Konkreter Reset-/Required-Action-Vorfall am 19. Maerz 2026

Fuer einen echten Passwort-Reset-Vorfall am **19. Maerz 2026** zeigt die Korrelation aus Access- und Keycloak-Logs:

- zuerst mehrere `RESET_PASSWORD_ERROR user_not_found`
- danach `UPDATE_PASSWORD_ERROR password_confirm_error`
- anschliessend `EXECUTE_ACTION_TOKEN_ERROR expired_code`
- dazwischen echte `500`-Antworten auf Keycloak-Endpunkte im `authenticate`-/`required-action`-Pfad

Zusatzbefund:

- Bei `UPDATE_PASSWORD_ERROR` wurde als `redirect_uri` ein IdP-Kontoziel protokolliert:
  - `https://id.school.example/realms/gustav/account/`

Das passt sowohl zu den beobachteten Fehlermeldungen als auch zur Wahrnehmung von unpassenden Rueckwegen.

## Abgrenzung zu anderen Fehlerbildern

### Nicht der primaere Schwerpunkt

- App-seitige `/auth/callback`-Fehler existieren, sind aber deutlich seltener.
- Im betrachteten Zeitraum wurden **13** `400 Bad Request` auf `/auth/callback` beobachtet.

### Weiterhin relevant, aber nicht die Hauptursache dieses Tickets

- `cookie_not_found` tritt in Keycloak weiterhin haeufig auf und erklaert einen Teil der historischen Incident-Wahrnehmung.
- Fuer dieses Ticket ist jedoch entscheidend:
  - Die aktuelle Produktionsinstanz scheitert zusaetzlich an eigenen Theme-Templates und erzeugt dadurch selbst `500`-Antworten.

## Warum die vorhandenen Tests das nicht erkannt haben

Die bestehende Testabdeckung (`backend/tests/test_keycloak_theme_files.py`) prueft vor allem:

- Dateivorhandensein
- statische Marker/Hooks
- String-Kontrakte fuer Resolver-Logik

Was aktuell fehlt:

- ein Render-/Negativtest fuer `error.ftl`, `login-page-expired.ftl` und `info.ftl` mit fehlendem oder nulligem `pageRedirectUri`
- ein Test fuer echte Keycloak-Kontextvarianten in Error-/Required-Action-Pfaden

Folge:

- Der Stand konnte testseitig “gruen” sein, obwohl er in Produktion in bestimmten Kontexten `500` wirft.

## Wahrscheinliche Folgeursachen / offene technische Fragen

1. **Template-Robustheit**
- Der Resolver oder die Aufrufweise muss so geaendert werden, dass fehlende Keycloak-Context-Variablen niemals zu einer FreeMarker-Exception fuehren.

2. **Ruecksprungziel fuer Required Actions / Reset**
- Im `UPDATE_PASSWORD_ERROR`-Pfad taucht weiterhin `.../realms/gustav/account/` als `redirect_uri` auf.
- Es ist zu pruefen, ob der laufende `gustav-web`-Client im Realm fuer diese Flows kein hinreichend sauberes App-Ziel vorgibt oder ob Keycloak hier intern auf ein ungeeignetes Default-Ziel faellt.

3. **Cookie-/Scanner-/Token-Edge-Cases**
- `cookie_not_found` und `expired_code` bleiben parallel bestehen.
- Diese Edge-Cases sollten nach dem Template-Fix getrennt von den jetzigen `500`-Crashes bewertet werden.

## Erwartetes Verhalten

- Kein Error-/Expired-/Info-Pfad im Keycloak-Theme darf bei fehlendem `pageRedirectUri` mit `500` abbrechen.
- Stattdessen muessen immer robuste, gethemte Recovery-Seiten gerendert werden.
- Ruecksprung-CTAs im Reset-/Verify-/Required-Action-Umfeld sollen bevorzugt zur App fuehren, nicht auf ein unhelpfules IdP-Kontoziel.

## Gewuenschte Umsetzung

1. **Theme-Hotfix**
- Resolver in `_gustav_error_components.ftl` null-/missing-sicher machen.
- `error.ftl`, `login-page-expired.ftl` und `info.ftl` gegen fehlende Kontextvariablen absichern.

2. **Tests erweitern**
- Render-/Kontexttests fuer fehlendes `pageRedirectUri`
- Negativtests fuer Error-/Expired-/Info-Pfade

3. **Realm-/Client-Pruefung**
- Laufende Client-Konfiguration fuer Required-Action-/Reset-Ruecksprungziele pruefen
- sicherstellen, dass App-Ziele bevorzugt werden und `id.../account/` nicht als nutzerfuehrender Standardpfad uebrig bleibt

## Akzeptanzkriterien

- Keine Keycloak-`500` mehr durch `error.ftl`, `login-page-expired.ftl` oder `info.ftl`, wenn `pageRedirectUri` fehlt.
- Error-/Expired-/Info-Seiten bleiben im GUSTAV-Look und liefern klare Recovery-Links.
- Passwort-Reset-/Required-Action-Fehler fuehren nicht auf ein unpassendes IdP-Kontoziel als primaeren Rueckweg.
- Tests decken den fehlenden `pageRedirectUri`-Kontext explizit ab.
