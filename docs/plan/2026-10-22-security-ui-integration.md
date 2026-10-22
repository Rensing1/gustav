# Integration von UI- und Security-Stand

## Ziel

Die sechs lokalen UI-Commits und der geprüfte Security-Commit werden auf dem lokalen `master` zusammengeführt. Öffentliche HTTP-APIs, Datenbankschemata und fachliche Abläufe bleiben unverändert. Es erfolgen kein Push, kein PR und kein Produktionsrollout.

## Ausgangslage

- Beide Entwicklungsreihen basieren auf `origin/master` bei `3ac665c5` und ändern keine gemeinsame Datei.
- Der simulierte Merge war konfliktfrei; Frontend-Produktionsbuild, Supply-Chain-Check, 87 gezielte Backend-Tests und 74 H5P-Tests waren erfolgreich.
- Der UI-Stand brachte bereits vor dem Merge zwei Svelte-Typfehler und 145 fehlschlagende Frontend-Tests mit. Der simulierte Merge erhöhte diese Zahl nicht und ergänzte einen erfolgreichen Security-Test.

## Red–Green–Refactor

1. Den Security-Branch per Merge-Commit integrieren.
2. Die vorhandenen roten UI-Nachweise unverändert reproduzieren.
3. Zuerst gemeinsame Ursachen minimal beheben: vollständige Props in der internen Vorschau, browsernahe `matchMedia`-Testumgebung und leere Svelte-Blöcke.
4. Danach ausschließlich veraltete Tests an die bereits beschlossenen UI-Verträge anpassen. Produktcode wird nur geändert, wenn der Test einen tatsächlichen Laufzeit- oder Barrierefreiheitsfehler zeigt.
5. Frontend-Check, Frontend-/H5P-Tests und Produktionsbuild grün ausführen. Anschließend `make verify`, die Security-Feature-Acceptance und das Dependency-Audit für den integrierten Stand ausführen.

## BDD-Szenarien

- Gegeben ist der lokale UI-Stand, wenn der Security-Commit integriert wird, dann entsteht der gemeinsame Git-Baum ohne Konflikte und alle Security-Pins bleiben erhalten.
- Gegeben ist eine interne Dialogvorschau, wenn der Aufgabenkontext gerendert wird, dann erhält er eine eindeutige Aufgaben-ID.
- Gegeben ist eine Desktop- oder schmale Testansicht, wenn die Gliederungsnavigation startet oder ihre Medienabfrage ändert, dann öffnet beziehungsweise schließt sie sich deterministisch.
- Gegeben sind die neuen Navigations- und Arbeitsbereichskomponenten, wenn ihre Vertragstests laufen, dann prüfen sie die aktuelle Struktur und keine entfernten UI-Elemente.
- Gegeben ist der integrierte lokale Stack, wenn der authentifizierte Security-Rundlauf ausgeführt wird, dann funktionieren Anmeldung, Markdown-Entwurf, Bild-Upload und H5P weiterhin gemeinsam.

## Abschluss

Der integrierte Stand gilt erst nach erfolgreichen Gates als lokal abgeschlossen. Bereits vorhandene UI-Testfehler werden nicht als Security-Ausnahme akzeptiert oder unterdrückt.

## Ergebnis

- Der Merge auf den lokalen `master` war konfliktfrei. Die anschließende Integration korrigiert ausschließlich tatsächliche UI-Laufzeitprobleme und veraltete Verträge: browsernahe Test-APIs, Dialog-/H5P-Sichtbarkeit, Abgabeaktionen, Modulnavigation und die Packaging-Prüfung des neuen `AppHeader`.
- `make test`: 3180 Tests bestanden, 36 reguläre Opt-in-Tests übersprungen.
- `make test-frontend-h5p`: Svelte-Check ohne Fehler oder Warnungen, 846 Frontend-Tests, 11 Build-Policy-Tests und 74 H5P-Tests bestanden; der Produktionsbuild war erfolgreich.
- `make docker-validate` und `make test-docker-image-smoke`: erfolgreich. Das Runtime-Image enthält PyJWT und den geprüften DSPy-SafeDisk-Pfad; `python-jose`, `ecdsa`, das ursprüngliche `diskcache` und Testwerkzeuge fehlen. Der isolierte Keycloak-26.8.1-Test mit PostgreSQL 16.15, OIDC-Discovery und bcrypt bestand.
- `make supply-chain-check`: erfolgreich. `make dependency-audit`: Frontend, H5P, Python und die separate DSPy-Upstream-Prüfung ohne bekannte Schwachstellen; keine Ignore-Liste und keine abgesenkte Schwelle.
- Der lokale Stack läuft nach dem Merge mit Keycloak 26.8.1, PostgreSQL 16.15 und Caddy 2.11.7. Die bestehende lokale Caddy-Root-CA blieb unverändert und ist in System, Chromium/Codex und Firefox vertraut.
- Die gezielte `security-update`-Feature-Acceptance bestand einschließlich Anmeldung, Markdown, Upload und H5P. Das Harness bestätigte anschließend die vollständige Bereinigung aller laufbezogenen Testdaten.
- `make verify-feature FEATURE=security-update` bestand anschließend als ungeteiltes Abschlussgate gegen den aktualisierten lokalen Stack.
