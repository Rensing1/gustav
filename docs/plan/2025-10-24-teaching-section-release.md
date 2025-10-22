# Plan: Teaching – Section Release Iteration (2025-10-24)

## Kontext
- Fortsetzung der Arbeiten aus `2025-10-21-teaching-units-sections-backend.md`, Iteration 3.
- Ziel: Abschnittsfreigaben pro Kursmodul implementieren (Toggle der Sichtbarkeit für Schüler).
- Rahmenbedingungen: Contract-First (`api/openapi.yml`), TDD (pytest), Security-first (RLS via Supabase).

## User Story
Als Kurs-Owner (Lehrkraft) möchte ich für jedes Kursmodul einzelne Abschnitte freischalten oder sperren, damit meine Schüler in diesem Kurs nur die Inhalte sehen, die für sie aktuell vorgesehen sind.

## BDD-Szenarien

### Sichtbarkeit toggeln (Happy Path)
- **Given** ich bin als Lehrkraft im Kurs angemeldet und besitze das Kursmodul  
  **And** der Abschnitt gehört zur verknüpften Lerneinheit  
  **When** ich den Endpoint zur Sichtbarkeit mit `visible=true` aufrufe  
  **Then** wird der Abschnitt für den Kurs freigeschaltet und die Antwort bestätigt den Zustand und Zeitstempel der Freigabe.
- **And** **When** ich denselben Endpoint mit `visible=false` aufrufe  
  **Then** wird die Freigabe entfernt und die Antwort bestätigt, dass `visible=false` gesetzt ist.

### Fehlerfälle – Fremdzugriff
- **Given** ich bin Lehrkraft, aber nicht Owner des Kurses  
  **When** ich versuche, die Sichtbarkeit eines Abschnitts in diesem Kurs zu ändern  
  **Then** erhalte ich `403 forbidden`.

### Fehlerfälle – Nicht existierende IDs
- **Given** ich bin Kurs-Owner  
  **When** ich einen Abschnitt angebe, der nicht im Kursmodul verknüpft ist  
  **Then** erhalte ich `404 not_found`.
- **And When** ich eine ungültige UUID als Pfadparameter sende  
  **Then** erhalte ich `400 bad_request`.

### Edge Case – Erste/letzte Freigabe
- **Given** alle Abschnitte eines Kursmoduls sind gesperrt  
  **When** ich den ersten Abschnitt freischalte  
  **Then** bleibt die Reihenfolge der übrigen Abschnitte unverändert und nur dieser Abschnitt ist sichtbar.
- **Given** mehrere Abschnitte sind freigeschaltet  
  **When** ich den zuletzt freigeschalteten Abschnitt wieder sperre  
  **Then** sehen Schüler nur noch die verbleibenden freigeschalteten Abschnitte.

### Fehlerfall – Ungültiger Aufruf
- **Given** ich bin Kurs-Owner  
  **When** ich den Endpoint ohne `visible`-Feld oder mit einem nicht-booleschen Wert aufrufe  
  **Then** erhalte ich `400 bad_request`.

## Offene Fragen / Annahmen
1. Freigaben gelten pro Kursmodul (`course_module_id`) und Abschnitt (`section_id`).
2. Nur Kurs-Owner dürfen Freigaben setzen/aufheben.
3. Nicht freigegebene Abschnitte bleiben für Schüler unsichtbar (Student-APIs später).

## Nächste Schritte
1. User Story finalisieren und BDD-Szenarien (Happy Path, Fehlerfälle, Edge Cases) ausarbeiten.
2. OpenAPI-Vertrag um neuen Endpoint zur Sichtbarkeitssteuerung ergänzen.
3. Supabase-Migrationsentwurf für `module_section_releases` vorbereiten.
4. Failing pytest für Endpoint anlegen (Red).
5. Minimalen Code schreiben, der Test erfüllt (Green).
6. Code kritisch prüfen, Verbesserungen vorschlagen (Refactor-Ideen).
7. Docstrings & erklärende Kommentare ergänzen.

## Referenzen
- Ursprung: `docs/plan/2025-10-21-teaching-units-sections-backend.md` (Iteration 3).
- Glossar: `docs/glossary.md` (Begriffe Kurs, Kursmodul, Abschnitt, Freigabe).
- Architektur: `docs/ARCHITECTURE.md`, Abschnitt Teaching.
