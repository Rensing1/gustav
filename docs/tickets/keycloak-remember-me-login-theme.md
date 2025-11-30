# Ticket: Keycloak „Remember me“ im GUSTAV-Login-Theme sichtbar machen

Status: offen  
Priorität: niedrig–mittel  
Betroffene Umgebung: Produktion (`gustav-lernplattform.de`)

## Kontext

- IdP: Keycloak 24.0.5, Realm `gustav`, Login-Theme `gustav`.
- Im Keycloak-Admin-Panel kann „Remember me“ aktiviert werden (längere Login-Sessions, Checkbox auf der Login-Seite).
- Das GUSTAV-Login-Theme (`keycloak/themes/gustav/login/login.ftl`) ist ein stark vereinfachtes Template, das bewusst nur E-Mail, Passwort, Login-Button sowie Links für „Passwort vergessen?“ und „Registrieren“ rendert.

## Problem

Wenn im Realm `gustav` die Option „Remember me“ aktiviert wird, erscheint auf der GUSTAV-Login-Seite trotzdem keine entsprechende Checkbox. Grund:

- Das aktuelle `login.ftl` rendert keinerlei UI für `rememberMe`. Typische Blöcke aus dem Standard-Theme fehlen, z. B.:
  - `${realm.rememberMe}`-Abfrage,
  - `<input type="checkbox" name="rememberMe">` inkl. Label.
- In den `messages_*.properties` sind keine Übersetzungen für `rememberMe` hinterlegt (weniger kritisch, da das Basis-Theme Defaults mitbringt, aber inkonsistent).

Faktisch ist das Remember-me-Feature IdP-seitig aktivierbar, aber in der GUSTAV-Oberfläche nicht sichtbar/nutzbar.

## Erwartetes Verhalten

- Wenn „Remember me“ im Realm aktiviert ist, zeigt die GUSTAV-Login-Seite eine Checkbox „Angemeldet bleiben“ (bzw. englisches Pendant) im gleichen Stil wie die übrigen Form-Elemente.
- Das Setzen der Checkbox beeinflusst die Session-Lebensdauer gemäß Keycloak-Konfiguration (Login-Timeout vs. Remember-me-Timeout).
- Ist „Remember me“ im Realm deaktiviert, wird die Checkbox nicht angezeigt.

## Hinweise für die Umsetzung

- Login-Template erweitern:
  - In `keycloak/themes/gustav/login/login.ftl` den offiziellen Block für `rememberMe` aus dem Standard-Keycloak-Theme übernehmen und an das bestehende Layout anpassen.
  - Positionierungsvorschlag:
    - Checkbox + Label unterhalb des Passwortfeldes und oberhalb des Login-Buttons oder
    - rechts/links neben dem „Passwort vergessen?“-Link, sofern das Layout das zulässt.
- Übersetzungen:
  - In `keycloak/themes/gustav/login/messages/messages_de.properties` und `messages_en.properties` geeignete Texte ergänzen, z. B.:
    - `rememberMe=Angemeldet bleiben`
    - `rememberMe=Keep me signed in`
- Technische Konsistenz:
  - Prüfen, ob GUSTAVs eigene Session-Konfiguration (App-Cookie `gustav_session`) mit längeren IdP-Sessions harmoniert; ggf. in `docs/references/user_management.md` kurz dokumentieren, wie „Remember me“ aus Sicht der App wirkt (z. B. verlängerte IdP-Session, aber App-Session-TTL bleibt unverändert).

## Akzeptanzkriterien

- Bei aktiviertem „Remember me“ im Realm:
  - zeigt die Login-Seite eine gestylte Checkbox mit passendem Label,
  - führt ein Login mit gesetzter Checkbox zu einer entsprechend länger gültigen IdP-Session.
- Bei deaktiviertem „Remember me“ im Realm:
  - erscheint keine Checkbox, das Verhalten entspricht dem aktuellen Stand.
- Theme- und ggf. Contract-Tests laufen grün; der neue Block ist in einem Snapshot-/Markup-Test abgesichert (analog zu anderen Theme-Datei-Checks).

