# Lokale Caddy-CA für Browser-Vertrauen

Status: Implementiert; die einmalige lokale Installation und Browserabnahme stehen noch aus

## User Story

Als Entwickler möchte ich die von Caddy verwendete lokale Root-CA ausdrücklich und nachvollziehbar in den Vertrauensspeichern des Systems, von Chromium/Codex und von Firefox installieren, damit ich GUSTAV unter `https://app.localhost` und Keycloak unter `https://id.localhost` ohne Zertifikatswarnungen prüfen kann, ohne TLS oder die Produktionsparität abzuschwächen.

## Umfang und Architekturentscheidung

- `tls internal`, HTTPS, Secure-Cookies und die bestehenden öffentlichen URLs bleiben unverändert.
- Die Installation ist ein ausdrücklich aufzurufender lokaler Entwicklungsschritt. `make up` verändert keine Vertrauensspeicher.
- Es wird nur Caddys öffentliche Root-CA exportiert. Private Schlüssel bleiben im Docker-Volume.
- Der Helfer unterstützt Linux sowie klassische, Snap- und Flatpak-Firefox-Profile.
- Es gibt keine API- oder Datenbankänderung. Daher sind weder eine Änderung an `api/openapi.yml` noch eine Supabase-Migration erforderlich.
- Es handelt sich nicht um ein nutzerseitiges GUSTAV-Feature. Ein neuer `@feature-acceptance`-Test ist deshalb nicht erforderlich; die Abnahme prüft die lokale Browser-Infrastruktur direkt.

## BDD-Szenarien und Testzuordnung

### Erfolgreiche Installation

Gegeben Caddy läuft und stellt eine gültige Root-CA bereit, wenn `make trust-local-ca` ausgeführt wird, dann wird dieselbe CA in den System-, Chromium/Codex- und aktiven Firefox-Vertrauensspeicher importiert.

Automatisierter Test: `backend/tests/test_local_ca_trust.py::test_trust_installs_valid_current_ca_in_all_discovered_stores`

### Idempotente Wiederholung

Gegeben alle Vertrauensspeicher enthalten bereits die aktuelle CA, wenn die Installation erneut läuft, dann werden keine Zertifikate gelöscht oder neu importiert.

Automatisierter Test: `backend/tests/test_local_ca_trust.py::test_trust_is_idempotent_for_matching_fingerprints`

### Rotierte Caddy-CA

Gegeben die persistente Caddy-CA wurde ersetzt, wenn der Status geprüft und die Installation erneut ausgeführt wird, dann wird die Abweichung gemeldet und ausschließlich der feste GUSTAV-Zertifikatseintrag ersetzt.

Automatisierte Tests: `test_status_reports_stale_trust_store` und `test_trust_replaces_only_stale_gustav_entries`

### Ungültige oder fehlende Quelle

Gegeben Caddy ist nicht erreichbar oder die exportierte Datei ist leer, ungültig oder kein CA-Zertifikat, wenn Status oder Installation laufen, dann endet der Helfer vor jeder Änderung mit einer konkreten Handlungsanweisung.

Automatisierte Tests: `test_export_failure_does_not_change_trust_stores` und `test_invalid_certificate_does_not_change_trust_stores`

### Fehlende Werkzeuge oder Browserprofile

Gegeben `certutil` fehlt oder kein aktives Firefox-Profil ist auffindbar, wenn die Installation angefordert wird, dann wird die konkrete Voraussetzung genannt und der betroffene Speicher nicht verändert.

Automatisierte Tests: `test_missing_certutil_reports_package_hint_before_changes` und `test_missing_firefox_profile_is_reported_without_guessing`

### Make-Integration

Gegeben ein Entwickler betrachtet die verfügbaren Make-Ziele, wenn er Hilfe oder `make up` ausführt, dann sind `local-ca-status` und `trust-local-ca` auffindbar und `make up` weist bei abweichender CA ausschließlich auf den expliziten Vertrauensschritt hin.

Automatisierter Test: Ergänzungen in `backend/tests/test_makefile_targets.py`.

## Umsetzungsschritte (Red-Green-Refactor)

1. Die beschriebenen Tests zunächst fehlschlagend ergänzen.
2. Einen kleinen, standardbibliotheksbasierten Helfer unter `backend/tools/` implementieren.
3. Die beiden Make-Ziele und den nicht invasiven Hinweis in `make up` anbinden.
4. README und E2E-Dokumentation um Export, Installation, Neustart und CA-Rotation ergänzen.
5. Fokussierte Tests, `make verify`, strikten Playwright-Smoke und Browserabnahme ausführen.

## Umsetzungsergebnis

- Der Helfer und seine Make-Ziele sind implementiert und durch 26 fokussierte Tests abgedeckt.
- `make verify` ist erfolgreich: 2165 Python-Tests bestanden, 78 wurden übersprungen; außerdem bestanden 412 Frontend- und 62 H5P-Tests.
- Die vorhandene Feature-Acceptance-Suite ist mit zehn bestandenen Tests grün.
- Die lokale Caddy-CA ist im System-Vertrauensspeicher vorhanden. Die Installation in Chromium/Codex und Firefox benötigt auf dem Entwicklungsrechner einmalig `libnss3-tools`, anschließend `make trust-local-ca` und einen vollständigen Neustart beider Browser.
- Der strikte Playwright-Smoke sowie die Abnahme in Firefox und im internen Codex-Browser folgen nach diesem lokalen Neustart. Sie sind keine verbleibende Codeänderung.

## Sicherheits- und Fehlerregeln

- Vor einer Änderung werden Quelle, CA-Eigenschaft, Gültigkeit und SHA-256-Fingerabdruck geprüft.
- `certutil` verwaltet einen festen Eintrag `GUSTAV Caddy Local CA`; fremde Einträge werden nie verändert.
- Systemweite Installation benötigt einen sichtbaren `sudo`-Schritt. Pakete werden nicht automatisch installiert.
- Status ist strikt lesend. Installation und Neustart der Browser bleiben ausdrücklich und transparent.
- Wenn Codex die in NSS importierte CA nach einem vollständigen Neustart weiterhin ablehnt, wird TLS nicht abgeschwächt; der Befund wird als Grenze des internen Browsers dokumentiert.
