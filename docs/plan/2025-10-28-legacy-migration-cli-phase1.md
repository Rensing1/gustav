# Plan: Legacy Migration CLI – Phase 1 (Identity Map & Skeleton)

## Ziel
Erste implementierbare Iteration des Legacy-Migrationsskripts. Fokus auf TDD-fähiges Gerüst mit Identity-Mapping-Phase, Audit-Ausgabe und Terminal-Feedback. Keine API- oder Schemaänderungen; Nutzung der bestehenden Tabellen laut Runbook.

## Scope dieser Iteration
- CLI-Skript `backend/tools/legacy_migration.py` mit Basisbefehlen (`--dry-run`, `--resume`, `--storage-path`, `--db-dsn`).
- Use Case `IdentityMapRun` liest Staging/Legacy-Daten (Stub-Fixture) und schreibt in `legacy_user_map`, protokolliert Fortschritt in `import_audit_runs`.
- Logging/Audit-Ausgabe im Terminal (start/end, Erfolg/Fehlschlag, Anzahl verarbeiteter Nutzer).
- Failing Pytest definieren, der CLI-Aufruf (Happy Path) gegen eine Test-Datenbank ausführt, dry-run/real-run Verhalten prüft und Audittabelle kontrolliert.
- Minimaler Code, um Test grün zu bekommen (kein tatsächlicher Import weiterer Entitäten).

Nicht enthalten:
- Weitere Migration-Phasen (Courses, Units, Sections, Materials, Tasks, Submissions).
- Fortschrittsbalken, Resumable-Checks über IdentityMap hinaus.
- Integration mit Supabase Docker/Compose (Test nutzt dedizierte lokale DB-Fixture).

## Risiken & Annahmen
- Test-Datenbank steht per Fixture zur Verfügung und erlaubt das Anlegen/Leeren der Tabellen.
- Service-Role-Zugang für Testumgebung vorhanden (RLS-Bypass).
- Legacy-Staging-Daten werden im Test über Fixtures/Seeds bereitgestellt (z.B. temporäre Tabelle oder Fakes).
- Terminal-Ausgabe kann über `capsys`/CliRunner geprüft werden.

## TDD-Schritte
1. Pytest schreiben (`backend/tests/migration/test_legacy_migration_cli.py`), der:
   - Testdaten in `legacy_user_map` und Staging-Tabelle vorbereitet.
   - CLI im Dry-Run (erwartet keine DB-Schreibungen) und anschließend im Normalmodus ausführt.
   - Audit-Tabellen (`import_audit_runs`, `import_audit_mappings`) auf erwartete Einträge prüft.
   - Terminalausgabe auf Run-Start/Ende prüft.
2. Minimal-Implementierung CLI + IdentityMap-Use-Case, bis Test grün.
3. Nach erfolgreichem Test kritische Review + Dokumentation (Docstrings, Inline-Kommentare).

## Done Criteria
- Pytest-Suite enthält mindestens einen Test, der die IdentityMap-Phase des CLI abdeckt und initial fehlschlägt (Red).
- CLI-Code sorgt nach Implementierung dafür, dass derselbe Test in Grün übergeht.
- Dokumentation im Code erklärt Zweck & Nutzung des CLI.
- Terminalausgabe erfüllt Runbook-Anforderung: Start, Fortschritt (Einfachzählung), Ergebnis, Audit-Run-ID.
