# Kummerkasten v1

## User Story
- Als Schüler möchte ich über mein Kontomenü einen Kummerkasten öffnen, einen Kurs auswählen und eine Rückmeldung absenden, damit ich anonym oder namentlich Verbesserungsvorschläge und Kritik teilen kann.
- Als Lehrkraft möchte ich über mein Kontomenü nur die Kummerkasten-Beiträge aus meinen eigenen Kursen sehen und diese archivieren oder wiederherstellen, damit ich Rückmeldungen geordnet bearbeiten kann.

## BDD-Szenarien
1. Given ein angemeldeter Schüler mit Kursmitgliedschaft, when er einen anonymen Beitrag mit Kurs und Text absendet, then wird der Beitrag gespeichert und der Lehrer sieht keinen Namen.
2. Given ein angemeldeter Schüler mit Kursmitgliedschaft, when er das Anonym-Häkchen deaktiviert und absendet, then wird der Beitrag gespeichert und der Lehrer sieht seinen Namen.
3. Given ein Schüler ohne Mitgliedschaft im gewählten Kurs, when er einen Beitrag absendet, then antwortet die API mit 403.
4. Given ein leerer Beitragstext, when der Schüler absendet, then antwortet die API mit 400.
5. Given eine Lehrkraft mit eigenen Kursen, when sie die Kummerkasten-Ansicht öffnet, then sieht sie nur offene Beiträge aus ihren Kursen, absteigend nach Erstellzeit.
6. Given eine Lehrkraft archiviert einen offenen Beitrag aus einem eigenen Kurs, when sie die offene Liste neu lädt, then fehlt der Beitrag dort und erscheint im Archiv.
7. Given eine Lehrkraft stellt einen archivierten Beitrag wieder her, when sie die offene Liste neu lädt, then erscheint der Beitrag wieder unter offen.
8. Given eine andere Lehrkraft ohne Kursbesitz, when sie auf Beiträge eines fremden Kurses zugreifen will, then antwortet die API mit 403 oder 404 fail-closed.

## OpenAPI-Entwurf
- `GET /api/learning/views/concern-box`
  - liefert `user` und `courses[]` für die Kursauswahl im Schülerformular
- `POST /api/learning/concern-box/entries`
  - Request: `{ course_id, message_text, anonymous }`
  - Response: `201 { id, created_at }`
- `GET /api/teaching/views/concern-box?scope=open|archived`
  - liefert `user`, aktive Filteroptionen und `entries[]`
- `POST /api/teaching/concern-box/entries/{entry_id}/archive`
  - Response: `204`
- `POST /api/teaching/concern-box/entries/{entry_id}/restore`
  - Response: `204`

## Migrationsentwurf
- Neue Tabelle `public.concern_box_entries`
  - `id uuid primary key default gen_random_uuid()`
  - `course_id uuid not null references public.courses(id) on delete cascade`
  - `student_sub text not null`
  - `message_text text not null`
  - `anonymous boolean not null default true`
  - `created_at timestamptz not null default now()`
  - `archived_at timestamptz null`
  - `archived_by text null`
- Indizes
  - `(course_id, created_at desc)`
  - `(student_sub, created_at desc)`
  - partieller Index auf offene Beiträge für Lehrkraftlisten
- RLS
  - Schüler dürfen `insert`, wenn sie Mitglied im Kurs sind.
  - Schüler bekommen in v1 keine `select`-Policy.
  - Lehrkräfte dürfen `select` und `update`, wenn sie Eigentümer des betroffenen Kurses sind.

## Implementierungsreihenfolge
1. OpenAPI-Vertrag und Frontend-Typen ergänzen.
2. API-, Packaging-, Frontend- und Migrationstests rot schreiben.
3. Migration und DB-Zugriff ergänzen.
4. App-Read-Models und Write-Endpunkte im Backend ergänzen.
5. SvelteKit-Seiten und Kontomenü verdrahten.
6. Tests grün ziehen und auf Verständlichkeit/Kommentierung prüfen.
