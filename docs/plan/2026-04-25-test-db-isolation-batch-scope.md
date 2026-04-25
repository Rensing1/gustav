# Test-DB-Isolation und batchweise Migrationstests

## Ziel

Die bestehende Testsuite darf keine gemeinsam genutzte Datenbank global leeren. DB-schreibende Tests sollen ihre eigenen Datensätze eindeutig markieren und anschließend nur diese Datensätze bereinigen. Legacy-Migrationstests sollen importierte Staging-Daten nach einem expliziten Batch filtern können.

## User Story

Als Entwickler und Betreiber von GUSTAV möchte ich DB-nahe Tests auch gegen eine produktionsnahe Supabase/PostgreSQL-Struktur ausführen können, ohne bestehende Daten zu löschen, damit versehentliche Testläufe keine Datenbank-Neuaufsetzung erzwingen.

## BDD-Szenarien

### Szenario 1: Worker-Testdaten werden markiert

Given ein Pytest-Lauf erzeugt `learning_submission_jobs`
When der Job angelegt wird
Then enthält die Payload eine Pytest-Quelle und eine stabile Testlauf-ID.

### Szenario 2: Worker verarbeitet nur den eigenen Testlauf

Given die Queue enthält Jobs aus mehreren Testläufen
When ein Worker-Test `run_once` mit einer Testlauf-ID ausführt
Then least und verarbeitet der Worker nur Jobs mit dieser Testlauf-ID.

### Szenario 3: Test-Cleanup löscht nur eigene Queue-Jobs

Given die Queue enthält produktive Jobs und Jobs des aktuellen Tests
When der Test seinen Cleanup ausführt
Then werden nur Jobs mit der aktuellen Testlauf-ID gelöscht.

### Szenario 4: Legacy-Migration verarbeitet nur einen Batch

Given Staging-Tabellen enthalten Zeilen mehrerer Import-Batches
When die Migration mit `--batch-id` gestartet wird
Then liest sie nur Zeilen mit passender `import_batch_id`.

### Szenario 5: Remote-DBs brauchen explizite Isolation

Given `DATABASE_URL` zeigt auf eine externe Datenbank
When DB-Tests ohne expliziten Isolationsmodus laufen
Then wird diese DSN nicht als Testziel verwendet.

## Umsetzung

- Queue-Jobs aus Pytest erhalten `_gustav_source=pytest` und `_gustav_test_run_id`.
- Worker-Leasing akzeptiert optional `test_run_id` und filtert auf diese Payload-Markierung.
- Test-Helfer `cleanup_learning_jobs_for_run` ersetzt globale Queue-Löschungen in Worker-Tests.
- Legacy-Migrations-CLI bekommt `--batch-id`; Staging-Loader erzwingen bei Batch-Betrieb die Spalte `import_batch_id`.
- Migration `20260425120000_legacy_import_batch_scope.sql` ergänzt Batch-Spalten idempotent.
- Ein statischer Safety-Test verhindert erneute globale Queue-Deletes in Worker-Tests.

## Verifikation

- Syntaxcheck für geänderte Python-Module.
- Gezielte Pytest-Suite für Batch-Scope, DB-Safety-Contract und bestehende Worker-Tagging-Tests.
- Keine Ausführung global destruktiver Datenbank-Operationen im Rahmen dieser Änderung.
