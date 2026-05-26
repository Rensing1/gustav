# Keycloak Error-Template Runtime-Härtung

## User Story

Als Nutzerin oder Nutzer möchte ich bei abgelaufenen, ungültigen oder cookie-losen Keycloak-Flows immer eine gethemte GUSTAV-Recovery-Seite sehen, damit der Wiederanmelde- oder Rückkehrpfad verständlich bleibt und nicht durch einen Keycloak-HTTP-500-Fehler verdeckt wird.

## BDD-Szenarien

- Given Keycloak rendert `error.ftl` ohne `pageRedirectUri`, When der Error-Flow ausgelöst wird, Then entsteht keine FreeMarker-`InvalidReferenceException`.
- Given Keycloak rendert `info.ftl` ohne `actionUri`, `pageRedirectUri` oder `url.loginUrl`, When ein abgekoppelter Info-Flow angezeigt wird, Then rendert das Template ohne HTTP 500.
- Given ein cookie-loser Login-Action-Request trifft Keycloak, When die Auth-Session nicht aus Cookies rekonstruiert werden kann, Then liefert Keycloak eine kontrollierte Recovery-Seite statt einer JSON-500-Antwort.
- Given ein ungültiger oder abgelaufener Action-Token wird geöffnet, When Keycloak den Fehlerpfad rendert, Then bleibt die GUSTAV-Fehlerseite stabil.
- Given ein Rücksprungziel zeigt auf den Keycloak-Account-Bereich oder auf eine externe Domain, When Recovery-Links gerendert werden, Then wird dieses Ziel nicht als primärer "Zurück zur App"-Link verwendet.

## Contract-First-Entwurf

- Kein `api/openapi.yml`-Update, weil keine GUSTAV-HTTP-API geändert wird.
- Keine Supabase/PostgreSQL-Migration, weil ausschließlich Keycloak-Theme-Dateien und Tests betroffen sind.
- Der Theme-Vertrag lautet: Error-, Info-, Expired- und Logout-Templates dürfen optionale Keycloak-Kontextwerte nie direkt dereferenzieren, ohne vorher einen sicheren Default zu setzen.

## Umsetzung

- `keycloak/themes/gustav/login/error.ftl`, `info.ftl`, `login-page-expired.ftl` und `logout-confirm.ftl` normalisieren optionale Werte mit parenthesized Defaults wie `(pageRedirectUri)!""`, `(client.baseUrl)!""`, `(actionUri)!""` und `(url.loginUrl)!""`.
- `resolve_primary_app_link(...)` wird positionsbasiert aufgerufen, weil FreeMarker-Funktionen keine Makro-ähnlichen benannten Argumente verwenden.
- `_gustav_error_components.ftl` bleibt zentrale Stelle für sichere App-Link-Auswahl und Footer-Links; Makros prüfen `url`, `realm` und `locale` defensiv.
- Recovery-Links auf Keycloak-`login-actions/*` werden in Error-Flows nicht mehr als CTA gerendert, weil sie bei cookie-losen Anfragen denselben Fehler erneut auslösen.
- `footer.ftl` wird analog gegen fehlende `realm`- und `locale`-Kontexte gehärtet, damit globale Keycloak-Fallback-Seiten dieselbe Fehlerklasse nicht erneut erzeugen.
- Keycloak läuft hinter Caddy mit expliziten `xforwarded`-Proxy-Headern; der IdP-Reverse-Proxy erzwingt für Keycloak-Set-Cookie-Antworten die GUSTAV-Cookie-Mindestattribute `Secure; SameSite=Lax`.

## Testplan

- `backend/tests/test_keycloak_theme_files.py` erhält Contract-Tests, die benannte Funktionsargumente verbieten und sichere Defaults in den betroffenen Templates verlangen.
- `backend/tests/test_compose_keycloak_postgres.py` sichert die Keycloak-Proxy-Konfiguration (`KC_PROXY_HEADERS=xforwarded`, `KC_HTTP_ENABLED=true`) und die Caddy-Cookie-Härtung statisch ab.
- `backend/tests_e2e/test_keycloak_error_pages_e2e.py` reproduziert die Produktionsfehler mit echtem Keycloak: cookie-loser `login-actions/authenticate` und ungültiger `login-actions/action-token` müssen gethemtes GUSTAV-HTML ohne HTTP 500, ohne FreeMarker-Ausgabe, ohne `login-actions`-Loop-Links und mit gehärtetem `KC_STATE_CHECKER`-Cookie liefern.
- Verifikation: `.venv/bin/pytest -q backend/tests/test_keycloak_theme_files.py backend/tests/test_compose_keycloak_postgres.py`, danach `docker compose up -d --build keycloak caddy`, danach `RUN_E2E=1 .venv/bin/pytest -q -m e2e backend/tests_e2e/test_keycloak_error_pages_e2e.py`.
