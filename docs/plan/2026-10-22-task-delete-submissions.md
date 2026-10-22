# Aufgaben mit vorhandenen Abgaben sicher behandeln

## Anlass und User Story

Bei der vollständigen UI-Prüfung schlug das echte Löschen einer H5P-Aufgabe mit vorhandener Abgabe mit HTTP 500 fehl. Die bestehende Fremdschlüsselregel schützt die Abgabe zu Recht. Als Lehrkraft möchte ich dafür eine verständliche Rückmeldung erhalten, damit ich die Aufgabe und vorhandene Schülerarbeit nicht versehentlich verliere.

## Vertrag und Szenarien

- Gegeben eine eigene Aufgabe mit Abgabe, wenn Löschen angefordert wird, dann antworten Abschnitts- und Modulroute mit 409 `task_has_submissions`; Aufgabe und Abgabe bleiben erhalten. Zuordnung: echter DB-/API-Test in `test_teaching_units_modules_api.py` und authentifizierter H5P-Drag-Browserfall.
- Gegeben eine eigene noch unbeantwortete Aufgabe, wenn sie gelöscht wird, dann bleibt 204 mit vorhandener Neunummerierung erhalten. Bestehende CRUD-Prüfungen sichern dies ab.
- Berechtigungen und CSRF bleiben in den vorhandenen Guards; eine fremde Lehrkraft erhält weiterhin 403.

Zuerst beide DELETE-Verträge in `api/openapi.yml` ergänzen, dann roten DB-/API-Test ausführen. Der DB-Adapter übersetzt ausschließlich die konkrete Abgaben-Fremdschlüsselverletzung in einen stabilen Teaching-Fehler. Die Web-Schicht bildet diesen auf eine private 409-Antwort ab; der Editor zeigt eine passende Meldung. Andere Datenbankfehler bleiben sichtbar. Keine Schemaänderung: Die bestehende Schutzregel bleibt erhalten; keine Migration erforderlich.

## Abnahme

Der echte H5P-Browserfall prüft zuerst den Abgabenschutz, beendet die Sitzung regulär und startet danach eine neue Sitzung mit einer unbeantworteten Aufgabe. Diese darf gelöscht werden; die Schüleroberfläche zeigt anschließend den reparierten Leerzustand und ermöglicht den nativen Sitzungsabschluss. Das Feature-Gate ist `make verify-feature FEATURE=h5p-drag-layout`. Danach werden die restlichen Gesamtprüfungen abgeschlossen. Kein Push.

## Ergebnis

Der DB-/API-Test reproduzierte zunächst die Fremdschlüsselverletzung und besteht nach der Fehlerübersetzung. Der echte H5P-Browserablauf bestätigt 409 ohne Verlust bestehender Abgaben sowie die weiterhin erlaubte 204-Löschung einer unbeantworteten Aufgabe. `make verify-feature FEATURE=h5p-drag-layout` und die vollständige historische Browserregression bestehen.
