# CLI-Token ausschließlich für Lehrkräfte

**Status:** umgesetzt
**Datum:** 20. August 2026

## Ausgangslage

Die Token-Endpunkte prüfen derzeit nur, ob eine Person angemeldet ist. Die Profilseite lädt und rendert die Tokenverwaltung ebenfalls für Schüler. Da CLI-Tokens schreibende Teaching-Scopes tragen können, muss die Rollenprüfung serverseitig erfolgen und die Oberfläche dieselbe Berechtigung widerspiegeln.

## User Story

Als Verantwortlicher für GUSTAV möchte ich, dass nur Lehrkräfte CLI-Tokens auflisten, erstellen oder widerrufen können, damit Schüler keine administrativen Zugangsdaten erzeugen und die öffentliche Oberfläche keine unzulässige Funktion anbietet.

## BDD-Szenarien und Testzuordnung

1. **Lehrkraft verwaltet eigene Tokens**
   - Given eine angemeldete Lehrkraft
   - When sie Tokens auflistet, erstellt oder widerruft
   - Then funktionieren die bestehenden Besitzer- und Geheimnisregeln unverändert
   - Nachweis: Backend-API-Integrationstest und Profil-Komponententest
2. **Schüler darf keine Tokens lesen**
   - Given ein angemeldeter Schüler
   - When er `GET /api/app/profile/cli-tokens` direkt aufruft
   - Then antwortet die API mit `403 forbidden` und liefert keine Metadaten
   - Nachweis: Backend-API-Test
3. **Schüler darf keine Tokens erstellen**
   - Given ein angemeldeter Schüler
   - When er den POST-Endpunkt direkt aufruft
   - Then antwortet die API mit `403` und der Token-Store bleibt unverändert
   - Nachweis: Backend-API-Test
4. **Schüler darf keine Tokens widerrufen**
   - Given ein angemeldeter Schüler kennt eine Token-ID
   - When er den DELETE-Endpunkt aufruft
   - Then antwortet die API mit `403`, unabhängig davon, wem die ID gehört
   - Nachweis: Backend-API-Test
5. **Schülerprofil bleibt nutzbar**
   - Given ein Schüler öffnet sein Profil
   - When die Seite geladen wird
   - Then wird der geschützte Token-Endpunkt nicht angefragt und keine CLI-Token-Oberfläche gerendert
   - Nachweis: SvelteKit-Load-Test, Komponenten-/Vertragstest und `@feature-acceptance`-Browser-Rundlauf

## API- und Datenbankentwurf

Contract-first erhalten alle drei Tokenoperationen `x-permissions: { requiredRole: teacher }` und eine dokumentierte `403`-Antwort. Das Datenbankschema und die Hash-/Besitzerlogik bleiben unverändert; eine Migration ist nicht nötig.

## Red–Green–Refactor

1. OpenAPI-Vertrag und rote Rollen-Vertragstests ergänzen.
2. Rote API-Tests für GET, POST und DELETE als Schüler schreiben.
3. Zentrale Rollenprüfung in allen drei Adaptern minimal ergänzen.
4. Rote Profiltests schreiben und Token-Load sowie Darstellung auf Lehrkräfte begrenzen.
5. Sicherheitsprüfung, gezielte Tests, authentifizierte Feature-Abnahme und `make verify-feature` ausführen.

## Umsetzung und Ergebnis

- Der OpenAPI-Vertrag weist alle drei Tokenoperationen ausdrücklich als lehrkraftgeschützt aus und dokumentiert `403 forbidden`.
- Die Backend-Routen prüfen die Lehrerrolle vor jedem Zugriff auf den Token-Store. Schüler können dadurch weder eigene noch erratene fremde Token-IDs lesen, erzeugen oder widerrufen.
- Die Profilseite fragt Tokenmetadaten nur für Lehrkräfte ab und rendert die Tokenverwaltung im Schülerprofil nicht.
- Der vorhandene Lehrkraftablauf bleibt durch seine bestehenden API- und Browsertests abgedeckt; ein neuer authentifizierter Schüler-Rundlauf prüft die fehlende Oberfläche.

## Verifikation

- Gezielte Backendtests und OpenAPI-Prüfung: 28 bestanden
- Gezielte Frontendtests: 6 bestanden
- Svelte-Diagnostik: 0 Fehler, 0 Warnungen
- Gezielte authentifizierte Browserprüfungen für Lehrkraft und Schüler: 3 bestanden
- `make verify-feature`: 2431 Backendtests bestanden, 78 übersprungen; 585 Frontendtests bestanden; 62 H5P-Tests bestanden; 22 Feature-Acceptance-Browsertests bestanden
