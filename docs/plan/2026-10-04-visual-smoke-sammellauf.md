# Globalen Visual-Smoke-Sammellauf reparieren

## Status

Umgesetzt und verifiziert am 4. Oktober 2026. Vor der Änderung brach der
unveränderte Aufruf `make test-visual-smoke` mit 13 frühen Fehlern ab, weil das
historische Make-Ziel weder eine laufbezogene Test-ID noch die lokale Caddy-CA
an Node weitergab. Über den sicheren Feature-Detail-Runner wurden danach die
elf dokumentierten veralteten Fälle sichtbar.

Die elf dokumentierten Bestandsfehler bezeichnen Playwright-Testfälle, nicht
einzelne PNG-Dateien: drei UI-Labor-Fälle, zwei Auth-Fälle und sechs
integrierte Designfälle. Der aktuelle, bereits freigegebene Designvertrag ist
maßgeblich; die älteren August-/September-Darstellungen werden nicht
wiederhergestellt.

## User Story

Als Entwickler möchte ich den vollständigen Visual-Smoke-Sammellauf über eine
sichere, reproduzierbare lokale Orchestrierung ausführen, damit visuelle
Regressionen zuverlässig erkannt werden, ohne Testkonten oder Fachdaten im
lokalen Produktionsabbild zurückzulassen.

## BDD-Szenarien und Testzuordnung

**Gegeben** der freigegebene lokale Compose-Stack, **wenn**
`make test-visual-smoke` ausgeführt wird, **dann** erhält der Chromium-Lauf eine
eindeutige Lauf-ID, ein privates Zustandsmanifest und die lokale Caddy-CA.

Automatisierter Nachweis: Runner- und Makefile-Verträge in
`backend/tests/test_feature_acceptance_tool.py`,
`backend/tests/test_visual_smoke_contract.py` und
`backend/tests/test_makefile_targets.py`.

**Gegeben** ein Visual-Smoke legt synthetische Konten und Fachdaten an,
**wenn** der Test erfolgreich ist oder fehlschlägt, **dann** werden nur die im
laufbezogenen Manifest registrierten Daten entfernt.

Automatisierter Nachweis: bestehende Cleanup-Verträge des
Feature-Acceptance-Runners sowie ein statischer Vertrag für den gemeinsamen
Playwright-Fixture und laufbezogene E-Mail-Adressen.

**Gegeben** die Auth-Shell wird mit einem deutschen Browserkontext geöffnet,
**wenn** Registrierung und Passwort-Reset auf Desktop oder Mobil geprüft
werden, **dann** bleiben die deutschen Überschriften und die reguläre
TLS-Prüfung verbindlich.

Automatisierter Nachweis: die beiden vorhandenen Auth-Visual-Smokes.

**Gegeben** die seit August und September freigegebenen Designänderungen,
**wenn** UI-Labor, Moduleditor und vollständige Arbeitsansichten aufgenommen
werden, **dann** entsprechen die Referenzbilder dem aktuellen `docs/DESIGN.md`
und der Sammellauf besteht zweimal hintereinander.

Automatisierter Nachweis: die mit `@visual-smoke` und `@design-system`
markierten Playwright-Tests sowie die manuelle Sichtprüfung aller tatsächlich
geänderten PNG-Dateien.

**Gegeben** ein entferntes oder nicht ausdrücklich für Mutationen
freigegebenes Ziel, **wenn** der Visual-Smoke gestartet wird, **dann** bricht
der Runner vor Browsermutationen ab.

Automatisierter Nachweis: die bestehenden Local-only- und
Mutation-Guard-Verträge des Feature-Acceptance-Runners.

## Umsetzung

1. Zuerst fehlschlagende Verträge für das neue Runner-Profil `visual`, die
   sichere Make-Verdrahtung, Chromium-Preflight, laufbezogene Identitäten und
   begrenzte Snapshot-Aktualisierung ergänzen.
2. Den vorhandenen Runner minimal um `@visual-smoke` erweitern und
   `make test-visual-smoke` darüber ausführen.
3. Die Visual-Specs auf den gemeinsamen Cleanup-Fixture sowie `e2eEmail` und
   `e2ePassword` umstellen. Die Auth-Smokes erhalten einen deutschen
   Browserkontext.
4. Referenzen ausschließlich über den sicheren Runner aktualisieren und jede
   Änderung am Designvertrag prüfen.
5. Dokumentation, Changelog und diesen Plan um den tatsächlichen
   Umsetzungsstand ergänzen.

## API, Datenhaltung und Sicherheit

Es ändert sich kein Produktendpunkt. `api/openapi.yml`, Supabase/PostgreSQL,
Migrationen und RLS bleiben unverändert. Neu ist ausschließlich die interne
Entwicklerschnittstelle
`backend.tools.feature_acceptance run --profile visual`. Der Runner behält die
bestehenden Local-only-Prüfungen, die exklusive Sperre, die private
Manifestdatei und die eigentümergebundene Bereinigung bei. TLS wird nicht
abgeschwächt.

## Verifikation

- gezielte Pytest-Verträge für Runner, Make-Ziele und Visual-Smoke-Quellen;
- `make local-ca-status`;
- sichere Aktualisierung und Sichtprüfung der betroffenen Referenzbilder;
- `make test-visual-smoke` zweimal erfolgreich mit 13 von 13 Fällen und
  bestätigter Bereinigung;
- `make verify` und `git diff --check`;
- separater Commit ausschließlich für diese Reparatur, kein Push.

Ein zusätzliches `@feature-acceptance`-Gate ist nicht erforderlich, weil kein
Produktablauf geändert wird. Der Visual-Smoke selbst bleibt der vollständige
Browsernachweis für diese Harness-Reparatur.

## Umsetzungsstand – 2026-10-04

- Das Runner-Profil `visual` selektiert ausschließlich `@visual-smoke`, prüft
  nur Chromium und übernimmt Local-only-Schutz, Lauf-ID, privates Manifest,
  Node-CA und eigentümergebundene Bereinigung vom bestehenden
  Feature-Acceptance-Harness.
- Alle datenverändernden Visual-Specs verwenden das gemeinsame Cleanup-Fixture
  sowie `e2eEmail` und `e2ePassword`. Die Auth-Shells laufen mit deutscher
  Locale; Registrierung wird an der Keycloak-Theme-Struktur und
  Passwort-Reset an der GUSTAV-App-Shell geprüft.
- Snapshot-Aktualisierung ist nur für eine ausdrücklich benannte
  `@design-system`-Spec zulässig. Das Make-Ziel aktualisiert UI-Labor,
  Moduleditor und integrierte Arbeitsansichten nacheinander über den sicheren
  Runner.
- 86 tatsächlich geänderte PNG-Referenzen wurden in fünf Kontaktbögen gegen
  `docs/DESIGN.md` geprüft. Vollständige mobile Navigation, Kummerkasten,
  Dialogzustände und der aktuelle Lernraum mit zwei funktionalen Flächen und
  1-px-Trenner entsprechen dem freigegebenen Vertrag.
- Die parallel abgeschlossene Material-Datei-Arbeit (`934e36e9`) wurde nicht
  Bestandteil dieser Reparatur. Ihre Änderungen betreffen in den verwendeten
  Fixtures nur Downloadlogik beziehungsweise ein nicht sichtbares
  Datei-`accept` und wurden nicht als neue Darstellung übernommen.
- Red/Green: Die neuen Harness-Verträge scheiterten zunächst am fehlenden
  Visual-Profil. Der sichere reale Sammellauf reproduzierte anschließend die
  elf dokumentierten Fehler; nach der minimalen Implementierung liefen die
  gezielten Verträge mit 87 Tests grün.
- `make local-ca-status` war grün. `make test-visual-smoke` bestand zweimal
  unmittelbar nacheinander mit jeweils 13 von 13 Fällen; beide Läufe
  bestätigten, dass keine laufbezogenen Konten, Kurse, Lerneinheiten,
  Sitzungen, Tokens oder H5P-Inhalte verblieben.
- `make verify` bestand mit 3.120 Backendtests, 844 Frontendtests, 66
  H5P-Tests, Produktionsbuild und allen statischen Gates. `git diff --check`
  blieb ebenfalls grün.
- Es wurden weder HTTP-API noch Datenbankschema, Migrationen, RLS oder
  Produktlogik geändert. Auf ein zusätzliches Feature-Acceptance-Gate wurde
  entsprechend der dokumentierten Begründung verzichtet.
