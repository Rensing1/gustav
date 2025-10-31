# Plan: Legacy Migration CLI – Phase 2 (Courses & Memberships)

## Ziel
Ausgehend vom bestehenden Identity-Mapping soll das Migration-CLI nun Kursdaten und Kursmitgliedschaften aus dem Legacy-Staging nach Alpha2 übertragen. Dabei bleiben TDD, Clean Architecture und die Audit-Anforderungen aus Phase 1 bestehen.

## Scope dieser Iteration
- Use Case `CoursesImportRun` verarbeitet:
  - `staging.courses` → `public.courses`
  - `staging.course_students` → `public.course_memberships`
- CLI erweitert sich um Phase-Sequenzierung (IdentityMap gefolgt von Courses).
- Audit-Logging pro Kurs/Mitgliedschaft (Status `ok/skip/conflict/error`) mit konsistenter Ausgabe.
- Fortschrittsmeldungen im Terminal (verarbeitete Kurse/Mitgliedschaften).
- Idempotenz: Wiederholte Läufe aktualisieren bestehende Datensätze und erzeugen keine Duplikate.

Nicht enthalten:
- Kursmodule, Units, Sections, Materialien, Tasks, Submissions.
- Resume-Mechanik über Kursphase hinaus.
- Detaillierte Konfliktauflösung (nur Erkennung/Protokollierung).

## Risiken & Annahmen
- Legacy-Courses verweisen nur auf bereits gemappte `creator_id` (IdentityMap muss gelaufen sein).
- `course_memberships` benötigt validierte `student_sub`; fehlende Zuordnung → Audit `skip` mit Grund `missing_identity`.
- Positions-/UUID-Konflikte werden durch Upsert-Logik abgefangen, führen aber zu Audit-Logs.

## TDD-Schritte
1. Neuer Pytest (`backend/tests/migration/test_legacy_migration_courses.py`):
   - Bereitet Staging-Kurse + Mitglieder sowie `legacy_user_map` vor.
   - Erwartet, dass CLI nach Phase 2 Coursetabelle und Membershiptabelle füllt.
   - Prüft Audit-Einträge je Entität, Idempotenz (zweiter Lauf ohne Änderungen) und Terminalausgabe.
2. Minimal-Implementierung des Use Cases + CLI-Erweiterung, bis Test grün.
3. Review von Code/Tests (Klarheit, Sicherheit, Idempotenz) sowie ergänzende Kommentare.

## Done Criteria
- Test schlägt initial fehl (fehlender Use-Case), anschließend grün nach Implementierung.
- CLI unterstützt Kursphase mit nachvollziehbarer Ausgabe und Audit-Logging.
- Dokumentation/Kommentierung erklärt Zweck, Anforderungen (Service-Role, Reihenfolge) und Idempotenzverhalten.
