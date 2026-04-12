# Plan: Upload-Intent-Header für Learning und Teaching vereinheitlichen

## Kontext

Im aktuellen Stand verwenden die Storage-basierten Upload-Flows in Learning und Teaching ähnliche, aber nicht identische technische Pfade:

- Learning-Schüleruploads erzeugen einen Upload-Intent mit Headern für den nachgelagerten `PUT` auf Storage oder den Upload-Proxy.
- Teaching-Materialuploads erzeugen ebenfalls einen Upload-Intent und verwenden die gelieferten Header beim Upload.

Im Learning-Pfad werden derzeit für `content-type` absichtlich zwei Schreibweisen zurückgegeben:

- `content-type`
- `Content-Type`

Browser-/Fetch-Implementierungen normalisieren diese Header case-insensitiv. Wenn beide Varianten in ein `Headers`-Objekt übernommen werden, kann daraus effektiv ein kombinierter Wert wie `application/pdf, application/pdf` entstehen. Das führt anschließend im Upload-Proxy zu `mime_not_allowed`.

Der vorhandene Hotfix `hotfix/learning-upload-content-type` entschärft das Symptom im Learning-Frontend, behebt aber nicht die eigentliche Ursache im Upload-Intent-Vertrag und vereinheitlicht den Teaching-Pfad nicht.

## Ziel

Learning- und Teaching-Uploads sollen fachlich getrennt bleiben, aber dieselbe technische Upload-Basis verwenden:

- kanonische Upload-Intent-Header
- gemeinsame Header-Normalisierung für Browser-/Server-Clients
- keine doppelten `Content-Type`-Varianten mehr

H5P-Importe bleiben bewusst außerhalb dieses Refactors, weil sie einen separaten `multipart/form-data`-Flow mit anderem Sicherheitsmodell verwenden.

## User Story

Als Schüler oder Lehrer möchte ich Datei-Uploads zuverlässig durchführen können, ohne dass Upload-Header je nach Pfad unterschiedlich behandelt werden, damit Uploads für Bilder, PDFs, SB3-, HEX- und Materialdateien robust funktionieren.

## BDD-Szenarien

### Learning

1. Given ein Schüler fordert einen Upload-Intent für `image/png` an,
   When der Server antwortet,
   Then enthält `headers` genau einen kanonischen `content-type=image/png`.

2. Given ein Schüler fordert einen Upload-Intent für `application/pdf`, `application/x.scratch.sb3` oder `application/x.makecode.hex` an,
   When der Server antwortet,
   Then enthält `headers` genau einen kanonischen `content-type` mit dem erwarteten MIME-Type.

3. Given ein Browser-Client erhält einen Upload-Intent mit Headern,
   When er die Header für `fetch(..., { method: "PUT" })` vorbereitet,
   Then werden Header case-insensitiv dedupliziert und ein fehlender `content-type` nur bei Bedarf ergänzt.

### Teaching

4. Given ein Lehrer fordert einen Material-Upload-Intent an,
   When der Server antwortet,
   Then enthält `headers` genau einen kanonischen `content-type`.

5. Given der Teaching-Upload-Client lädt eine Materialdatei hoch,
   When er den Upload-Intent verwendet,
   Then werden die Header über denselben deduplizierenden Helper aufgebaut wie im Learning-Pfad.

### Regression / Scope

6. Given H5P-Importe,
   When dieser Fix umgesetzt wird,
   Then bleibt deren `multipart/form-data`-Flow unverändert.

## Vertragsänderungen

- `api/openapi.yml` beschreibt Upload-Intent-`headers` als normalisierte Header-Map mit lower-case keys.
- Es gibt keine neuen Endpunkte und keine Datenbankmigration.

## Implementierungsstrategie

1. Red:
   - Bestehende Learning-Tests so anpassen/ergänzen, dass nur noch `content-type` erwartet wird.
   - Teaching-Tests ergänzen, damit ebenfalls nur der kanonische Header akzeptiert wird.
   - Frontend-Tests für einen gemeinsamen Header-Builder hinzufügen:
     - doppelte Schreibweisen werden dedupliziert
     - Fallback-MIME wird ergänzt
     - andere Header bleiben erhalten

2. Green:
   - Gemeinsamen Header-Builder im Frontend anlegen und in Learning + Teaching verwenden.
   - Gemeinsame Backend-Helfer für die Normalisierung von Upload-Intent-Headern einführen.
   - Learning-Upload-Intent auf ausschließlich kanonische Header umstellen.
   - Teaching-Upload-Intent auf dieselbe technische Semantik ausrichten.

3. Refactor:
   - Kleine gemeinsame Upload-Intent-Helfer aus den Routen extrahieren, soweit das ohne Vermischung der Fachlogik möglich ist.
   - OpenAPI und vorhandene Kontrakttests an die kanonische Header-Semantik anpassen.

## Verifikation

- `pytest` für Learning- und Teaching-Upload-Verträge
- `vitest` für den gemeinsamen Frontend-Header-Builder
- gezielte Regression für PDF, PNG/JPEG, SB3 und HEX
