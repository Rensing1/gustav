# Auth-Session-Bootstrap und Keycloak-Theme-Härtung

## Zusammenfassung
- Die Startseite und das Root-Layout dürfen den angemeldeten Zustand nicht mehr getrennt auflösen.
- Nach einem Snapshot-Restore muss Keycloak das lokale GUSTAV-Theme deterministisch wiederverwenden.
- Der Logout-Flow soll auch dann stabil auf eine GUSTAV-Seite führen, wenn die BFF-Session bereits fehlt.

## Umsetzung
- `frontend/src/routes/+layout.server.ts` bleibt die einzige Quelle für `bootstrap`.
- `frontend/src/routes/+page.server.ts` liest den Parent-Load und leitet nur anhand dieses bereits geladenen Zustands weiter.
- `frontend/src/lib/server/backend-auth.ts` bleibt beim Redirect-Verhalten kompatibel, wird aber durch zusätzliche Tests gegen den Mischzustand aus App-Session und fehlender BFF-Session abgesichert.
- `backend/tools/import_snapshot_backup.py` ergänzt nach dem Keycloak-Restore einen SQL-Schritt, der `loginTheme`, `accountTheme` und `emailTheme` für den Realm `gustav` wieder auf `gustav` setzt.

## Tests
- Frontend-Contract-Test: Die Root-Page darf `session-bootstrap` nicht selbst laden, sondern muss `parent()` nutzen.
- Frontend-Unit-Test: Logout bleibt auf dem GUSTAV-Success-Pfad stabil, wenn nur noch die App-Session-Cookie-Bereinigung vom Backend kommt.
- Migrationstest: Nach dem Keycloak-Restore wird zusätzlich die Theme-Lokalisierung ausgeführt.

## Annahmen
- Das gemeldete Mischbild entstand durch zwei voneinander getrennte `session-bootstrap`-Reads im selben Seitenaufbau.
- Snapshot-Restores dürfen die lokale Realm-Branding-Konfiguration nicht dauerhaft überschreiben.
