# Zuverlässige endgültige Abgabe mit fester Entwurfsbindung

**Status:** umgesetzt
**Datum:** 20. August 2026

## Ausgangslage

Die Oberfläche zeigt eine vollständig ausgewertete Rückmeldungsfassung an und erzeugt daraus einen stabilen Idempotenzschlüssel. Der Finalisierungsendpunkt ignoriert jedoch die Identität dieser angezeigten Fassung und wählt bei der Verarbeitung erneut den neuesten Rückmeldungsentwurf. Entsteht parallel in einem anderen Tab oder durch eine Wiederholung ein neuer Entwurf, kann deshalb eine noch nicht fertige oder eine andere Fassung finalisiert werden. Zusätzlich lädt die SvelteKit-Aktion vor jeder Finalisierung redundant den gesamten Lernraum; ein Fehler in diesem Leseweg verhindert die zulässige Abgabe, obwohl der geschützte Finalisierungsendpunkt selbst alle Berechtigungen prüft.

## User Story

Als lernende Person möchte ich genau die vollständig rückgemeldete Fassung endgültig abgeben, die ich vor mir sehe, damit parallele oder wiederholte Rückmeldungsanfragen meine Abgabe nicht unzuverlässig machen.

## BDD-Szenarien und Testzuordnung

1. **Angezeigte Fassung wird finalisiert**
   - Given eine vollständig ausgewertete Rückmeldungsabgabe wird angezeigt
   - When „Endgültig abgeben“ gewählt wird
   - Then enthält die Anfrage deren `feedback_submission_id` und die finale Abgabe kopiert exakt diese Fassung
   - Nachweis: OpenAPI-Vertragstest, Repository-Integrationstest, SvelteKit-Aktionstest und `@feature-acceptance`-Playwright-Test
2. **Neuerer paralleler Entwurf**
   - Given nach der angezeigten Fassung entsteht ein neuerer noch nicht ausgewerteter Entwurf
   - When die angezeigte Fassung finalisiert wird
   - Then wird weiterhin die explizit benannte fertige Fassung finalisiert
   - Nachweis: echter Datenbank-Integrationstest
3. **Fremde oder unpassende Entwurfs-ID**
   - Given die ID gehört einem anderen Schüler, Kurs oder einer anderen Aufgabe
   - When die Finalisierung versucht wird
   - Then entsteht keine Abgabe und die API antwortet mit `409 draft_missing`
   - Nachweis: API-/Datenbank-Negativtest
4. **Entwurf noch nicht fertig**
   - Given die explizit benannte Rückmeldungsabgabe ist noch in Verarbeitung
   - When sie finalisiert wird
   - Then antwortet die API mit `409 draft_not_ready`
   - Nachweis: API-Integrationstest
5. **Wiederholte identische Anfrage**
   - Given dieselbe Fassung und derselbe Idempotenzschlüssel werden erneut gesendet
   - When die Wiederholung eintrifft
   - Then wird dieselbe finale Abgabe zurückgegeben und kein Versuch doppelt verbraucht
   - Nachweis: Datenbank-Integrationstest und Browser-Doppelklicktest
6. **Unabhängigkeit vom redundanten Seiten-Leseweg**
   - Given die Finalisierungsaktion enthält Aufgabe und Rückmeldungs-ID
   - When der Browser die Aktion absendet
   - Then ruft die BFF direkt den autorisierenden Finalisierungsendpunkt auf, ohne zuvor den ganzen Lernraum erneut zu laden
   - Nachweis: SvelteKit-Aktionstest

## API- und Datenbankentwurf

`POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize` erhält contract-first einen verpflichtenden JSON-Body:

```yaml
type: object
required: [feedback_submission_id]
additionalProperties: false
properties:
  feedback_submission_id:
    type: string
    format: uuid
```

Die bestehende Antwort und Fehlercodes bleiben erhalten. Das Datenbankschema reicht aus; die vorhandenen Besitzer-, Kurs-, Aufgaben-, Intent- und Statusspalten erlauben eine sichere gebundene Auswahl. Eine Migration ist nicht nötig.

## Red–Green–Refactor

1. OpenAPI-Vertrag und rote Vertragstests für `feedback_submission_id` ergänzen.
2. Rote API-/Repository-Tests für parallele, fremde und unfertige Entwürfe schreiben.
3. Use Case und Repository minimal auf die explizite Entwurfs-ID binden.
4. Rote Frontendtests für Body-Weitergabe und den entfallenden redundanten Lernraum-Load schreiben.
5. BFF und Formular minimal anpassen, anschließend verständliche Namen, Docstrings und Fehlermeldungen prüfen.
6. Gezielte Tests, authentifizierte Feature-Abnahme und `make verify-feature` ausführen.

## Umsetzungsergebnis

- Der API-Vertrag verlangt nun `feedback_submission_id`; die BFF übernimmt die ID aus der sichtbar rückgemeldeten Fassung.
- Use Case und Repository wählen die Rückmeldungsabgabe über ID, Schüler, Kurs, Aufgabe und `intent=feedback`. Fremde oder unpassende IDs sind dadurch nicht sichtbar und werden nicht finalisiert.
- Ein neuerer paralleler Entwurf beeinflusst die gewählte Fassung nicht mehr. Der stabile Idempotenzschlüssel schützt Wiederholungen weiterhin vor doppelten Versuchen.
- Die Finalisierungsaktion lädt nicht mehr redundant den vollständigen Lernraum. Autorisierung und Sichtbarkeit bleiben am geschützten Backend-/Datenbankrand erhalten.
- Text-, Datei-, Pending-, Frontend- und OpenAPI-Nachweise decken den neuen Vertrag ab.
