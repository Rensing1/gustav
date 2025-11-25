# GUSTAV auf einem neuen Linux-System deployen

Status: Draft (Stand 2025-02)  
Zielgruppe: Lehrkräfte oder IT-Admins ohne tiefes DevOps-Wissen

Die folgenden Schritte bringen eine frische Linux-Installation (z. B. Ubuntu 22.04 LTS) zum Laufen. Das Setup entspricht exakt der Produktionsumgebung: Supabase (Postgres + Storage), GUSTAV (FastAPI + Keycloak + Learning Worker) und – optional – der lokale KI-Dienst Ollama.

---

## Voraussetzungen (Hardware & Netzwerk)

- **Hardware**: mind. 4 vCPU, 8 GB RAM und 40 GB SSD. Für produktive Klassenstufen empfehlen wir 8 vCPU, 16 GB RAM und 100 GB SSD (wegen Supabase-Storage, Ollama-Modellen und Logfiles).  
- **Netz**: stabile symmetrische Verbindung mit ≥20 Mbit/s Upload (Datei-Uploads/Feedback).  
- **Ports (extern)**: 22/TCP für SSH, 80/443 für Caddy (HTTP→HTTPS, Let’s Encrypt), optional 11434 falls Ollama extern erreichbar sein soll. Interne Supabase-Ports bleiben nur lokal sichtbar.  
- **DNS**: zwei FQDNs, z. B. `gustav.schule.de` (App) und `id.gustav.schule.de` (Keycloak).

---

## 1. System vorbereiten

1. **Pakete aktualisieren**  
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
   Warum: Sicherheitsupdates und aktuelle Kernel.

2. **Basis-Tools installieren** (`git`, Docker Engine, Docker Compose Plugin, `curl`, `ufw`)  
   ```bash
   sudo apt install -y git docker.io docker-compose-plugin curl ufw
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER   # einmal ab- und wieder anmelden
   ```

3. **Supabase CLI installieren**  
   ```bash
   curl -fsSL https://cli.supabase.com/install/linux | sh
   echo 'export PATH="$HOME/.supabase/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   supabase --version
   ```
   (Alternativ: Paketmanager deiner Distribution konsultieren.)

4. **Optionale Hilfsprogramme**  
   - `make` (für vorbereitete Shortcuts): `sudo apt install -y make`  
   - Python venv, falls Tests lokal laufen sollen: `sudo apt install -y python3.11-venv`

---

## 2. Repository klonen und vorbereiten

1. **Projektcode holen**  
   ```bash
   git clone <REPO_URL> gustav-alpha2
   cd gustav-alpha2
   ```
   `<REPO_URL>` durch den echten HTTPS- oder SSH-Link ersetzen.

2. **Umgebungsdatei erstellen**  
   ```bash
   cp .env.example .env
   ```
   Danach `.env` editieren und sichere Werte setzen. Für produktive Deployments sind folgende Einträge verpflichtend, weil sonst die Sicherheits-Guards beim Start abbrechen (`backend/web/config.py`):
   - `GUSTAV_ENV=prod`, `REQUIRE_STORAGE_VERIFY=true`, `ENABLE_STORAGE_UPLOAD_PROXY=false`, `ENABLE_DEV_UPLOAD_STUB=false`, `AUTO_CREATE_STORAGE_BUCKETS=false`.
   - `APP_DB_PASSWORD`, `KC_ADMIN_CLIENT_SECRET`, `KC_DB_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`.
   - Öffentlich erreichbare URLs: `WEB_BASE`, `REDIRECT_URI`, `KC_BASE_URL`, `KC_PUBLIC_BASE_URL` **und** die Keycloak-spezifischen Hostnames aus dem Compose-File (`KC_HOSTNAME_URL`, `KC_HOSTNAME_ADMIN_URL`). Alle vier Werte müssen auf die endgültigen HTTPS-FQDNs zeigen, sonst funktionieren OIDC-Redirects nicht.
   - Supabase-Credentials: `SUPABASE_URL` kommt aus `supabase status`, der `SUPABASE_SERVICE_ROLE_KEY` darf **nie** auf `DUMMY_DO_NOT_USE` verbleiben. Sobald der Supabase-Stack läuft (Abschnitt 3), Werte mit `make supabase-sync-env` oder `scripts/sync_supabase_env.py` in `.env` schreiben und anschließend den Dummy manuell ersetzen.
   - Falls Ollama/AI geplant: `AI_BACKEND` auf ein reales Backend setzen (`local` oder `remote`), niemals `stub`. Modelle: `AI_FEEDBACK_MODEL`, `AI_VISION_MODEL`, Timeouts etc.

3. **Uploads-Verzeichnis anlegen (für Vision-Worker)**  
   ```bash
   mkdir -p .tmp/dev_uploads
   ```

4. **Hostname-Anpassungen planen**  
   - `reverse-proxy/Caddyfile`: Domains `app.localhost` und `id.localhost` durch die echten FQDNs ersetzen.  
   - DNS/A-Records der Schule auf die Server-IP legen (z. B. `gustav.schule.de` → App, `id.gustav.schule.de` → Keycloak). Für Tests ohne öffentliche Domains können weiterhin `*.localhost`-Einträge genutzt werden.
   - `docker-compose.yml`: Stelle sicher, dass `caddy` Ports `80:80` **und** `443:443` mapped (Standard seit 2025). Nur für rein lokale Tests darfst du das Mapping auf `8100:80` zurückdrehen; produktive Zertifikate von Let’s Encrypt gehen nur bei offenem Port 80/443.
   - **Keycloak-Redirects aktualisieren**: Die ausgelieferte Realm-Datei `keycloak/realm-gustav.json` erlaubt ausschließlich `https://localhost/*`. Passe vor dem ersten Start entweder diese Datei an oder konfiguriere nach dem Import über die Keycloak-Admin-Konsole (`Clients → gustav-web → Settings`). Hinterlege dort die endgültigen Werte aus `WEB_BASE` unter `Valid Redirect URIs` **und** `Web Origins` (z. B. `https://gustav.schule.de/*`). Erst wenn die Domains eingetragen sind, akzeptiert Keycloak den OIDC-Redirect und der Login funktioniert auf PROD.
   - Beispiel für eine echte Caddy-Konfiguration (`reverse-proxy/Caddyfile`):
     ```caddy
     gustav.schule.de {
       reverse_proxy gustav-alpha2:8000
     }

     id.gustav.schule.de {
       reverse_proxy keycloak:8080
     }
     ```
     Caddy erledigt Zertifikate automatisch, sobald die Domains auf den Server zeigen und Ports 80/443 offen sind.

---

## 3. Supabase-Stack starten

1. **Supabase-Dienste hochfahren**  
   ```bash
   supabase start
   supabase status
   ```
   Läuft alles, zeigt `supabase status` bei API, DB, Storage und Studio „RUNNING“. Der Befehl erstellt automatisch das Docker-Netz `supabase_network_gustav-alpha2`, das GUSTAV später nutzt.

2. **Supabase-Credentials in `.env` spiegeln**  
   ```bash
   make supabase-sync-env
   # Alternativ: scripts/sync_supabase_env.py
   ```
   Das Skript aktualisiert ausschließlich `SUPABASE_URL` und `SUPABASE_SERVICE_ROLE_KEY`. Werte wie `SUPABASE_PUBLIC_URL` (muss auf `WEB_BASE` zeigen) oder `SUPABASE_ANON_KEY` setzt du im Anschluss von Hand, sonst verweisen signierte Downloads weiterhin auf `https://app.localhost`. Prüfe außerdem, dass kein Dummy-Schlüssel (`DUMMY_DO_NOT_USE`) übrig bleibt.

3. **Migrationen anwenden**  
   ```bash
   supabase migration up
   ```
   Sorgt dafür, dass Postgres, Policies und Storage-Buckets dem Versionsstand unter `supabase/migrations/` entsprechen.

4. **App-Loginrolle anlegen bzw. Passwort rotieren**  
   ```bash
   make db-login-user APP_DB_USER=gustav_app APP_DB_PASSWORD='<starkes Passwort>'
   ```
   Dieser Schritt ist Pflicht, weil Migrationen ausschließlich Rechte an die Rolle `gustav_limited` vergeben (siehe Kommentar in `supabase/migrations/20251109082814_grant_storage_select.sql`). Das eigentliche LOGIN-Role (`APP_DB_USER`) existiert nicht automatisch und muss hier erstellt werden – idealerweise mit einem serverseitigen Passwort-Manager. Verwende denselben User/Pass, den du in `.env` gesetzt hast.

5. **(Optional) Seeds oder Backups einspielen**  
   - Seeds laufen automatisch, wenn in `supabase/config.toml` aktiviert.  
   - Für echte Produktionsdaten bitte das jeweilige Runbook (unter `docs/migration/`) befolgen.

---

## 4. GUSTAV-Container bauen und starten

1. **Docker Compose aufrufen**  
   ```bash
   docker compose up -d --build
   docker compose ps
   ```
   Dienste im Compose-Stack:
   - `caddy`: Reverse Proxy, stellt Port 80/443 (Let’s Encrypt) bereit – nur für rein lokale Tests alternativ `8100:80` nutzen  
   - `web`: FastAPI/HTMX-Backend  
   - `learning-worker`: Hintergrundjobs & KI-Feedback  
   - `keycloak` + `keycloak-db`: Identity Provider, läuft mit `kc.sh start --optimized` (kein Dev-Modus). Hostnames werden über `.env` via `KC_HOSTNAME_URL`/`KC_HOSTNAME_ADMIN_URL` gesetzt und müssen zu deinen FQDNs passen.  
   - `ollama`: lokale KI-Inferenz (kann bei Bedarf aus dem Compose-File entfernt werden)

2. **Logs prüfen**  
   ```bash
   docker compose logs -f caddy web learning-worker keycloak
   ```
   Stoppe mit `Ctrl+C`, wenn keine Fehlermeldungen mehr auftauchen.

3. **Gesundheitschecks**  
   ```bash
   # Ersetze die Domains durch deine Werte aus WEB_BASE bzw. KC_PUBLIC_BASE_URL
   curl -s https://gustav.schule.de/health
   curl -s -o /dev/null -w '%{http_code}\n' https://id.gustav.schule.de/realms/gustav/.well-known/openid-configuration
   ```
   Ergebnis: `{"status":"healthy"}` und HTTP 200 für den Keycloak-Endpunkt. Wenn du (noch) über `localhost` testest, füge den passenden `Host`-Header hinzu: `curl -s -H "Host: app.localhost" https://<SERVER-IP>/health`.

4. **Optionale Tests**  
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r backend/requirements.txt
   .venv/bin/pytest -q
   ```

### Tests & Qualitätssicherung

Nach jedem erfolgreichen Container-Start führt die verantwortliche Lehrkraft bzw. der IT-Admin die folgenden Prüfungen durch und dokumentiert das Ergebnis (Runbook-Log oder `docs/runbooks/preflight_checklist.md`). Deployments ohne grünes Testergebnis gelten als fehlgeschlagen:

- `scripts/preflight.sh` bündelt Healthchecks (`supabase status`, API-/Keycloak-Health, Storage) und verweist auf die detailliertere Checkliste. Abweichungen sofort untersuchen, bevor Nutzer sich anmelden.
- `make test` (alias `.venv/bin/pytest -q`) führt alle automatisierten Regressionstests gegen die frisch migrierte Datenbank aus. Der Test-Lauf garantiert, dass Use-Cases, Policies und RLS-Regeln mit dem aktuellen Schema funktionieren.
- `make test-e2e` validiert die zentralen Login- und Kursfreigabe-Flows per End-to-End-Suite (`RUN_E2E=1 pytest -m e2e`). Dieser Schritt ist Pflicht vor dem ersten produktiven Einsatz sowie nach Änderungen an Auth oder Kursverwaltung.
- Manueller Smoke-Test: Als Lehrkraft in Keycloak anmelden, Kursübersicht öffnen, einen Abschnitt aktivieren und sicherstellen, dass die Lernenden-Ansicht geladen werden kann. Fehler direkt in `docs/runbooks/preflight_checklist.md` notieren.

Werden Tests rot, Stack per `docker compose logs` analysieren, die Ursache beheben (z. B. fehlende Migration, Secrets, RLS-Policy) und den kompletten Testblock erneut ausführen. Erst wenn alle Prüfungen grün sind, wird der Zugang für die Klasse freigegeben.

---

## 5. Firewall und Netzwerk-Freigaben

Der Server sollte nur die wirklich benötigten Ports öffentlich anbieten. Typische Einstellungen mit `ufw` (Ubuntu-Standard):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp           # SSH-Login
sudo ufw allow 80/tcp           # HTTP (Let’s Encrypt Challenge)
sudo ufw allow 443/tcp          # HTTPS (Caddy Reverse Proxy)
# Optional: nur öffnen, wenn externe KI-Clients Ollama nutzen sollen
sudo ufw allow 11434/tcp        # Ollama API
sudo ufw enable
sudo ufw status verbose
```

- Die Supabase-Ports (54321–54324 für API/Studio, 54322 für Postgres) bleiben geschlossen und sind nur über Docker-Bridge erreichbar.  
- Falls deine Distribution `firewalld` nutzt, setze äquivalent `firewall-cmd --permanent --add-port=80/tcp --add-port=443/tcp`. Für rein lokale Tests ohne echte Domains genügt Port 8100; in dem Fall ersetze die Regeln entsprechend.
- Prüfe zusätzlich die Schul-Firewall bzw. den Router und gib dieselben Ports frei.

---

## 6. Nacharbeiten & Betrieb

- **DNS + Zertifikat**: Wenn echte Domains genutzt werden, erhält Caddy über HTTPS/Aufrufe automatisch Let’s Encrypt-Zertifikate (Ports 80/443 müssen dann offen sein; passe das Compose-Port-Mapping entsprechend an).  
- **Konfigurationsänderungen**: Nach Änderungen an `.env`, `reverse-proxy/Caddyfile` oder Python-Code den Stack neu starten: `docker compose up -d --build`.  
- **Statuschecks**: `scripts/preflight.sh` bündelt wichtige Prüfungen (`supabase status`, Healthcheck, Keycloak). Für den vollständigen Ablauf siehe `docs/runbooks/preflight_checklist.md`, u. a. mit OIDC-Check, RLS-Rollenprüfung und Smoke-Tests.  
- **Backups**: Postgres- und Storage-Dumps per `supabase db dump` bzw. Volume-Backups erstellen (Dokumentation unter `docs/backups/`). Für den laufenden Betrieb: Cron im Container aufsetzen, z. B. `0 2 * * * /usr/bin/python /app/scripts/backup_daily.py --once >>/var/log/backup.log 2>&1`. Im Compose-Setup nutzt der Service `BACKUP_DATABASE_URL=postgresql://postgres:postgres@supabase_db_gustav-alpha2:5432/postgres`, `KC_DB_URL=jdbc:postgresql://keycloak-db:5432/keycloak`, `SUPABASE_STORAGE_ROOT=/app/supabase/storage`, `BACKUP_DIR=/backups`, `RETENTION_DAYS=7`. Wichtig: DSNs im Container dürfen keine 127.0.0.1-Hosts nutzen.  
- **Stoppen**: `docker compose down` für den App-Stack, `supabase stop` für die Datenplattform.

---

## 7. Nützliche Make-Kommandos (Shortcuts)

Die wichtigsten Automationsbefehle sind bereits im `Makefile` hinterlegt. Sie vereinfachen wiederkehrende Aufgaben:

| Befehl | Zweck | Wann einsetzen? |
| --- | --- | --- |
| `make up` | Baut alle Images neu und startet den Compose-Stack. | Nach Änderungen am Code oder an Images. |
| `make ps` | Zeigt den Status der Compose-Dienste. | Schnellcheck, ob Container laufen. |
| `make db-login-user APP_DB_USER=<name> APP_DB_PASSWORD=<secret>` | Erzeugt/aktualisiert den Datenbank-Login und hängt ihn an die Rolle `gustav_limited`. | Direkt nach dem ersten `supabase start` oder wenn Passwörter gedreht werden müssen. |
| `make supabase-status` | Führt `supabase status` aus. | Prüfen, ob Postgres/Storage/Studio laufen. |
| `make supabase-sync-env` | Liest Supabase-DSNs/Keys via CLI aus und schreibt sie in `.env`. | Nach `supabase db reset` oder wenn Service-Rollen-Schlüssel neu sind. |
| `make test` | Aktiviert das Python-Venv und führt `pytest -q` aus. | Schnelle Regressionstests vor dem Deploy. |
| `make test-e2e` | Startet die markierten End-to-End-Tests (`RUN_E2E=1 pytest -m e2e`). | Nach größeren Änderungen am Login-/UI-Fluss. |
| `make test-ollama` / `make test-ollama-vision` | Prüfen die lokale KI-Anbindung (Feedback bzw. Vision). | Nur nötig, wenn `AI_BACKEND=local` aktiv ist und Ollama laufen soll. |

Alle Targets lesen automatisch `.env`, daher keine erneute Eingabe der Secrets nötig. Optional lassen sich Variablen (`APP_DB_USER`, `OLLAMA_URL`, …) beim Aufruf überschreiben.

Mit diesen Schritten läuft GUSTAV auf einem frischen Linux-System produktionsgleich. Falls etwas hakt, zuerst `docker compose logs` und `supabase status` prüfen – damit findet man 90 % aller Fehlkonfigurationen.
