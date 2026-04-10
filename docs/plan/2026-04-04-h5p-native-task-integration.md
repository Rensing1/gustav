# Plan: H5P als nativer GUSTAV-Aufgabentyp

Status: in Umsetzung

Goal:
- H5P soll im Lehrenden- und Lernraum wie ein nativer GUSTAV-Aufgabentyp wirken.
- Die sichtbare UI darf keine technische `content_id` oder Debug-Aktionen mehr in den Vordergrund stellen.
- Lehrkräfte arbeiten task-zentriert, auch wenn der bestehende H5P-Service intern weiter mit `content_id`s arbeitet.

Leitplanken:
- Contract-first: neue task-zentrierte Teaching-Endpunkte zuerst in `api/openapi.yml`.
- TDD: zuerst Contract-/API-/Packaging-Tests, dann minimale Implementierung.
- KISS: bestehende `/h5p/*`-Routen bleiben technische Basis; neue Teaching-Endpunkte kapseln sie.

Umsetzung:
1. OpenAPI um task-zentrierte H5P-Teaching-Endpunkte ergänzen:
   - `GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/editor-model`
   - `POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import`
   - `GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export`
   - `POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset`
2. Teaching-Backend ergänzt dünne Wrapper um den H5P-Service:
   - Eigentümer- und `Task.kind="h5p"`-Checks
   - Import patcht die Aufgabe mit neuer `content_id`
   - Export nutzt die zur Aufgabe gehörige `content_id`
   - Reset entfernt die verknüpfte `content_id`
3. Teacher-Svelte-UI wird task-zentriert:
   - keine sichtbare `Content-ID`
   - native Toolbar mit `Importieren`, `Exportieren`, `Zurücksetzen`, `H5P speichern`
   - Editor-Model wird über den task-zentrierten Endpunkt geladen
4. Lernraum glättet die H5P-Darstellung:
   - keine Sondersektion „Interaktive Aufgabe“
   - H5P-Player sitzt im normalen Aufgabenkörper
   - Status wirkt wie Teil des normalen Aufgaben-Workspaces

Testfokus:
- OpenAPI dokumentiert die neuen Teaching-Endpunkte samt Teacher-Permission.
- API-Tests decken Import, Reset und Editor-Model mit task-zentriertem Zugriff ab.
- Packaging-/Frontend-Contracts sichern:
  - keine sichtbare `Content-ID`-UI in `TeacherH5PTaskEditor.svelte`
  - Teacher-Editor nutzt task-zentrierte Endpunkte
  - Lernraum rendert H5P ohne separate Sondersektion
