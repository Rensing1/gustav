# CLI-Upload von HTML-Simulationen reparieren

## User Story

Als Lehrkraft möchte ich eine eigenständige HTML-Simulation mit der GUSTAV-CLI hochladen, damit ich interaktive Materialien skriptfähig bereitstellen kann, ohne dass abweichende Storage-MIME-Metadaten die sichere Finalisierung verhindern.

## Sicherheitsentscheidung

Für `kind=simulation` sind der vom Server erzeugte Upload-Intent und die tatsächlich gespeicherten Bytes maßgeblich. Der Intent muss weiterhin einen `.html`-Dateinamen und den MIME-Typ `text/html` enthalten. GUSTAV liest das Objekt beim Finalisieren vollständig innerhalb der 5-MiB-Grenze, prüft Größe und SHA-256 und validiert anschließend UTF-8, HTML-Struktur und Offline-Eigenschaften. Deshalb dürfen abweichende MIME-Metadaten des Storage die Finalisierung nicht blockieren.

Für `kind=file` bleibt die Storage-MIME-Prüfung unverändert streng. Simulationen werden weiterhin ausschließlich über den gehärteten GUSTAV-Endpunkt mit Browser-Sandbox und CSP ausgeliefert; einen Rohdownload gibt es nicht.

## BDD-Szenarien und Testzuordnung

| Szenario | Automatisierter Nachweis |
|---|---|
| Given ein kanonischer Simulations-Intent und gültige HTML-Bytes, when der Storage `application/octet-stream` oder `text/plain` meldet, then wird die Simulation erfolgreich finalisiert | Parametrisierter Service-Test |
| Given ein manipulierter Intent-MIME-Typ, when die Finalisierung versucht wird, then löscht GUSTAV das Objekt und antwortet mit `mime_not_allowed` | Service-Sicherheitstest |
| Given ein manipulierter Intent-Dateiname ohne `.html`, when die Finalisierung versucht wird, then löscht GUSTAV das Objekt und antwortet mit `invalid_filename` | Service-Sicherheitstest |
| Given falsche Größe, Prüfsumme, ungültiges HTML oder externe Ressourcen, when finalisiert wird, then bleibt die bestehende Ablehnung erhalten | Service-Regressionssuite |
| Given ein normales Datei-Material mit widersprüchlichem Storage-MIME, when finalisiert wird, then bleibt `mime_not_allowed` erhalten | Service-Regressionssuite |
| Given eine ungültige CLI-Simulation, when `materials upload` gestartet wird, then endet die CLI vor dem ersten API-Aufruf | Parametrisierter CLI-Test |
| Given eine gültige `.html`-Datei, when die CLI sie mit `--kind simulation --mime-type text/html` hochlädt, then sendet sie den kanonischen Uploadheader | CLI-Unit-Test |
| Given ein über die Oberfläche erzeugtes CLI-Token, when eine Lehrkraft eine Simulation mit der echten CLI hochlädt, then können Lehrkraft und Lernende die Simulation sicher starten | `@feature-acceptance` Playwright-Test in `simulation-material.spec.ts` |

## API-Vertrag

Die bestehenden Upload-Intent- und Finalize-Endpunkte bleiben bestehen. Für Simulationen dokumentiert der Vertrag:

- Dateiname endet auf `.html`, MIME-Typ im Intent ist `text/html` und die Größe beträgt höchstens 5 MiB.
- Die Finalisierung prüft die tatsächliche Objektgröße, SHA-256 sowie das vollständige HTML-Dokument.
- MIME-Metadaten des Storage sind für `kind=simulation` nicht autoritativ.
- Für `kind=file` bleibt der Storage-MIME-Typ Teil der verbindlichen Endung/MIME-Prüfung.

## Datenhaltung und Migration

Es sind keine Schema- oder RLS-Änderungen und keine Migration erforderlich. Die vorhandenen Tabellen, Materialarten und der private `materials`-Bucket bleiben unverändert.

## Umsetzung nach Red-Green-Refactor

1. OpenAPI-Vertrag präzisieren und fehlschlagende Service-, CLI- und Browsertests ergänzen.
2. Finalisierungslogik nach Materialart trennen und die CLI-Validierung für Simulationen lokal schließen.
3. Dokumentation aktualisieren, gezielte Tests ausführen und anschließend `make verify-feature FEATURE=simulation-material` sowie `make verify` erfolgreich abschließen.
