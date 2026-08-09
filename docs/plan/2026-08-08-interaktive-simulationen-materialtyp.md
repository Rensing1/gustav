# Interaktive Simulationen als Materialtyp

## User Story

Als Lehrkraft möchte ich eine selbstständige interaktive HTML-Simulation als Material hochladen, mit einer kurzen Orientierung versehen und vorab prüfen können, damit Schülerinnen und Schüler ein Konzept explorativ untersuchen können, ohne dass die Simulation selbst zur bewerteten Aufgabe wird.

## Fachliche Entscheidungen

- `simulation` wird ein dritter Materialtyp neben `markdown` und `file`.
- Eine Simulation ist genau eine UTF-8-HTML-Datei bis 5 MiB. CSS, JavaScript, Bilder und kleine Datensätze sind eingebettet; externe Ressourcen und Netzverbindungen sind unzulässig.
- `body_md` enthält einen optionalen Orientierungstext. Arbeitsauftrag, Abgabe und Feedback bleiben separate GUSTAV-Aufgaben.
- Der Player startet nur nach einer bewussten Aktion und speichert weder Zustand noch Ergebnisse oder Telemetrie.
- Simulationscode gilt auch bei Upload durch eine Lehrkraft als nicht vertrauenswürdig. Er wird serverseitig geprüft und in einer CSP- und Iframe-Sandbox ohne Same-Origin-Rechte ausgeführt.
- Version 1 kennt keine zentrale Bibliothek, Wiederverwendung, Paketformate oder Ersetzung des HTML-Inhalts.

## BDD-Szenarien und automatisierte Nachweise

1. **Gültiger Upload:** Gegeben eine berechtigte Lehrkraft, wenn sie eine selbstständige HTML-Datei mit Titel und Orientierung finalisiert, dann entsteht ein Material `kind=simulation`. Nachweis: API- und Datenbanktest.
2. **Explizite Vorschau:** Gegeben eine gespeicherte Simulation, wenn die Lehrkraft „Vorschau starten“ wählt, dann wird erst danach ein sandboxed Iframe erzeugt. Nachweis: Frontend-Komponententest und Playwright.
3. **Freigegebenes Lernen:** Gegeben ein offener Abschnitt, wenn der Schüler „Simulation starten“ wählt, dann werden Orientierung und Player angezeigt. Nachweis: `@feature-acceptance`-Playwright-Test über echte Oberfläche, Server, Storage und Datenbank.
4. **Zurücksetzen und Schließen:** Gegeben veränderter Zustand, wenn der Schüler zurücksetzt oder schließt, dann wird das Iframe neu erzeugt beziehungsweise entfernt. Nachweis: Komponenten- und Browser-Test.
5. **Offline-Grenze:** Gegeben HTML mit externen Quellen, Imports, Navigation oder Netzwerk-APIs, wenn finalisiert wird, dann antwortet die API mit einem stabilen Fehlercode und entfernt das temporäre Objekt. Nachweis: Validator- und Service-Tests.
6. **Formatgrenzen:** Leere, ungültige UTF-8-, MIME-/Endungs- oder über 5 MiB große Dateien werden abgelehnt. Nachweis: Service- und API-Tests.
7. **Berechtigungen:** Unangemeldete, fremde oder noch nicht freigeschaltete Aufrufe erhalten keinen Player. Nachweis: Routen- und E2E-Tests.
8. **Typtrennung und Löschen:** Datei-Endpunkte liefern kein Simulations-HTML; beim Löschen verschwindet auch das Storage-Objekt. Nachweis: Routen- und Service-Tests.

## Vertrag und Architektur

- OpenAPI ergänzt `simulation`, den Upload-Intent-Discriminator `kind`, `body_md` beim Finalisieren, `simulation_url` bei Lernmaterialien sowie geschützte Player-Endpunkte für Teaching und Learning.
- Eine Migration erweitert die Material- und Upload-Intent-Constraints, die private Bucket-Whitelist und einen mengenbasierten Sichtbarkeits-Helper für gespeicherte Material-Assets.
- Beim Finalisieren lädt der Teaching-Use-Case die Bytes begrenzt aus dem Storage, prüft tatsächliche Größe und SHA-256, dekodiert strikt als UTF-8 und validiert HTML, URLs, CSS und offensichtliche Netzwerk-/Navigations-APIs.
- Player-Endpunkte streamen die Bytes selbst und liefern `Cache-Control: private, no-store`, `nosniff`, `no-referrer`, eine restriktive Permissions-Policy und eine CSP mit `sandbox allow-scripts`, `connect-src 'none'` und ohne Frames, Worker, Objekte, Form-Targets oder Base-URI.
- Direkte Download- oder Presigned-URLs für Simulations-HTML sind ausgeschlossen.

## TDD-Reihenfolge und Abschluss

1. OpenAPI-Vertrag, danach fehlschlagende Contract-Tests.
2. Fehlschlagende Migrations-, Validator-, Use-Case- und Routentests; anschließend minimale Implementierung und Refactoring.
3. Fehlschlagende Frontend- und CLI-Tests; anschließend Oberfläche und CLI-Parität.
4. Dokumentation, lokale Migration, gezielte Testläufe und abschließend `make verify-feature`.

Die statische Prüfung kann absichtlich verschleierten Inline-Code nicht formal als offline beweisen. Diese bekannte Grenze, ebenso wie mögliche CPU-belastende Endlosschleifen, wird in der Nutzerdokumentation festgehalten.
