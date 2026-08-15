# E2E How‑To

Status: Stable

## Voraussetzungen
- `make up` (startet web + keycloak + caddy + h5p + worker)
- Nach `supabase db reset`: `make reset-local` (Key/Env resync + Services werden neu erstellt)
- `.env` mit korrekten `KC_BASE`/`WEB_BASE`/`KC_REALM`/`KEYCLOAK_ADMIN_PASSWORD` und docker-intern erreichbarem `SESSION_DATABASE_URL`

## Ausführen
```bash
make test-e2e
# oder manuell:
# RUN_E2E=1 E2E_VERIFY_TLS=1 REQUESTS_CA_BUNDLE=.tmp/caddy-root.crt .venv/bin/pytest -q -m e2e
```

Hinweis: `make test-e2e` führt vor Pytest automatisch `make keycloak-admin-sync` aus.
Damit werden driftende lokale Keycloak-Admin-Credentials (Snapshot/Import-Nachlauf)
auf den `.env`-Zustand zurückgeführt.

Die E2E-Suite akzeptiert keine unverschlüsselt beziehungsweise ohne Zertifikatsprüfung aufgebauten HTTPS-Verbindungen. `make test-e2e` kopiert die lokale Caddy-Root-CA nach `.tmp/caddy-root.crt` und setzt die erforderlichen TLS-Variablen. Ein manueller Lauf ohne `E2E_VERIFY_TLS=1` oder ohne nichtleeres CA-Bundle bricht vor der Testausführung mit einer Handlungsanweisung ab.

Für interaktive Prüfungen in Firefox oder Codex reicht das Python-CA-Bundle nicht aus, weil diese Browser eigene NSS-Vertrauensspeicher verwenden können. Der lokale Status und die ausdrücklich bestätigte Installation laufen über:

```bash
make local-ca-status
# Firefox und Codex vollständig schließen
make trust-local-ca
```

`make trust-local-ca` benötigt `certutil` aus dem Debian-/Ubuntu-Paket `libnss3-tools` und verwendet für den System-Trust-Store sichtbar `sudo`. Das Ziel ist idempotent und verändert ausschließlich den festen Eintrag `GUSTAV Caddy Local CA`. Nach einer Installation oder CA-Rotation müssen Firefox und Codex vollständig neu gestartet werden.

Caddy erneuert die lokalen Server- beziehungsweise Leaf-Zertifikate automatisch; GUSTAV verwendet dafür eine Laufzeit von 72 Stunden. Diese reguläre Erneuerung ändert die Root-CA nicht und benötigt daher kein erneutes `make trust-local-ca`. Erst wenn das persistente Docker-Volume `caddy_data` gelöscht oder beispielsweise durch `docker compose down -v` neu erzeugt wurde, entsteht eine neue Root-CA. Dann zeigt `make local-ca-status` den abweichenden Fingerabdruck, und nach vollständig geschlossenen Browsern ersetzt `make trust-local-ca` ausschließlich den verwalteten GUSTAV-Eintrag.

Für die visuellen Playwright-Smokes wird einmalig `make playwright-bootstrap` ausgeführt. `make test-visual-smoke` prüft den Chromium-Browser vor dem Start und meldet den Bootstrap-Befehl frühzeitig, statt erst am Ende des produktnahen Profils zu scheitern.

## Lokale Browser-Personas

Für wiederholbare manuelle Prüfungen stehen eine feste Dev-Lehrkraft und ein fester Dev-Schüler zur Verfügung. Die Zugangsdaten liegen ausschließlich in der ignorierten lokalen `.env`:

```bash
make dev-accounts
```

Der erste Lauf ergänzt fehlende `DEV_TEACHER_*`- und `DEV_STUDENT_*`-Werte, provisioniert beide Konten in Keycloak und erstellt den Kurs „GUSTAV Browser-Test“ mit der modularen Lerneinheit „Digitale Systeme untersuchen“. Ein erneuter Lauf lässt eine vollständige Landschaft unverändert. Eine noch vollständige ältere Fixture ohne Übungsmodule wird additiv erweitert; der vorhandene Lernstand bleibt dabei erhalten.

Die Fixture enthält drei Phasen, sechs verzweigte Lernmodule und zwei Übungsmodule, Markdown-, Bild- und PDF-Materialien sowie native, visuelle, Scratch-, Calliope-, Filius-, H5P- und Dialogaufgaben. Das native Übungsmodul besitzt Kriterien, Lehrkraft-Kontext und Musterlösung; das zweite Übungsmodul bindet den importierten H5P-Inhalt ein. Der Schüler besitzt eine ausgewertete Einstiegsabgabe und einen fortsetzbaren KI-Dialog; dadurch sind erledigte, offene und gesperrte Module, beide Übungsstapel sowie Diagnostikdaten gleichzeitig prüfbar.

Der Reset löscht alle Kurse und Lerneinheiten der dedizierten Dev-Lehrkraft und baut die definierte Landschaft neu auf. Andere Konten bleiben unberührt:

```bash
make reset-dev-accounts
make test-dev-accounts
```

Vor der ersten Löschung schreibt der Reset ein privates Recovery-Manifest nach `.tmp/dev-accounts-state.json`. Er übernimmt darin offene oder fehlgeschlagene Kurslöschaufträge, wartet über die eigentümergeschützte Status-API auf `completed` und entfernt das aufgezeichnete H5P-Objekt erst danach. Bei Workerfehler oder Timeout wird kein Erfolg gemeldet; der nächste Lauf kann denselben Zustand sicher fortsetzen. Manifest und `.env` haben Dateimodus `0600`.

Beide Befehle verweigern entfernte Web-, Keycloak- und Storage-Adressen. Der KI-Dienst darf entweder über Loopback oder als entfernter HTTPS-Provider wie Mistral konfiguriert sein; entfernte Klartext-HTTP-Adressen und Zugangsdaten in der URL bleiben verboten. Für entfernte HTTPS-Anbieter wird das öffentliche CA-Bundle verwendet, nicht die lokale Caddy-CA. Der Reset beginnt erst, wenn Web, Keycloak, H5P, Storage, Learning-Worker samt Lifecycle-Kommandos und das konfigurierte KI-Modell erreichbar sind. Das Browser-Smoke-Profil ist opt-in und gehört bewusst nicht zu `make verify`.

Nach einem erfolgreichen Reset gilt derselbe erwartete Lernstand: „Start und Überblick“ ist erledigt und enthält Abgabe plus formative Rückmeldung; die drei Erarbeitungsmodule sind offen; der KI-Dialog ist fortsetzbar; H5P ist noch nicht abgeschlossen; „Transferaufgabe“ und „Abschluss“ sind gesperrt. Die Diagnostik zeigt bereits die Einstiegsabgabe.

## Typische Fehler
- Health 502/Timeout → Web nicht erreichbar (Logs prüfen: `docker compose logs -n 200 web`).
- `ERR_CERT_AUTHORITY_INVALID` in Firefox/Codex → `make local-ca-status`; nur bei fehlendem oder abweichendem Root-Fingerabdruck Browser vollständig schließen, `make trust-local-ca` ausführen und Browser neu starten.
- `ERR_CERT_DATE_INVALID` trotz übereinstimmender Root-CA → Systemzeit und Gültigkeitszeitraum des Leaf-Zertifikats prüfen, Caddy und anschließend den betroffenen Browser neu starten; die TLS-Prüfung niemals abschalten.
- 500 bei `/auth/callback` → Session-DB nicht erreichbar (`SESSION_DATABASE_URL` zeigt fälschlich auf `127.0.0.1:54322` im Container).
- 401 bei `/api/me` → meist Folgefehler von `/auth/callback` (Cookie wird nicht gesetzt).
