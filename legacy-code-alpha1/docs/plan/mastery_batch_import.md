# Mastery Batch Import - Implementierungsplan

## 2025-01-11T10:45:00+01:00

**Ziel:** Vereinfachung der Massenerstellung von Wissensfestiger-Aufgaben durch verschiedene Import-Optionen.

**Annahmen:**
- Bestehende Datenstruktur (task_base + mastery_tasks) bleibt unverändert
- Import soll für Lehrer ohne SQL-Kenntnisse nutzbar sein
- Verschiedene Import-Formate sollen unterstützt werden

**Offene Punkte:**
- Bevorzugtes Import-Format (JSON, CSV, Excel)?
- Integration in bestehende UI oder separates Tool?
- Validierung und Fehlerbehandlung bei Batch-Imports?

**Beschluss:** Mehrere Optionen entwickeln, beginnend mit SQL-Template für technische Nutzer

**Nächster Schritt:** SQL-Workflow dokumentieren und weitere Optionen ausarbeiten

---

## Optionen-Übersicht

### Option 1: SQL-basierter Workflow (Sofort nutzbar)
- **Vorteile:** Keine Entwicklung nötig, direkt in Supabase nutzbar
- **Nachteile:** SQL-Kenntnisse erforderlich
- **Zielgruppe:** Technisch versierte Lehrer/Admins

### Option 2: CSV/Excel Import via Python-Skript
- **Vorteile:** Vertrautes Format, offline bearbeitbar
- **Nachteile:** Skript-Ausführung erforderlich
- **Aufwand:** 2-3 Stunden Entwicklung

### Option 3: Streamlit-UI mit Bulk-Import
- **Vorteile:** Benutzerfreundlich, integriert in App
- **Nachteile:** Entwicklungsaufwand höher
- **Aufwand:** 4-6 Stunden Entwicklung

### Option 4: JSON-Import via CLI
- **Vorteile:** Flexibel, versionierbar
- **Nachteile:** JSON-Format weniger vertraut
- **Aufwand:** 2 Stunden Entwicklung

---

## SQL-Template Dokumentation (Option 1)

### Datenstruktur
```
task_base:
├── id (UUID, auto-generated)
├── section_id (UUID, required)
├── instruction (TEXT, required)
├── task_type ('mastery_task')
├── assessment_criteria (JSONB)
├── solution_hints (TEXT)
└── order_in_section (999 für Mastery)

mastery_tasks:
├── task_id (UUID, FK zu task_base.id)
├── difficulty_level (1-3)
└── spaced_repetition_interval (Tage)
```

### Workflow
1. Section-ID identifizieren (via UI oder Query)
2. Aufgaben-Daten sammeln
3. SQL-Template ausfüllen
4. In Supabase SQL Editor ausführen

### Beispiel-Template
```sql
-- Single Task
DO $$
DECLARE
    v_section_id UUID := 'YOUR-SECTION-ID';
    v_task_id UUID;
BEGIN
    INSERT INTO task_base (
        section_id, instruction, task_type, 
        assessment_criteria, solution_hints, order_in_section
    ) VALUES (
        v_section_id,
        'Aufgabenstellung hier...',
        'mastery_task',
        '{"criteria": ["Kriterium 1", "Kriterium 2"]}'::JSONB,
        'Lösungshinweise hier...',
        999
    ) RETURNING id INTO v_task_id;

    INSERT INTO mastery_tasks (task_id, difficulty_level)
    VALUES (v_task_id, 2);
END $$;

-- Batch Insert
WITH new_tasks AS (
    INSERT INTO task_base (section_id, instruction, task_type, assessment_criteria, order_in_section)
    VALUES 
        ('SECTION-ID', 'Frage 1', 'mastery_task', '{"criteria": ["K1"]}', 999),
        ('SECTION-ID', 'Frage 2', 'mastery_task', '{"criteria": ["K2"]}', 999)
    RETURNING id
)
INSERT INTO mastery_tasks (task_id, difficulty_level)
SELECT id, 1 FROM new_tasks;
```

---

## CSV-Import Spezifikation (Option 2)

### CSV-Format
```csv
instruction,difficulty,criteria_1,criteria_2,criteria_3,hints
"Was ist eine Variable?",1,"Definition korrekt","Beispiel genannt",,"Denke an Speicherplätze"
"Erkläre Schleifen",2,"For-Schleife","While-Schleife","Anwendungsfall","Wiederholung von Code"
```

### Python-Skript Features
- CSV-Validierung
- Batch-Processing mit Fortschrittsanzeige
- Fehlerprotokoll
- Rollback bei Fehlern

---

## UI-Integration (Option 3)

### Neue Komponente: `BulkMasteryImport`
- **Ort:** `/app/components/bulk_mastery_import.py`
- **Features:**
  - Textarea für JSON/CSV-Paste
  - Datei-Upload (CSV/Excel)
  - Vorschau der zu importierenden Tasks
  - Validierung vor Import
  - Fortschrittsbalken
  - Fehlerbehandlung

### Integration in Detail-Editor
- Neuer Button "📤 Bulk Import" neben "➕ Neuer Wissensfestiger"
- Modal/Expander mit Import-Optionen
- Import nur für ausgewählten Abschnitt

---

## Implementierungsreihenfolge

1. **Phase 1:** SQL-Templates dokumentieren (erledigt)
2. **Phase 2:** Python-Skript für CSV-Import
3. **Phase 3:** UI-Integration mit Basis-Features
4. **Phase 4:** Excel-Support und erweiterte Validierung

---

## Sicherheitsüberlegungen

- **Input-Validierung:** Instruction max. 5000 Zeichen
- **SQL-Injection:** Parametrisierte Queries verwenden
- **Berechtigungen:** Nur Teacher können in eigene Units importieren
- **Rate-Limiting:** Max. 100 Tasks pro Import
- **Audit-Log:** Import-Aktionen protokollieren

---

## Test-Szenarien

1. **Happy Path:** 10 valide Tasks importieren
2. **Fehlerfall:** Ungültige Section-ID
3. **Edge-Case:** Leere/doppelte Instructions
4. **Performance:** 100 Tasks in < 5 Sekunden
5. **Rollback:** Bei Fehler keine Teilimporte

---

## Metriken & Monitoring

- Import-Erfolgsrate
- Durchschnittliche Tasks pro Import
- Fehlertypen und -häufigkeit
- Performance-Metriken (Tasks/Sekunde)