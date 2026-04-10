# 2026-04-06 - Profilseite im Kontomenü

Status: abgeschlossen

## Zusammenfassung

- Neue gemeinsame Route `/profile` im Namensmenü für Schüler und Lehrkräfte.
- Profil umfasst `Anzeigename`, `Vorname`, `Nachname`, schreibgeschützte
  `E-Mail` und eine Passwort-Aktion.
- `Vorname` und `Nachname` werden initial aus dem Login-Identifier abgeleitet,
  sind danach korrigierbar und nach der ersten Speicherung für 180 Tage
  gesperrt.
- Lehrkraftansichten bevorzugen künftig `Vorname + Nachname`; der bisherige
  robuste Login-/E-Mail-Fallback bleibt erhalten.

## Contract-First

- `api/openapi.yml` wird erweitert um:
  - `GET /api/app/profile`
  - `PATCH /api/app/profile/display-name`
  - `PATCH /api/app/profile/name`
  - `GET /auth/password`
- Neue Schemas:
  - `AppProfileView`
  - `ProfileDisplayNameUpdate`
  - `ProfileNameUpdate`

## BDD-Szenarien

1. Given ein authentifizierter Nutzer, when `/profile` geladen wird, then sieht
   er Anzeigename, Vorname, Nachname, E-Mail und eine Passwort-Aktion.
2. Given `firstName` und `lastName` fehlen, when das Profil geladen wird, then
   werden aus E-Mail/Login abgeleitete Vorschlagswerte angezeigt.
3. Given ein neuer Anzeigename, when gespeichert wird, then wird
   `display_name` aktualisiert und die Shell zeigt nach Redirect den neuen
   Namen.
4. Given Vor- und Nachname wurden noch nie bewusst gespeichert, when sie
   gespeichert werden, then werden sie übernommen und eine 180-Tage-Sperre
   gesetzt.
5. Given die Sperre ist aktiv, when Vor- und Nachname erneut gespeichert
   werden, then lehnt der Server die Änderung mit einem klaren Fehler ab.
6. Given eine Lehrkraft sieht einen Lernenden, when Vor- und Nachname gepflegt
   sind, then werden diese statt des Anzeigenamens angezeigt.
7. Given eine Passwortänderung wird gestartet, when `/auth/password` geöffnet
   wird, then erfolgt ein Redirect in den Keycloak-Flow mit
   `kc_action=UPDATE_PASSWORD`.

## Tests

- OpenAPI-Contract-Tests für Profil- und Passwort-Endpunkte
- API-Tests für Profil-Readmodel, Display-Name-Update und Namenssperre
- Auth-Test für `/auth/password`
- SvelteKit-Vertragstest für Route `/profile` und Menülink
- Frontend-Komponententests für die Profilseite

## Annahmen

- Keine Supabase-Migration; die Sperrinformation lebt als Keycloak-Attribut.
- `display_name` bleibt der persönliche Produktname.
- `Vorname` und `Nachname` werden intern und in der UI genau so benannt.
