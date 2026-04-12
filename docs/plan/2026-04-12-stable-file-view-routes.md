# Stabile Datei-Views ohne ablaufende Storage-JWTs

## Zusammenfassung
- Root Cause: Mehrere Lernraum-/Live-/SSR-Views geben kurzlebige Storage-Signed-URLs direkt an Browser-Komponenten weiter.
- Sobald Polling stoppt oder eine View länger offen bleibt, laufen diese URLs ab und Vorschauen/Downloads brechen mit `InvalidJWT`.
- Vor dem eigentlichen Fix wird der bereits offene Upload-/Teaching-Arbeitsstand separat committed.
- Danach werden stabile, authentifizierte GUSTAV-Dateirouten eingeführt und als kanonischer öffentlicher Zugriffspfad genutzt.

## User Story
- Als Lernende:r oder Lehrkraft möchte ich Datei-Vorschauen und Downloads auch dann noch nutzen können, wenn eine Seite länger offen bleibt, ohne dass eingebettete Vorschauen oder Links wegen abgelaufener Storage-Tokens verschwinden.

## BDD-Szenarien
- Given eine Datei-Abgabe im Lernraum, when die Rückmeldung fertig ist und die Seite länger als eine Minute offen bleibt, then Vorschau und Download funktionieren weiterhin.
- Given eine frühere Datei-Abgabe im Lernraum-Verlauf, when sie geöffnet wird, then wird die Datei über eine stabile GUSTAV-URL geladen statt über eine direkt signierte Storage-URL.
- Given eine Datei-Abgabe in der Lehrkraft-Live-Ansicht, when sie angezeigt oder heruntergeladen wird, then bleibt der Zugriff stabil und authentisiert.
- Given ein sichtbares Datei-Material im Lernraum, when es inline angezeigt wird, then nutzt auch diese Vorschau eine stabile GUSTAV-URL.
- Given eine nicht autorisierte oder nicht sichtbare Datei, when der neue Dateipfad aufgerufen wird, then schlägt der Zugriff fail-closed fehl.

## Design-Entscheidungen
- Kein TTL-Hotfix und kein Client-Refresh-Workaround.
- Statt Redirect auf Signed-URLs liefern neue App-Endpunkte die Datei serverseitig aus.
- `url` und `download_url` bleiben im Frontend erhalten, zeigen aber auf GUSTAV-Routen statt auf `/storage/v1/object/sign/...`.
- `disposition=inline|attachment` bleibt das gemeinsame Modell für Vorschau und Download.
- Scope umfasst Lernraum, Lernmaterial-Dateivorschau, Lehrkraft-Live-Ansichten und die relevanten Legacy-/SSR-Datei-Views.

## Vertragsänderungen
- Neue Learning-Dateirouten:
  - `GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions/{submission_id}/file`
  - `GET /api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file`
- Neue Teaching-Dateiroute:
  - `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest/file`
- `LearningSubmission.files[].url`
- `LearningSubmission.files[].download_url`
- `LearningMaterial.file_url`
- `TeachingLatestSubmission.files[].url`
  liefern stabile GUSTAV-URLs; die OpenAPI-Beschreibung wird entsprechend aktualisiert.

## Testplan
- Backend-Contract-Tests für neue Datei-Endpunkte inklusive Auth, Ownership, Visibility, `disposition` und `Cache-Control`.
- API-/Payload-Tests stellen sicher, dass Response-Felder keine direkten Signed-Storage-URLs mehr enthalten.
- Frontend-/SSR-Tests decken Lernraum, Materialkarten und Live-Detailansichten mit stabilen Datei-URLs ab.
- Regressionsprüfung: Vorschau/Download funktionieren weiterhin für Bild, PDF, SB3 und HEX.
- Abschluss: `make verify`.

## Ablauf
1. Bestehende offene Änderungen separat committen.
2. Red-Tests für stabile Datei-Endpunkte und Payload-Verträge schreiben.
3. Minimale Implementierung der neuen serverseitigen Dateirouten.
4. Frontend-/SSR-Views auf die stabilen URLs umstellen.
5. OpenAPI/Doku nachziehen.
6. Zielgerichtete Suiten und `make verify` ausführen.
