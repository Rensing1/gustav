# Programm- und OpenDocument-Dateien als Material

## Ziel

Lehrkräfte können Scratch-, Calliope-, Filius-, Python-, JSON-, Text- und OpenDocument-Dateien über die Weboberfläche, den direkten CLI-Upload und den CLI-Spiegel als privates `Material` bereitstellen. Lernende laden freigegebene Dateien mit ihrem Originalnamen herunter; GUSTAV zeigt diese Formate nicht inline an und führt sie nicht aus.

## User Stories

- Als Lehrkraft möchte ich `.sb3`, `.hex`, `.fls`, `.py`, `.json`, `.txt`, `.odt`, `.ods` und `.odp` als Material hochladen, damit Lernende sie in der vorgesehenen lokalen Anwendung bearbeiten können.
- Als Lehrkraft möchte ich dieselben Dateien mit `gustav materials upload` und über einen CLI-Spiegel verwalten, ohne MIME-Typen selbst ermitteln zu müssen.

## BDD-Szenarien und Testzuordnung

1. **Unterstütztes Material über die Weboberfläche**
   - Given eine Lehrkraft bearbeitet einen Lernabschnitt oder ein Lernmodul,
   - when sie eine unterstützte Datei als Material hochlädt,
   - then speichert GUSTAV sie privat mit Originalname und kanonischem MIME-Typ.
   - Nachweis: parametrisierter API-Test und `@feature-acceptance` in `frontend/e2e/material-program-file-download.spec.ts`.

2. **Automatische CLI-Erkennung**
   - Given eine unterstützte lokale Datei,
   - when die Lehrkraft `gustav materials upload` ohne `--mime-type` ausführt,
   - then sendet die CLI den zur Endung gehörenden kanonischen MIME-Typ.
   - Nachweis: parametrisierter Test in `backend/tests/test_gustav_cli.py` für Abschnitts- und Modulziele.

3. **CLI-Fehler vor einem Netzwerkzugriff**
   - Given eine unbekannte Endung oder ein widersprüchliches `--mime-type`,
   - when die Lehrkraft den CLI-Upload startet,
   - then bricht die CLI mit einer verständlichen Meldung ab, bevor sie Upload-Intent oder Storage aufruft.
   - Nachweis: CLI-Unit-Tests mit gesperrten HTTP-Helfern.

4. **CLI-Spiegel bleibt verlustfrei**
   - Given ein Spiegel mit einem unterstützten Datei-Material,
   - when `sync pull`, `status` oder `push` das Asset verarbeitet,
   - then bleiben Originalname, kanonischer MIME-Typ und Bytes stabil.
   - Nachweis: Roundtrip- und Preflight-Tests in den CLI-Sync-Tests.

5. **Sicherer Download für Lernende**
   - Given ein freigegebenes Programm- oder OpenDocument-Material und eine aktive Kursmitgliedschaft,
   - when der Lernende die Datei öffnet oder ausdrücklich `inline` anfordert,
   - then liefert GUSTAV die exakten Bytes als `attachment` mit `private, no-store` und `X-Content-Type-Options: nosniff`.
   - Nachweis: API-Routentest und Playwright-Downloadtest.

6. **Fail closed**
   - Given das Material ist nicht freigegeben, der Lernende ist kein Kursmitglied oder die Lehrkraft ist nicht Autor,
   - when die Datei angefordert oder verändert wird,
   - then liefert GUSTAV keine Dateibytes.
   - Nachweis: DB-gestützte API-Integrationstests.

7. **Bestehende Vorschauen bleiben erhalten**
   - Given ein PDF, PNG, JPEG oder eine eigenständige HTML-Simulation,
   - when das Material geöffnet wird,
   - then bleibt das bisherige Vorschau- beziehungsweise Sandbox-Verhalten unverändert.
   - Nachweis: Frontend- und API-Regressionstests.

## API-Vertrag

Die bestehenden Material-Endpunkte bleiben erhalten. `MaterialUploadIntentRequest.mime_type` akzeptiert bei `kind=file` zusätzlich:

- `application/x.scratch.sb3`
- `application/x.makecode.hex`
- `application/x.filius.fls`
- `text/x-python`
- `application/json`
- `text/plain`
- `application/vnd.oasis.opendocument.text`
- `application/vnd.oasis.opendocument.spreadsheet`
- `application/vnd.oasis.opendocument.presentation`

Endung und MIME-Typ müssen zusammenpassen. Unbekannte Endungen führen zu `invalid_filename`, widersprüchliche MIME-Typen zu `mime_not_allowed`. Für nicht vorschaufähige Formate erzwingen Lehrkraft- und Lernenden-Downloads `Content-Disposition: attachment`; die Lernendenroute setzt zusätzlich `X-Content-Type-Options: nosniff`.

## Datenbank und Storage

Die Tabellenstruktur, `kind='file'` und die RLS-Policies bleiben unverändert. Eine additive Supabase-Migration erweitert ausschließlich `storage.buckets.allowed_mime_types` für den privaten `materials`-Bucket und setzt `public=false`. Das allgemeine Materiallimit bleibt 20 MiB; Simulationen bleiben separat auf 5 MiB begrenzt.

## Implementierungsreihenfolge

1. OpenAPI-Vertrag und Storage-Migration entwerfen.
2. Fehlende API-, CLI-, Sync- und Frontendtests schreiben und ihr Scheitern nachweisen.
3. Eine zentrale Teaching-Regel für Endung, MIME-Typ und Inline-Fähigkeit implementieren.
4. Backend, CLI und CLI-Sync an diese Regel anbinden; die Weboberfläche erhält dieselbe explizite TypeScript-Zuordnung.
5. Downloadoberflächen auf reine Attachments für die neuen Formate begrenzen.
6. Dokumentation aktualisieren und gezielte Tests ausführen.
7. `make verify-feature FEATURE=material-program-file-download` und anschließend `make verify` erfolgreich ausführen.

## Nicht im Umfang

- Malware-Scanning
- Quelltextvorschau oder serverseitige Ausführung
- Externe Editor-Integrationen
- Neue Dateitypen für Schülerabgaben
- Änderungen an PDF-/Bildvorschauen oder HTML-Simulationen
