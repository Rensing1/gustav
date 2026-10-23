# Compose & ENV Vereinheitlichung

Status: Stable

## Prinzip
- Container verwenden Service‑Namen statt 127.0.0.1 für DB/Keycloak.
- Web/App-DSNs werden aus `APP_DB_USER/APP_DB_PASSWORD` gebaut.
- Der Learning-Worker verwendet getrennte Credentials über `LEARNING_WORKER_DB_USER` / `LEARNING_WORKER_DB_PASSWORD`.
- Web und Learning-Worker verwenden den Backend-Code aus dem gebauten Image. Das verbindliche Compose-Profil mountet keinen Host-Quellcode nach `/app/backend`.
- Ein noch nicht erreichbarer Supabase-Stack führt zu `503` Readiness; die Runtime wechselt niemals implizit auf flüchtige In-Memory-Daten.

## Beispiel (docker-compose.yml)
```yaml
environment:
  - APP_DB_USER=${APP_DB_USER:-gustav_app}
  - APP_DB_PASSWORD=${APP_DB_PASSWORD:-CHANGE_ME_DEV}
  - DATABASE_URL=postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres
  - LEARNING_DATABASE_URL=${LEARNING_DATABASE_URL:-postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres}
  - LEARNING_WORKER_DB_USER=${LEARNING_WORKER_DB_USER:-gustav_worker}
  - LEARNING_WORKER_DB_PASSWORD=${LEARNING_WORKER_DB_PASSWORD:-CHANGE_ME_DEV}
  - LEARNING_WORKER_DATABASE_URL=${LEARNING_WORKER_DATABASE_URL:-postgresql://${LEARNING_WORKER_DB_USER}:${LEARNING_WORKER_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres}
  - TEACHING_DATABASE_URL=${TEACHING_DATABASE_URL:-postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@supabase_db_gustav-alpha2:5432/postgres}
  - SESSION_DATABASE_URL=${SESSION_DATABASE_URL:-postgresql://postgres:postgres@supabase_db_gustav-alpha2:5432/postgres}
```

## Anti‑Pattern
- `SESSION_DATABASE_URL=postgresql://...@127.0.0.1:54322/postgres` im Container → Verbindungsfehler.

## Keycloak: Bootstrap und Bestandskompatibilität

Der Keycloak-Service übergibt ausschließlich `KC_BOOTSTRAP_ADMIN_USERNAME` und `KC_BOOTSTRAP_ADMIN_PASSWORD`. Nicht leere gleichnamige ENV-Eingaben haben Vorrang; andernfalls verwendet Compose die bisherigen Eingaben `KEYCLOAK_ADMIN` und `KEYCLOAK_ADMIN_PASSWORD`. Sind auch diese leer oder nicht gesetzt, bleiben die bisherigen lokalen Standardwerte erhalten. Für jeden Einsatz mit eigenen Zugangsdaten müssen diese explizit gesetzt werden; `.env.example` enthält nur Platzhalter.

Die bisherigen Namen bleiben für vorhandene `.env`-Dateien und Test-/Importwerkzeuge erhalten. Diese Werkzeuge lesen weiterhin `KEYCLOAK_ADMIN*`; abweichende Bootstrap-Werte ändern deren Anmeldedaten nicht. Der Keycloak-Service lädt `.env` nicht pauschal als Containerumgebung, sondern erhält nur seine ausdrücklich aufgeführten Einstellungen. Dadurch werden weder veraltete Admin-Variablen noch sachfremde Geheimnisse an Keycloak weitergereicht. Zusätzliche Keycloak-Einstellungen brauchen einen expliziten Compose-Eintrag.

Das Login-Theme erhält `ORIGIN` ausdrücklich für die Links zur Wiederanmeldung (`/auth/login`) und Passwort-Hilfe (`/auth/forgot`). Bestehende nicht leere `ORIGIN`-Eingaben haben Vorrang. Fehlt `ORIGIN` oder ist es leer, verwendet Compose `WEB_BASE`; fehlt auch dieser Wert oder ist er leer, gilt `https://app.localhost`. Das Ziel stammt ausschließlich aus der vertrauenswürdigen Deployment-Konfiguration, nicht aus Anfrageparametern. Die Compose-Regression prüft Vorrang und Rückfälle mit synthetischen Adressen; der isolierte Keycloak-Smoke prüft beide tatsächlich gerenderten Links mit einer von localhost abweichenden Adresse.

Bootstrap erzeugt einen temporären Admin ausschließlich beim erstmaligen Anlegen des Master-Realms. Bei einer bestehenden Datenbank bleiben vorhandene Admin-Konten und Passwörter gültig; andere Bootstrap-Werte erzeugen dort weder einen neuen Admin noch einen Passwortreset. Ein temporärer Bootstrap-Zugang ist nach Einrichtung eines dauerhaften, abgesicherten Admin-Zugangs zu entfernen. Siehe [Keycloak: Bootstrap-Semantik](https://www.keycloak.org/server/bootstrap-admin-recovery).

## Einzelknoten und Sticky Sessions

`KC_SPI_STICKY_SESSION_ENCODER__INFINISPAN__SHOULD_ATTACH_ROUTE=false` deaktiviert den Owner-Routenanhang am Authentifizierungscookie explizit. Das Compose-Modell betreibt einen einzelnen Keycloak-Knoten; eine Weiterleitung anhand des Knotensuffixes wird nicht benötigt. Die [Implementierung in Keycloak 26.8.1](https://github.com/keycloak/keycloak/blob/26.8.1/model/infinispan/src/main/java/org/keycloak/models/sessions/infinispan/InfinispanStickySessionEncoderProviderFactory.java) warnt nur bei aktiviertem `shouldAttachRoute`. Die Einstellung unterdrückt keine Logkategorie. Bei einer späteren Mehrknotentopologie muss die Sitzungsaffinität des Proxys gesondert entworfen werden.

## bcrypt 1.7.0: verbleibende interne SPI-Abhängigkeit

`keycloak-bcrypt` 1.7.0 implementiert weiterhin `org.keycloak.credential.hash.PasswordHashProviderFactory` und verwendet `keycloak-server-spi-private` als Compile-Abhängigkeit: [Builddatei](https://github.com/leroyguillaume/keycloak-bcrypt/blob/v1.7.0/build.gradle.kts), [Factory](https://github.com/leroyguillaume/keycloak-bcrypt/blob/v1.7.0/src/main/java/com/github/leroyguillaume/keycloak/bcrypt/BCryptPasswordHashProviderFactory.java). Der versions- und hashgeprüfte Provider wird gegen dieselbe Keycloak-Version wie das Runtime-Image gebaut. Das beseitigt die interne Abhängigkeit nicht; eine `KC-SERVICES0047`-Buildwarnung dazu bleibt erwartbar und wird nicht ausgeblendet.

Der isolierte Test `make test-keycloak-security-smoke` prüft die gebaute Provider-Version und über `/admin/serverinfo` die Registrierung `providers.password-hashing.internal=true` einschließlich `bcrypt`. Zusätzlich prüft er eine Neuinstallation und das Upgrade 26.7.3/bcrypt 1.6.0 → 26.8.1/bcrypt 1.7.0 mit PostgreSQL, erreichbaren OIDC-Schlüsseln und erfolgreichen sowie abgewiesenen bcrypt-Anmeldungen. Eine ausdrückliche bcrypt-Testpolicy verhindert, dass die erste Anmeldung den Upgrade-Nachweis durch Umhashen auf einen anderen Algorithmus entwertet; die ausgelieferte Realm-Policy wird dafür nicht geändert.

Der Imagebau normalisiert Theme-Verzeichnisse und -Dateien mit expliziten `COPY`-Berechtigungen. Verzeichnisse bleiben durchsuchbar, Dateien für den Laufzeitnutzer lesbar; die root-eigenen Ressourcen sind für UID 1000 nicht schreibbar. Das umfasst auch die separat kopierten gemeinsamen Styles und Fonts. Restriktive lokale Dateimodi wie `0600` werden nicht unverändert ins Laufzeitimage übernommen. Die symbolischen Verzeichnismodi benötigen Dockerfile-Frontend 1.14 oder neuer; siehe [Docker-COPY-Vertrag](https://docs.docker.com/reference/dockerfile/#copy---chmod). Der Imagevertrag prüft als UID 1000/GID 0 alle Theme-Pfade einschließlich Fonts. Der temporäre Kandidaten-Build-Kontext setzt beide betroffenen Templates und die gemeinsamen Styles absichtlich auf `0600`; die alte Upgrade-Baseline erhält einen eigenen lesbaren Kontext. Der echte Checkout bleibt unverändert.

Zusätzlich importiert derselbe Smoke den tatsächlich im Image gebackenen GUSTAV-Realm mit `--import-realm`. Er startet für `gustav-web` einen OIDC-Code-Flow mit PKCE, übernimmt Cookies und den dynamisch gerenderten Registrierungslink und erwartet das vollständige GUSTAV-Formular mit HTTP 200. Das gilt für die frische 26.8.1-Datenbank sowie vor und nach dem Upgrade. Die isolierten HTTPS-Aufrufe prüfen ein kurzlebiges synthetisches Zertifikat; Secure-Cookies und Zertifikatsprüfung bleiben aktiv. Die vollständigen synthetischen Keycloak-Logs liegen im temporären pytest-Verzeichnis und werden auf Template-/HTTP-500-Fehler geprüft. Der Test verwendet sämtliche expliziten Compose-Einstellungen mit synthetischen Werten; lediglich Datenbankhost und TLS-Dateien gehören zur isolierten Testumgebung. Es werden weder Registrierungsformulare abgeschickt noch E-Mails versendet.

Ein erfolgreicher Lauf mit dem öffentlichen Realm-Import bestätigt diesen Repository-Stand. Er beweist nicht, dass abweichende bestehende Realm-Konfigurationen oder bereits gebaute Deployment-Images denselben Stand besitzen. Ein Fehlerbericht mit `Failed to process template` benötigt für eine belastbare Reparatur die bereinigte innere FreeMarker-Ausnahme mit Template, Zeile und Ausdruck; `MediaType not set` allein benennt die Ursache nicht.

**Risiko für das nächste Keycloak-Major-Upgrade:** Die interne SPI kann inkompatibel geändert oder entfernt werden. Erfolgreiche Tests für 26.8.1 sind keine Zusage für die nächste Major-Version. Vor deren Freigabe sind Provider-Quellcode und private Abhängigkeiten erneut zu prüfen, gegen die Zielversion zu bauen und beide isolierten Datenbank-/Anmeldesmokes auszuführen. Bei einem Bruch ist eine kompatible Provider-Version oder Anpassung erforderlich. Ein Rücksprung nach einer Keycloak-Schemamigration benötigt den vorherigen Datenbankstand und das dazu passende Image; ein reiner Image-Downgrade reicht nicht.
