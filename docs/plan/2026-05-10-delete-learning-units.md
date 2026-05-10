# Lerneinheiten löschen

## Ziel

Lehrkräfte können selbst erstellte Lerneinheiten sichtbar und zuverlässig löschen. Die bestehende Teaching-API bleibt der zentrale Vertrag; die Svelte-Oberfläche macht die Aktion im Katalog und im Arbeitsbereich auffindbar.

## Vorgehen

- API-Vertrag für `DELETE /api/teaching/units/{unit_id}` um Storage-Fehlerfälle ergänzen.
- Vor dem DB-Delete alle zur Lerneinheit gehörenden Storage-Objekte entfernen:
  - Datei-Materialien aus dem Material-Bucket.
  - Schülerabgaben und PDF-Derivate aus dem Submission-Bucket.
- DB-Hard-Delete erst ausführen, wenn Storage-Aufräumen erfolgreich war.
- In der SvelteKit-Oberfläche direkte Aktionen nach `docs/DESIGN.md` anbieten:
  - keine versteckte Ellipsis-Pflicht für `Bearbeiten`/`Löschen`,
  - harte, kompakte Workspace-Aktionen,
  - Löschdialog mit Titelbestätigung und klarer Warnung zu Kurszuordnungen.

## Tests

- OpenAPI-Vertrag dokumentiert `502` und `503` beim Unit-Delete.
- Backend-API löscht Material- und Submission-Storage-Objekte vor dem Unit-Delete.
- Backend-API bricht bei Storage-Fehlern ab und lässt die Unit erhalten.
- Frontend-Katalog zeigt eine Löschaktion je Lerneinheit.
- Frontend-Detailseite zeigt direkte Header-Aktionen und einen Löschdialog.
