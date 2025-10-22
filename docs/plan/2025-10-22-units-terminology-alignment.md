# Terminology Alignment: Einheitlicher Begriff `unit`

## Ausgangslage
- Glossar fordert den einheitlichen Begriff `unit` in Code, Datenbank und Dokumentation.
- Historisch war die Supabase-Tabelle noch nicht auf `public.units` umgestellt; alle Migrationen, RLS-Policies und SQL-Queries adressieren derzeit den alten Namen.
- Die Datenbank ist derzeit leer, sodass wir Migrationen gefahrlos nachträglich anpassen und per `supabase db reset` neu aufsetzen können.

## Ziel
Komplette Harmonisierung der Terminologie: Alle technischen Artefakte (Migrationen, SQL, Python-Code, Tests, Dokumentation) verwenden konsequent `unit` bzw. `units`.

## Vorgehen
1. **Glossar-Refresher & Scope-Abgleich**  
   - Glossar-Eintrag verifizieren und als Referenz für Formulierungen festlegen.  
   - Liste aller betroffenen Komponenten (Backend, Tests, Docs, Supabase-Migrationen).

2. **Migrationen neu schreiben**  
   - Bestehende SQL-Migrationen auf den neuen Tabellennamen `public.units` anpassen, inklusive Triggern, Policies, Indizes und Fremdschlüsseln.  
   - Konsistenz der Foreign Keys in abhängigen Tabellen (`unit_sections`, `unit_materials`, `unit_tasks`, `course_modules` etc.) prüfen und ggf. anpassen.

3. **Backend & Tests anpassen (TDD)**  
   - Vor Codeänderungen fehlende Tests formulieren, die den neuen Tabellennamen erwarten.  
   - Repository/Use-Case-Schicht sowie Fixtures und Mocks auf `units` umstellen.  
   - Tests ausführen (`.venv/bin/pytest -q`) und sicherstellen, dass sie grün werden.

4. **Dokumentation aktualisieren**  
   - Alle Dateien mit der alten Bezeichnung aufspüren.  
   - Terminologie in Architektur-, Changelog- und Referenz-Dokumenten angleichen.

5. **Datenbank zurücksetzen und validieren**  
   - `supabase db reset` ausführen, um die angepassten Migrationen frisch aufzusetzen.  
   - Prüfen, dass das Schema korrekt erstellt wurde und keine Altlasten verbleiben.

6. **Nachbereitung**  
   - Lessons Learned für zukünftige Terminologie-Änderungen dokumentieren.  
   - Optionalen Rollout-Guide für andere Umgebungen ergänzen.

## Offene Fragen
- Müssen externe Integrationen (z. B. Analytics, ETL) ebenfalls auf `units` aktualisiert werden?  
- Gibt es gespeicherte Supabase-Edge-Funktionen oder Views, die den alten Namen referenzieren?
