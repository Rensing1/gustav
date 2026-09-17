# Auth: eine Zuständigkeit und eine GUSTAV-Sitzung

Status: lokal abgeschlossen und abgenommen am 17.09.2026. Grundlage ist der am 16.09.2026 ausdrücklich freigegebene Gesamtplan. Kein Push und kein Produktionsdeployment.

## User Story

Als Schüler möchte ich mich ohne doppelte Eingaben registrieren, sämtliche Passwortanforderungen vorher kennen und zuverlässig angemeldet bleiben. Auf einem persönlichen Gerät ermöglicht die freiwillige Option „Angemeldet bleiben“ bis zu 30 Tage ohne erneute Passworteingabe.

## Architektur und Vertrag

FastAPI übernimmt OIDC, persistente browsergebundene Login-Vorgänge, die gemeinsame PostgreSQL-Sitzung und Token-Erneuerung. SvelteKit und H5P verwenden ausschließlich `gustav_session`. Sitzungsschlüssel werden gehasht gespeichert; Tokens bleiben serverseitig. Die unabhängige App-TTL entfällt zugunsten der von Keycloak bestätigten Refresh-Gültigkeit. Fehlerzustände: angemeldet, nicht angemeldet (401), vorübergehend nicht prüfbar (503). Cookie-Schreibzugriffe verlangen Origin oder Referer; CLI-Bearer bleiben getrennt. Der API-Vertrag wird zuerst angepasst.

OIDC-Vorgänge sind 15 Minuten gültig, einmalig konsumierbar und separat an den Browser gebunden (bis zu drei Vorgänge). Der Continuation-Marker begrenzt automatische Versuche für 60 Sekunden über den Callback hinaus. Explizites Abmelden unterdrückt automatische Wiederanmeldung bis zum nächsten ausdrücklich gestarteten Login.

`POST /auth/logout` widerruft die Sitzung, `GET /auth/logout` zeigt eine Bestätigung. Der Logout-Callback prüft State. Alte BFF-Session- und Session-sync-Endpunkte entfallen. Einmalige Neuanmeldung beim koordinierten Umstieg ist akzeptiert; Konten und Lerndaten bleiben erhalten.

## Etappen

1. Vertrag und fehlschlagende Regressionstests.
2. Keycloak 26.7.3 separat aktualisieren; vorher private Sicherung und Wiederherstellungsprobe. BCrypt, Profile, Templates, Proxy und persistente Sessions prüfen.
3. Registrierung direkt öffnen und alle fünf Passwortregeln aus aktiver Policy anzeigen. Domain-Prüfung bleibt verbindlich im IdP. Laufenden Realm gezielt angleichen.
4. Einheitlichen Sitzungsdienst und PostgreSQL-OIDC-Speicher per Migration implementieren. Refresh-Lease: zehn Sekunden, Versionsschutz, fünf Sekunden HTTP-Timeout, kein Netzaufruf in offener DB-Transaktion. Transiente Fehler erhalten die Sitzung.
5. Frontend, Backend, Proxy und H5P koordiniert umstellen. Entwürfe erhalten, keine automatischen Wiederholungen fachlicher Schreibzugriffe.
6. Nach Abnahme Doppelarchitektur, BFF-Tabelle und Alt-Konfiguration entfernen; Referenz aktualisieren.

## BDD und Testzuordnung

| Given – When – Then | Nachweis |
|---|---|
| Neuer Schüler – Registrierung öffnen – ein Formular und alle Regeln | auth-registration |
| Ungültige Domain/Passwort – absenden – verständliche Fehler, sichere Eingaben erhalten | auth-registration, auch ohne JavaScript |
| Kurseinladung – registrieren und E-Mail bestätigen – richtiger Kurs | course-invite-registration |
| Remember-me – Browser/Auth-Dienst neu starten – Anmeldung ohne Login-Klick | auth-session-continuity |
| Kein SSO – Continuation scheitert – begrenzter Login-Fallback | auth-session-continuity |
| Token abgelaufen – parallele Backend-Prozesse – ein koordinierter Refresh | pytest mit echter lokaler DB |
| Refresh-Ausfall/Prozessabbruch – Erholung – Sitzung erhalten, Lease läuft ab | pytest mit Zeitsteuerung |
| Logout während Refresh – verspätetes Ergebnis – Sitzung bleibt widerrufen | DB-Paralleltest und Browser |
| Ungültiger State/Browser/Nonce/Audience/Origin – Anfrage – Ablehnung | OIDC-/API-/CSRF-Tests |
| Lernaufgabe – Wiederanmeldung – Entwurf erhalten, keine doppelte Abgabe | auth-unified-session, Upload und H5P |

Zusätzlich: BCrypt-Import, Passwort-Reset, E-Mail-Verifikation, Rollenänderung bei Refresh, JWKS-Rotation und Ausfälle. Neues Browserfenster darf nur persistente Cookies übernehmen. Fristgrenzen werden mit kontrollierter Zeit getestet.

## Konfiguration und Sicherheitsgrenzen

- Passwort: mindestens acht Zeichen, Groß-/Kleinbuchstabe, Zahl, Sonderzeichen. Keine erzwungenen Änderungen vorhandener Passwörter.
- Remember-me: Idle und Maximum 30 Tage. Normal: Idle 24 Stunden, Maximum sieben Tage. Access-Token: fünf Minuten. Client-Fristen erben SSO.
- API-Audience `gustav-api`, ID-Token-Audience `gustav-web`; kein azp-only-Fallback.
- Persistente Sessions in Keycloak; keine In-Memory-Ausweichpfade bei DB-Ausfall.
- Keine Secrets, PII, Tokens, Cookies oder Auth-Queryparameter in Logs/öffentlichen Dokumenten.
- Supabase ausschließlich per Migration; Keycloak-Schema über unterstütztes Upgrade, Realm-Konfiguration gezielt per Admin-API. Ops-Unterlagen und Backups bleiben privat.

## Abnahme

Vor Browserprüfungen `make local-ca-status`. Je Spec mindestens ein echter `@feature-acceptance`-Rundlauf. Vor Abschluss und Commit: `make verify-feature FEATURE=auth-registration`, `FEATURE=auth-session-continuity`, `FEATURE=auth-unified-session`, `FEATURE=course-invite-registration` sowie `make docker-validate`. Keine historische Gesamtsuite ohne Anlass. Keycloak-Rollback benötigt DB-Sicherung, nicht nur das alte Image. Destruktive Bereinigung erst nach erfolgreicher Abnahme.

## Arbeitsnachweise

- Ausgangspunkt: sauberer master, Fast-forward-Synchronisation ohne Änderungen.
- Voruntersuchung: 33 gezielte Frontend-Tests bestanden. Transienter Refresh-503 löscht Sitzung; drei parallele Reads erzeugen drei Refreshs (beides mit unverändertem Code reproduziert).

### Konsolidierung der Auth-Tests

Die bisherigen Callback-Tests installierten einen browserungebundenen In-Memory-State und teilweise einen Callback-Stub, der ohne Tokenprüfung eine Sitzung setzte. Diese Testarchitektur entfällt mit den alten Auth-Pfaden. Ihre Sicherheitsfälle werden in `test_unified_auth_routes.py` (echte PostgreSQL-Vorgänge, Browserbindung, Replay, PKCE, sichere Rücksprungziele, Abmeldung), `test_session_token_validation.py` (echte Signaturen, Issuer, beide Audiences, Nonce, Zeitgrenzen, Rollen und Subject), `test_unified_sessions.py` (Datenbankkoordination und Ausfälle) und den Browser-Specs zusammengeführt. CLI-Berechtigungstests und fachliche API-Tests bleiben erhalten. Prüfungen, die ausdrücklich Cookie-Anmeldung am BFF verbieten oder zusätzliche Sitzungslaufzeiten voraussetzen, werden auf den neuen Vertrag umgestellt.

Die erste breite Prüfung zeigte vor allem eine Testkonfigurationsabweichung: ASGI-Testclients verwenden `http://test`, die neu verbindliche Origin-Prüfung verglich zunächst mit der produktiven Callback-Konfiguration. Die Test-Fixture benennt ihre eigene Origin nun ausdrücklich. Produktionsprüfungen bleiben unverändert streng. Nach dieser Korrektur bestanden bereits 399 der zuvor fehlgeschlagenen Tests.

Keycloak 26.7.3 verschiebt die Passworteingabe standardmäßig hinter die E-Mail-Verifikation. Die unterstützte Flow-Option `always_set_password_on_register_form=true` hält den vereinbarten Ein-Formular-Ablauf aufrecht; die E-Mail-Verifikation bleibt verpflichtend. Die Option ist upstream als veraltet gekennzeichnet und muss beim nächsten Upgrade erneut geprüft werden. Quelle: https://github.com/keycloak/keycloak/blob/26.7.3/services/src/main/java/org/keycloak/authentication/forms/RegistrationPassword.java

Bisherige lokale Abnahmen: separate Upgrade-Prüfung `auth-platform`, Registrierung ohne JavaScript einschließlich Verifikation, Remember-me mit neuem Browserprozess und ausschließlich persistenten Cookies, ausdrückliche Abmeldung, Entwurfserhalt nach Wiederherstellung und H5P-Import/Ergebnisübermittlung. Die vollständigen Gates werden nach der gemeinsamen Umstellung und Bereinigung ausgeführt; der Abschlussnachweis folgt unten.

Die Kurseinladung erhält nach der Rückkehr eine ausdrückliche Formularbestätigung. Given eine bestätigte Anmeldung und gültige Einladung, When die Bestätigungsseite geöffnet wird, Then bleibt die Mitgliedschaft unverändert; erst der herkunftsgeprüfte POST tritt dem Kurs bei. Ein 401/503 bewahrt die Einladung ohne automatische Wiederholung. Nachweis: `invite/complete/page.server.test.ts` und `course-invite-registration`. Das bisherige Frontend-Sitzungsgeheimnis wird durch einen ausschließlich für den fachlichen Einladungswunsch verwendeten Schlüssel `COURSE_INVITE_INTENT_SECRET` ersetzt.

Die echte Passwort-Reset-Prüfung zeigte, dass Keycloak Policy-Verletzungen als globalen Formularfehler liefert. Die Passwortformulare ordnen auch diesen Fall barrierefrei dem neuen Passwort zu (Browser-Regressionsnachweis). Grundlage: [UpdatePassword 26.7.3](https://github.com/keycloak/keycloak/blob/26.7.3/services/src/main/java/org/keycloak/authentication/requiredactions/UpdatePassword.java).

### Rückfallentscheidung und Bereinigung am 17.09.2026

Alle fünf gezielten Browser-Specs sind mit echter lokaler Datenhaltung erfolgreich: `auth-platform`, `auth-registration`, `course-invite-registration`, `auth-session-continuity` und `auth-unified-session`. Remember-me wurde mit einem neuen Browserprozess ohne Übernahme des Sitzungscookies und mit echten Neustarts beider Auth-Dienste geprüft. Die unabhängige Keycloak-Abnahme und geprüfte private Wiederherstellungssicherung liegen vor. Entscheidung für den freigegebenen lokalen Stack: Die gemeinsame Architektur bleibt aktiv; die alte zweite Sitzung wird nicht wieder eingeführt. Vor ihrer eigenen Bereinigungsmigration wird zusätzlich eine private Sicherung der alten GUSTAV-Sitzungstabellen abgelegt. Konten und Lerndaten sind nicht Bestandteil dieser Bereinigung. Die abschließenden `verify-feature`-Gates folgen auf dem bereinigten Schema.

Der Produktverantwortliche hat am 17.09.2026 klargestellt, dass ausschließlich Keycloak verwendet wird und kein externer Anmeldeanbieter existiert. Der im übernommenen Plan erwähnte Broker-Rundlauf entfällt daher ausdrücklich. Die reguläre Keycloak-Anmeldung und übernommene BCrypt-Passwörter werden durch `auth-platform` geprüft.

### Tokens bleiben auch beim Abmelden im Backend

Die Standard-RP-Weiterleitung mit `id_token_hint` würde ein ID-Token an den Browser ausgeben und damit der vereinbarten Grenze widersprechen. FastAPI führt deshalb zuerst den OIDC-Abmeldeaufruf mit diesem Hinweis im POST-Formularbody serverseitig aus und prüft dessen bestätigte Rückleitung. Der Browser erhält anschließend ausschließlich `client_id`, Rücksprungadresse und State, damit Keycloak seine Cookies selbst entfernen kann. Ein Ausfall beendet weiterhin die lokale Sitzung, zeigt aber keine vollständige Abmeldung an; die Fehlerseite bietet eine ausdrückliche Wiederholung an. Ohne gespeicherte GUSTAV-Sitzung kann Keycloak selbst eine Abmeldebestätigung verlangen. Given ein abgemeldeter lokaler Benutzer und ein nicht erreichbarer IdP, When die Seite angezeigt wird, Then steht dort nur die lokale Abmeldung und ein sicherer erneuter Versuch. Nachweise: OIDC-Adapter-/Routentests und `auth-session-continuity`; normaler vollständiger Logout zusätzlich in `auth-platform`. Grundlage: [Keycloak LogoutEndpoint 26.7.3](https://github.com/keycloak/keycloak/blob/26.7.3/services/src/main/java/org/keycloak/protocol/oidc/endpoints/LogoutEndpoint.java).

Der Ausfall-Rundlauf deckt auch die erneute Abmeldung über die Fehlerseite ab. Auth-Aktionslinks laden das Zieldokument vollständig, damit dessen Herkunftsrichtlinie für native POST-Formulare wirksam wird. Eine reine SPA-Navigation würde die `no-referrer`-Richtlinie der Fehlerseite behalten und den berechtigten Versuch als `Origin: null` ablehnen. Der Schutz gegen fremde oder fehlende Herkunft bleibt unverändert. Nachweise: `AuthFrame.test.ts` (zuerst rot) und der echte Ausfall-/Wiederholungsablauf.

Die echte Keycloak-Abmeldebestätigung benötigt zusätzlich `session_code=${logoutConfirm.code}` im Formular. Dieses versteckte Feld fehlte in der bisherigen eigenen Vorlage. Der Ausfall-/Wiederholungs-Browsertest und ein gezielter Theme-Vertragstest reproduzieren die Ablehnung vor der Korrektur. Die Vorlage übernimmt nun das Feld entsprechend dem [Keycloak-26.7.3-Original](https://github.com/keycloak/keycloak/blob/26.7.3/themes/src/main/resources/theme/base/login/logout-confirm.ftl).

Die benannten Wartungsgates `test-db-security` und `harness-minimum` werden auf die konsolidierten Auth-Tests umgestellt. Ein neuer Vertragstest prüft für sämtliche expliziten Testpfade im Makefile, dass die Datei tatsächlich existiert; er findet zunächst vier veraltete Verweise. So bleiben die gezielten Prüfkommandos auch nach Entfernen der Doppelarchitektur verwendbar.

## Abschlussnachweise

Die unabhängige Upgrade-Abnahme, Wiederherstellungsprobe und Rückfallentscheidung sind abgeschlossen. Beide Supabase-Migrationen sind lokal angewandt; `bff_sessions` und alte tokenlose GUSTAV-Sitzungen sind entfernt. Konten und Lerndaten bleiben erhalten. Produktionsdeployment und Push sind nicht Bestandteil dieses Auftrags.

| Prüfung | Stand |
|---|---|
| `make verify-feature FEATURE=auth-registration` | Bestanden: 2.989 Backend-Tests, 732 Frontend-Tests, H5P, Build und Browser-Rundlauf |
| `make verify-feature FEATURE=auth-unified-session` | Bestanden: gleiche Basisprüfung, echter Entwurf-/Upload-/H5P-Rundlauf |
| `make verify-feature FEATURE=auth-session-continuity` | Nach letzter Logout-Korrektur bestanden: 2.997 Backend-Tests, 735 Frontend-Tests, H5P, Build und Browser-Rundlauf |
| `make verify-feature FEATURE=course-invite-registration` | Bestanden: 2.998 Backend-Tests, 735 Frontend-Tests, H5P, Build und Browser-Rundlauf |
| `make verify-feature FEATURE=auth-platform` | Bestanden: 2.998 Backend-Tests, 735 Frontend-Tests, H5P, Build, normale Anmeldung, vollständiger Logout und BCrypt-Import |
| `make docker-validate` | Bestanden |

33 optionale Tests der allgemeinen Backend-Suite sind übersprungen; die geforderten Auth- und PostgreSQL-Regressionsnachweise wurden ausgeführt. Die abschließenden Logout-Korrekturen betreffen außerdem den gemeinsamen Auth-Rahmen und eine Keycloak-Vorlage. Deshalb wurden die bereits vollständig abgenommenen Registrierungs- und Lernabläufe abschließend nochmals als echte Browser-Rundläufe auf dem letzten Stand geprüft: `auth-registration` und `auth-unified-session` sind erneut bestanden. Die TLS-Vertrauensprüfung war vor den Browserläufen erfolgreich; die Zertifikatsprüfung blieb aktiv. Sämtliche laufbezogenen Testkonten und Testdaten wurden anschließend erfolgreich bereinigt.

Die Auth-Referenz, Architektur, Konfiguration und Testinventare beschreiben die gemeinsame Architektur. Die zweite Sitzungsverwaltung, TypeScript-OIDC-Implementierung, Synchronisationswege und zugehörigen Tabellen und Einstellungen sind entfernt. Die 30-Tage-Fristen sind mit kontrollierter Zeit geprüft; der Browser-Rundlauf weist echte Neustarts und fortgesetztes SSO nach, keine 30-tägige Echtzeitbeobachtung.
