# Authentifizierung, Sitzungen und Cookies

Stand: 17. September 2026. Diese Referenz beschreibt die gemeinsame GUSTAV-Sitzung und ersetzt die frühere Doppelarchitektur.

## Zuständigkeit

Keycloak 26.7.3 verwaltet Passwörter, E-Mail-Verifikation, Remember-me und verbindliche Sitzungsfristen. FastAPI führt OIDC, Tokenprüfung, Sitzungsauflösung, Refresh und Abmeldung aus. SvelteKit rendert Seiten und leitet das gemeinsame Cookie bei Backend-Aufrufen weiter. Es besitzt keine OIDC-Tokens, Client-Geheimnisse oder eigene Anmeldesitzung. H5P prüft dieselbe Sitzung über FastAPI; interne, ausdrücklich authentifizierte Dienstaufrufe bleiben getrennt.

## Login und Registrierung

1. `/auth/login`, `/auth/register`, `/auth/password` und `/auth/forgot` werden durch Caddy an FastAPI geleitet. `/register` führt unmittelbar zum Registrierungsformular bei Keycloak.
2. FastAPI erzeugt State, Nonce und PKCE-Verifier. PostgreSQL speichert den Vorgang für 15 Minuten in `auth_flows`, gebunden an ein separates Browser-Cookie. State und Browserbindung werden nur als Hash gespeichert. Pro Browser bleiben höchstens drei Vorgänge erhalten.
3. Der Callback konsumiert genau einen passenden Vorgang atomar. Falsche Browserbindung, Replay, abgelaufener State und widersprüchliche Callback-Parameter werden abgelehnt.
4. FastAPI tauscht den Code mit dem PKCE-Verifier ein und prüft Signatur, Issuer, zeitliche Gültigkeit, Subject, Nonce und beide Audiences: ID-Tokens gehören zu `gustav-web`, Access-Tokens ausdrücklich zu `gustav-api`. `azp` ersetzt die Audience nicht.
5. Nach erfolgreicher Prüfung entsteht eine zufällige GUSTAV-Sitzung. Der Browser erhält ausschließlich ihren opaken Schlüssel. Ein vorhandener alter Schlüssel wird widerrufen. Rücksprungziele sind zentral geprüfte lokale Pfade mit begrenzten Queryparametern; Callback-Adressen stammen aus der Konfiguration.

Die Registrierung fragt Anzeigename, Schul-E-Mail und Passwort einmal ab. Die verbindliche Domain-Prüfung liegt in Keycloak und gilt auch bei direktem Aufruf. Der Realm-Renderer übernimmt `ALLOWED_REGISTRATION_DOMAINS` für neue Realms; bestehende Realms werden gezielt über die Admin-API aktualisiert.

Registrierung, Zurücksetzen und Passwortänderung zeigen die aktive Passwortpolicy gemeinsam vor der Eingabe: mindestens acht Zeichen, Großbuchstabe, Kleinbuchstabe, Zahl und Sonderzeichen. Es gibt keine abweichende Browservalidierung. E-Mail und Anzeigename bleiben nach Fehlern erhalten, Passwörter werden nicht erneut ausgegeben. Bestehende Konten müssen ihr Passwort nicht vorsorglich ändern.

Keycloak 26 verschiebt die Passwortanlage standardmäßig hinter die E-Mail-Verifikation. Die Flow-Konfiguration `always_set_password_on_register_form=true` erhält den vereinbarten Ein-Formular-Ablauf mit anschließender Verifikation. Diese unterstützte, upstream bereits als veraltet markierte Option muss beim nächsten Upgrade erneut geprüft werden. Der Reset verwendet `/protocol/openid-connect/forgot-credentials`; ein direkter Einstieg unter `login-actions` verliert OIDC-Kontext und ist kein unterstützter Client-Einstieg. Siehe [Keycloak-Administration](https://www.keycloak.org/docs/26.7.3/server_admin/#_registration-rc-client-flows) und [RegistrationPassword](https://github.com/keycloak/keycloak/blob/26.7.3/services/src/main/java/org/keycloak/authentication/forms/RegistrationPassword.java).

## Cookie-Vertrag

Alle folgenden Cookies sind host-only, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`.

| Cookie | Zweck | Lebensdauer |
|---|---|---|
| `gustav_session` | Einzige GUSTAV-Anmeldesitzung; zufälliger Schlüssel | Browser-Sitzungscookie, ohne `Max-Age` |
| `gustav_auth_browser` | Bindung eines OIDC-Vorgangs an den Browser | 15 Minuten |
| `gustav_auth_attempt` | Signierte Begrenzung automatischer SSO-Versuche | 60 Sekunden |
| `gustav_auth_logged_out` | Signierter Schutz vor automatischer Wiederanmeldung nach Logout | 30 Tage, bis zur ausdrücklichen Anmeldung |

Keycloak setzt seine eigenen Cookies auf dem IdP-Host. Kurs-Einladungen und andere fachliche Cookies sind keine Anmeldesitzungen. Cookie-Inhalte dürfen nicht in Logs erscheinen. HTTP-Zugriffslogs und personenbezogene Keycloak-Ereignislogs sind deaktiviert; der Proxy entfernt das Anfrageobjekt aus Fehlerlogs.

## Fristen und Remember-me

| Einstellung | Ohne Remember-me | Mit Remember-me |
|---|---:|---:|
| SSO-Inaktivität | 24 Stunden | 30 Tage |
| Maximale SSO-Laufzeit | 7 Tage | 30 Tage |
| Access-Token | 5 Minuten | 5 Minuten |
| Client-Sitzungsfristen | Von SSO geerbt | Von SSO geerbt |

Die freiwillige Checkbox ist zunächst leer. Sie eignet sich für persönliche Geräte. Die GUSTAV-Sitzung übernimmt `refresh_expires_in` aus der erfolgreichen Token-Antwort und aktualisiert ihre Gültigkeit nach jedem Refresh. Es gibt keine zusätzliche unabhängige Abmeldung nach 24 Stunden.

Nach einem Browser-Neustart fehlt das GUSTAV-Sitzungscookie. Eine persistente Keycloak-Remember-me-Sitzung kann die Anmeldung automatisch wiederherstellen. Startseite und geschützte Seiten verwenden dafür `/auth/continue` mit `prompt=none`. Ein signierter Marker erlaubt höchstens einen automatischen Versuch innerhalb von 60 Sekunden und bleibt nach dem Callback wirksam. Neue Besucher sehen nach erfolgloser Prüfung eine neutrale Anmeldung; abgelaufene Sitzungen und technische Störungen haben unterschiedliche Fehlerzustände.

## Persistenz und Refresh

`public.app_sessions` enthält den SHA-256-Hash des zufälligen Sitzungsschlüssels, Subject, Rollen, Anzeigename, ID-/Access-/Refresh-Token, Ablaufzeiten und die Refresh-Koordination. Nur serverseitige Datenbankrollen erhalten Zugriff; RLS und eingeschränkte Tabellenrechte schützen Browserrollen. Konten und Lerndaten liegen getrennt davon.

Der frameworkunabhängige `SessionService` liefert eine gültige Sitzung, keine Sitzung oder `SessionUnavailable`. Der HTTP-Adapter übersetzt die letzten beiden Ergebnisse in `401` beziehungsweise `503`. Infrastrukturfehler löschen keine wiederherstellbare Sitzung.

30 Sekunden vor Access-Token-Ablauf versucht ein Prozess, den Refresh atomar für zehn Sekunden zu reservieren. Dabei steigt eine Versionsnummer. Erst nach Abschluss dieser kurzen Transaktion erfolgt der Token-Netzaufruf mit fünf Sekunden Timeout. Nur die unveränderte Reservierung derselben Version darf das Ergebnis speichern. Eine abgelaufene Reservierung erlaubt die Übernahme durch einen anderen Prozess; solange niemand sie übernommen hat, darf ihr bisheriger Besitzer ein erfolgreich rotiertes Token noch sicher speichern. Ein spätes Ergebnis überschreibt weder neuere Tokens noch stellt es eine gelöschte Sitzung wieder her.

Parallel eintreffende Anfragen verwenden ein noch gültiges Token oder warten begrenzt auf das gemeinsame Ergebnis. Nach spätestens sechs Sekunden Wartebudget liefern sie `503`. Netzwerkfehler, `429` und `5xx` führen zu einer fünfsekündigen Wiederholungssperre. `invalid_grant` und endgültiger Ablauf führen zur Ablehnung. Ein Prozessabbruch hinterlässt höchstens die befristete Reservierung.

Ein unbekannter Signaturschlüssel löst einmalig einen erneuten JWKS-Abruf aus. Ein Ausfall dieses Abrufs ist ein Infrastrukturfehler; eine überprüfbar ungültige Signatur ist eine ungültige Anmeldung. Offensichtlich fehlerhafte JWTs werden bereits vor dem Netzaufruf abgelehnt. Rollen werden bei erfolgreichem Refresh aus den neuen verifizierten Tokens übernommen. Administrative Keycloak-Widerrufe greifen spätestens bei der nächsten Erneuerung; bis dahin gilt das begrenzte Restfenster des fünfminütigen Access-Tokens.

## Schreibzugriffe und Abmeldung

Cookie-authentifizierte Schreibzugriffe benötigen einen passenden `Origin`; nur bei fehlendem `Origin` ist ein passender `Referer` zulässig. Maßgeblich ist die konfigurierte öffentliche Callback-Origin. Fremde, fehlende oder ungültige Herkunft wird mit `403` abgelehnt. Zusätzliche fachliche CSRF-Token-Prüfungen bleiben erhalten. SvelteKit und H5P reichen die tatsächliche Browserherkunft weiter. Sie erzeugen keine vertrauenswürdigen Origin-Header für ungeprüfte Anfragen.

Ein ausdrücklich übermittelter ungültiger Bearer-Token kann nicht durch ein gültiges Cookie ersetzt werden. CLI-Tokens behalten eigene Scopes und ausschließlich dafür freigegebene Routen. Schreibzugriffe werden nach einer Wiederanmeldung niemals automatisch erneut gesendet. Lernentwürfe überstehen eine notwendige Wiederherstellung; Dateiauswahl und Übermittlung müssen bewusst erfolgen.

`GET /auth/logout` zeigt eine Bestätigung. Erst `POST /auth/logout` widerruft die lokale Sitzung und führt zunächst die Keycloak-Abmeldung serverseitig mit browsergebundenem State aus. Auch das ID-Token bleibt dabei im Backend. Nach bestätigter IdP-Antwort wird der Browser ohne Tokens zu Keycloak weitergeleitet, damit dessen Cookies entfernt und der State-Callback abgeschlossen werden. Der Logout-Marker unterbindet anschließende automatische SSO-Anmeldung. Erst eine ausdrückliche Anmeldung hebt ihn auf. Ein Ausfall beim IdP ändert die lokale Abmeldung nicht, darf aber nicht als vollständige Abmeldung bestätigt werden. `/auth/logout/callback` bestätigt nur einen passenden, einmalig konsumierten Logout-Vorgang. Eine unvollständige Abmeldung bietet eine ausdrückliche Wiederholung an. Fehlt bereits die lokale Sitzung, kann Keycloak die Abmeldung selbst bestätigen lassen.

## Konfiguration, Migration und Nachweise

Das Backend verwendet `KC_BASE_URL`, `KC_PUBLIC_BASE_URL`, `KC_REALM`, `KC_CLIENT_ID`, `REDIRECT_URI`, optional `KC_CLIENT_SECRET`, `SESSION_DATABASE_URL` und `APP_CSRF_TOKEN_SECRET`. Der Signaturschlüssel für die Marker muss mindestens 32 Zeichen lang sein. Für die Anmeldung benötigt das Frontend nur seine öffentliche `ORIGIN` und `API_INTERNAL_BASE_URL`. Der getrennte `COURSE_INVITE_INTENT_SECRET` signiert ausschließlich fachliche Einladungswünsche; er ist kein OIDC- oder Sitzungsgeheimnis. Nach einer Registrierung wird ein Kursbeitritt ausdrücklich per Formular bestätigt, niemals durch einen lesenden Seitenaufruf. Alte BFF-Sitzungsvariablen und Synchronisationsschnittstellen entfallen.

Die additive Migration erweitert `app_sessions` und legt `auth_flows` an. Alte Sitzungen ohne Tokens werden nicht übernommen; die einmalige Neuanmeldung ist beabsichtigt. Die abschließende Bereinigung der alten BFF-Tabelle erfolgt separat nach der lokalen Abnahme und Rückfallentscheidung. Supabase-Schemaänderungen erfolgen ausschließlich über Migrationen. Keycloak migriert sein eigenes Schema; nach einem Upgrade erfordert ein Rückwechsel die geprüfte Datenbanksicherung, nicht nur das alte Image. Referenz: [Upgrade-Anleitung](https://www.keycloak.org/docs/26.7.3/upgrading/).

Automatisierte Nachweise: `test_unified_auth_routes.py`, `test_unified_sessions.py`, `test_session_token_validation.py`, `test_unified_token_adapter.py`; Browser-Specs `auth-platform`, `auth-registration`, `auth-session-continuity`, `auth-unified-session` und `course-invite-registration`. Die Browserprüfung nutzt den freigegebenen lokalen Stack mit aktiver TLS-Prüfung. Der Stand der einzelnen Gates ist im [Implementierungsplan](../plan/2026-09-16-unified-auth.md) dokumentiert.
