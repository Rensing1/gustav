# Plan — Supabase-Migrationen dürfen Helper-Owner setzen

## Kontext
- Sicherheitsziel (vgl. `docs/CHANGELOG.md`): Alle SECURITY-DEFINER-Helper sollen der Limited-Rolle `gustav_limited` gehören, um BYPASSRLS-Eskalationen auszuschließen.
- Migration `20251027114908_learning_course_units_helper.sql` versucht `ALTER FUNCTION … OWNER TO gustav_limited`. Beim lokalen `supabase db reset` bricht sie mit `SQLSTATE 42501 must be able to SET ROLE "gustav_limited"` ab.
- Ursache: Die Supabase-CLI führt Migrationen als Rolle `supabase_admin` aus. Diese Rolle ist nicht Mitglied von `gustav_limited` und besitzt keine Superuser-Rechte; der Owner-Wechsel schlägt daher fehl.
- Tests (`backend/tests/test_learning_rls_owners.py`) maskieren das Problem: Statt zu fehlschlagen, wird bei falschem Owner `pytest.skip(...)` ausgeführt.

## Zielbild
- Migrationen sollen die Owner-Änderungen gefahrlos durchführen können.
- Tests sollen rot werden, wenn Helper nicht `gustav_limited` gehören.
- Sicherheitsprinzip (SECURITY DEFINER + Limited Owner) bleibt bestehen.

## Vorgehen
1. **Rollen-Grants absichern**
   - Neue Supabase-Migration anlegen (`supabase migration new`), die `grant gustav_limited to supabase_admin;` ausführt, falls das Grant noch nicht existiert.
   - Kommentar in der Migration: Warum der Grant sicher ist (Limited-Rolle, keine Superuser-Rechte).
   - Reihenfolge: Timestamp > `20251027114908`, damit der Grant vor künftigen Owner-Änderungen greift.

2. **Tests verschärfen**
   - `backend/tests/test_learning_rls_owners.py`: Statt `pytest.skip(...)` muss der Test mit `pytest.fail(...)` abbrechen, sobald ein Helper nicht `gustav_limited` gehört.
   - Docstring ergänzen: Voraussetzung „Migration runner muss Mitglied in `gustav_limited` sein“.

3. **Verifikation**
   - `supabase db reset` ausführen → Erfolg erwartet.
   - `.venv/bin/pytest backend/tests/test_learning_rls_owners.py -q` → grün.

4. **Dokumentation**
   - Hinweis in `docs/references/learning.md` (oder passendem Abschnitt): Migration Runner benötigt Limited-Rollen-Mitgliedschaft.
   - Lessons Learned zurück in diesen Plan eintragen (Status, Ergebnis).

## Offene Fragen
- Bedarf es zusätzlicher Grants für weitere Helper-Rollen?
- Müssen wir historische Migrationen aktualisieren, die Owner-Änderungen enthalten?
- Supabase-CLI läuft als `supabase_admin`; laut Fehlermeldung darf diese Rolle nicht modifiziert werden
  („reserved role, only superusers can modify it“). Lösungspfad muss das berücksichtigen.
