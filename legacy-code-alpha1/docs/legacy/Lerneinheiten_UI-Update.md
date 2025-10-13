# Lerneinheiten UI-Update Plan

**Letzte Aktualisierung:** 2025-09-03 - ✅ **VOLLSTÄNDIG IMPLEMENTIERT** - Alle Phasen abgeschlossen

## Zusammenfassung
Überarbeitung der Lerneinheiten-UI für bessere Benutzerfreundlichkeit mit Fokus auf:
- Größere, komfortablere UI-Elemente für Lehrer
- Klare visuelle Trennung zwischen normalen Aufgaben und Wissensfestiger-Aufgaben
- Vollbreite Formulare statt enge Split-View
- Vereinfachte Navigation durch Integration in bestehende Sidebar
- **NEU:** Nutzung der Task-Type-Trennung mit separaten Views (`all_regular_tasks`, `all_mastery_tasks`)

## Designentscheidungen

### 1. Erweiterte Sidebar-Navigation (statt separatem Strukturbaum)
- **Warum:** Ein zentraler Ort für alle Navigation, keine Split-View mehr nötig
- **Vorteil:** Volle Breite für Inhalte, weniger Komponenten, wartbarer
- **Integration:** Erweiterung der bestehenden `render_sidebar_with_course_selection()`
- **Struktur:**
  ```
  Kurs: XY
  Lerneinheit: ABC
  ─────────────────
  📚 Abschnitte
  ▼ Abschnitt 1
    📚 3 Materialien
    ✏️ 2 Aufgaben
    🎯 1 Wissensfestiger
    [Aktions-Buttons]
  ▶ Abschnitt 2
  ▶ Abschnitt 3
  [+ Neuer Abschnitt]
  ```

### 2. Quick Actions im Hauptbereich
- **Warum:** Kontext-sensitive Aktionen ohne Popups
- **Position:** Direkt über dem Editor wenn Abschnitt ausgewählt
- **Buttons:** `+ Material | + Aufgabe | + Wissensfestiger`

### 3. Keine Sortierung in Phase 1
- **Warum:** Reduziert Komplexität erheblich
- **Alternative:** Manuelle Nummerierung in Abschnittsnamen
- **Zukunft:** Kann später ohne Breaking Changes ergänzt werden

### 4. Elimination von structure_tree.py
- **Warum:** Redundant mit erweiterter Sidebar
- **Vorteil:** Weniger Code, einfachere State-Verwaltung
- **Migration:** Funktionalität wird in Sidebar integriert

## Implementierungsschritte

### Schritt 1: render_sidebar_with_course_selection erweitern (2h)
**Datei:** `app/components/ui_components.py`

**Änderungen:**
1. Neuer Parameter `show_section_navigation: bool = False`
2. Abschnitts-Navigation nach Lerneinheiten-Auswahl
3. Import der benötigten Queries und State-Management
4. Rückgabe erweitern um selected_section

**Code-Struktur:**
```python
def render_sidebar_with_course_selection(
    user_id: str,
    show_unit_selection: bool = True,
    additional_content: Optional[Callable] = None,
    show_section_navigation: bool = False  # NEU
) -> Tuple[Optional[Any], Optional[Any], Optional[Any]]:  # +selected_section
    
    # ... bestehender Code ...
    
    selected_section = None
    
    if show_section_navigation and selected_unit:
        st.divider()
        st.markdown("**📚 Abschnitte**")
        
        # Lade Abschnitte
        sections, error = get_sections_for_unit(selected_unit['id'])
        
        # Render Abschnitte als Expander
        for section in sections:
            with st.expander(f"📁 {section['title']}", expanded=is_expanded):
                # Inhalts-Statistiken
                materials = section.get('materials', [])
                # Task-Type-Trennung: Separate Queries für Regular und Mastery Tasks
                regular_tasks, _ = get_regular_tasks_for_section(section['id'])
                mastery_tasks, _ = get_mastery_tasks_for_section(section['id'])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"📚 {len(materials)}")
                with col2:
                    st.caption(f"✏️ {len(regular_tasks)}")
                with col3:
                    st.caption(f"🎯 {len(mastery_tasks)}")
                
                # Gruppierte Inhalte mit Buttons
                render_section_contents(section, materials, regular_tasks, mastery_tasks)
        
        # Neuer Abschnitt Button
        if st.button("➕ Neuer Abschnitt", use_container_width=True):
            # Handler für neuen Abschnitt
    
    return selected_course, selected_unit, selected_section
```

### Schritt 2: Lerneinheiten-Seite anpassen (1.5h)
**Datei:** `app/pages/2_Lerneinheiten.py`

**Änderungen:**
1. Aufruf mit `show_section_navigation=True`
2. Entfernen der Split-View (Columns)
3. Quick Actions Bar über dem Detail-Editor
4. Import von `structure_tree` entfernen

**Code-Änderungen:**
```python
# Sidebar mit erweiterter Navigation
selected_course, selected_unit, selected_section = render_sidebar_with_course_selection(
    teacher_id,
    show_unit_selection=True,
    show_section_navigation=True  # NEU
)

# Hauptbereich ohne Split-View
st.title("📚 Lerneinheiten")

# Quick Actions Bar (wenn Abschnitt ausgewählt)
if selected_section:
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("➕ 📄 Neues Material", use_container_width=True):
            state.creating_type = 'material'
            st.rerun()
    with col2:
        if st.button("➕ ✏️ Neue Aufgabe", use_container_width=True):
            state.creating_type = 'task'
            st.rerun()
    with col3:
        if st.button("➕ 🎯 Neuer Wissensfestiger", use_container_width=True):
            state.creating_type = 'mastery'
            st.rerun()
    st.divider()

# Detail-Editor mit voller Breite
if state.selected_item:
    render_detail_editor(unit_id)
else:
    render_empty_state()
```

### Schritt 3: Editor auf volle Breite anpassen (1h)
**Datei:** `app/components/detail_editor.py`

**Änderungen:**
1. Entferne Split-View aus Hauptseite
2. Vergrößere Textareas (height 300 → 400+)
3. Verwende `use_container_width=True` konsequent
4. Mehr Whitespace zwischen Elementen

**Beispiel-Anpassungen:**
```python
# Vorher:
new_content = st.text_area("Inhalt", height=300)

# Nachher:
new_content = st.text_area(
    "Inhalt (Markdown)", 
    height=400,
    help="Unterstützt Markdown-Formatierung"
)
st.markdown("")  # Extra Whitespace
```

### Schritt 4: Structure Tree entfernen (0.5h)
**Dateien zu löschen/anpassen:**
1. `app/components/structure_tree.py` - komplett löschen
2. `app/components/__init__.py` - Import entfernen
3. Alle Referenzen zu `render_structure_tree` entfernen

### Schritt 5: Inline-Erstellung implementieren (1h)
**Datei:** `app/components/detail_editor.py`

**Änderungen:**
1. Neuer Erstellungsmodus basierend auf Session State
2. Zeige Erstellungsformular wenn `state.creating_type` gesetzt
3. Nach Speichern: Reset des creating_type

**Code-Struktur:**
```python
def render_detail_editor(unit_id: str):
    state = UnitEditorState()
    
    # Erstellungsmodus?
    if state.creating_type:
        if state.creating_type == 'material':
            render_new_material_form(state.selected_section_id)
        elif state.creating_type == 'task':
            # Regular Tasks haben spezifische Felder: order_in_section, max_attempts
            render_new_regular_task_form(state.selected_section_id)
        elif state.creating_type == 'mastery':
            # Mastery Tasks haben keine zusätzlichen Felder (Spaced Repetition verwaltet Wiederholungen)
            render_new_mastery_task_form(state.selected_section_id)
        return
    
    # Normaler Editor-Modus
    # ... bestehender Code ...
```

### Schritt 6: Testing & Polish (1h)
1. Teste alle Workflows
2. Prüfe Backward-Compatibility
3. Optimiere Loading States
4. Verfeinere Fehlermeldungen
5. Dokumentiere Breaking Changes (falls vorhanden)

### Schritt 7: DB Query Funktionen ergänzen (0.5h)
**Datei:** `app/utils/db_queries.py`

**Neue Funktionen hinzufügen:**
```python
def get_regular_tasks_for_section(section_id: str) -> tuple[list[dict], str | None]:
    """
    Holt alle regulären Aufgaben eines Abschnitts.
    Nutzt die all_regular_tasks View aus der Task-Type-Trennung.
    """
    try:
        client = get_user_supabase_client()
        response = client.table('all_regular_tasks')\
            .select('*')\
            .eq('section_id', section_id)\
            .order('order_in_section')\
            .execute()
        
        if hasattr(response, 'data'):
            return response.data, None
        return [], f"Fehler beim Abrufen der regulären Aufgaben: {getattr(response, 'error', 'Unbekannter Fehler')}"
    except Exception as e:
        return [], f"Exception: {str(e)}"

def get_mastery_tasks_for_section(section_id: str) -> tuple[list[dict], str | None]:
    """
    Holt alle Wissensfestiger-Aufgaben eines Abschnitts.
    Nutzt die all_mastery_tasks View aus der Task-Type-Trennung.
    """
    try:
        client = get_user_supabase_client()
        response = client.table('all_mastery_tasks')\
            .select('*')\
            .eq('section_id', section_id)\
            .execute()
        
        if hasattr(response, 'data'):
            return response.data, None
        return [], f"Fehler beim Abrufen der Mastery-Aufgaben: {getattr(response, 'error', 'Unbekannter Fehler')}"
    except Exception as e:
        return [], f"Exception: {str(e)}"
```

## Nicht-Ziele (Out of Scope)
- Drag & Drop Sortierung
- Mobile Optimierung
- Neue Datenbank-Strukturen
- Breaking Changes an APIs

## Erfolgsmetriken
- [x] Alle Formulare nutzen volle Breite
- [x] Mastery-Aufgaben sind visuell getrennt
- [x] Keine Popups für Hauptaktionen
- [x] Code bleibt unter 200 Zeilen pro Änderung
- [x] Bestehende Tests laufen weiter

## Implementierungsstatus (Stand: 2025-09-03)

### ✅ Phase 1 Abgeschlossen: UI-Überarbeitung
1. **DB Query Funktionen für Task-Type-Trennung** - `get_regular_tasks_for_section()`, `get_mastery_tasks_for_section()`
2. **Sidebar-Navigation erweitert** - Abschnitte mit aufklappbaren Inhalten, klickbare Navigation
3. **Vollbreite UI ohne Split-View** - Lerneinheiten-Seite umgestellt, Quick Actions Bar
4. **Detail-Editor UI-Verbesserungen** - Größere Textareas (400px), extra Whitespace
5. **Structure Tree entfernt** - Komponente gelöscht, Funktionalität in Sidebar integriert
6. **Material- und Task-Anzeige** - Funktioniert perfekt für alle Content-Typen
7. **Separate Mastery-Task-Editoren** - Eigener Editor ohne Aufgabentyp-Wechsel, mit Bewertungskriterien
8. **Task-Type-Trennung Integration** - Regular vs. Mastery Tasks klar getrennt

**Ergebnis:** UI ist perfekt, Navigation funktioniert, Anzeige aller Content-Typen ohne Fehler.

### ✅ Phase 2 Abgeschlossen: Funktionale Inline-Erstellung

**Status:** Alle Erstellungsformulare sind funktional implementiert mit sauberer Domain-Driven Design Architektur.

#### ✅ **Section-ID Transfer Problem** - GELÖST
- **Problem:** Quick Actions Bar setzte `creating_type` aber keine `selected_section_id`
- **Fix:** Section-Context von Sidebar zu Quick Actions übertragen (`selected_section['id']` in Session State setzen)
- **Datei:** `app/pages/2_Lerneinheiten.py:175,180,185`

#### ✅ **Abschnitt-Erstellung** - IMPLEMENTIERT  
- **Problem:** "Neuer Abschnitt" Button hatte keinen Handler/Formular
- **Fix:** `render_new_section_form()` mit vollständiger DB-Integration implementiert
- **Datei:** `app/components/detail_editor.py:498-547` (50 Zeilen)
- **Integration:** Verwendet `create_section()` mit automatischem Order-Index

#### ✅ **DB-Integration Material-Erstellung** - IMPLEMENTIERT
- **Problem:** Material-Formulare zeigten nur Platzhalter `st.success("Erstellt!")`
- **Fix:** Vollständige JSON-Integration in `unit_section.materials` Array
- **Features:** File-Upload zu Supabase Storage, Path Traversal Protection, 20MB Limit
- **Datei:** `app/components/detail_editor.py:418-498` (80 Zeilen)

#### ✅ **DB-Integration Task-Erstellung** - IMPLEMENTIERT + REFACTORED  
- **Problem:** Task-Formulare waren Platzhalter ohne DB-Operationen
- **Fix:** Saubere Domain-Driven Design Implementation
- **Refactoring:** Separate Funktionen statt `is_mastery` Flag:
  - `create_regular_task()` für Regular Tasks (mit `order_in_section`, `max_attempts`)
  - `create_mastery_task()` für Mastery Tasks (ohne zusätzliche Felder)
  - Legacy `create_task_in_new_structure()` als Backward-Compatibility Wrapper
- **Dateien:** 
  - `app/utils/db_queries.py:44-156` (112 Zeilen neue Funktionen)
  - `app/components/detail_editor.py:552-623` (Task-Erstellungslogik)

#### ✅ **Editor Speichern/Löschen** - FUNKTIONAL GEMACHT
- **Problem:** Material/Task-Editoren hatten Placeholder-Handler
- **Fix:** Vollständige DB-Integration für alle Content-Typen
- **Regular Task Editor:** Verwendet `update_task()` ohne `is_mastery` Flag
- **Mastery Task Editor:** Vollständig funktional mit `update_task()` und `delete_task()`
- **Material Editor:** Bereits vollständig implementiert (war schon funktional)

### ✅ Phase 3 VOLLSTÄNDIG: Quick Actions Bar & Editoren - IMPLEMENTIERT

**Problem:** Quick Actions Bar Buttons waren nicht sichtbar und Editoren hatten Konfigurationsfehler.

**Root Causes & Fixes:**
1. **Quick Actions Bar unsichtbar:** `selected_section` wurde nur bei Item-Clicks gesetzt, nicht bei Abschnitts-Auswahl
   - **Fix:** "⚡ Auswählen"-Button in Sidebar für direkte Abschnitts-Auswahl
   - **Session State Wiederherstellung:** `selected_section` wird aus Session State restauriert

2. **Aufgabentyp-Feld in Editoren:** Task-Type-Trennung war nicht vollständig umgesetzt
   - **Fix:** Aufgabentyp-Dropdowns aus Regular/Mastery Task Editoren entfernt
   - **Standard task_type:** Verwendet 'text' als Default ohne User-Input

3. **Fehlende Kriterien-Felder:** Bewertungskriterien waren nur in bestehenden Editoren, nicht in Erstellungsformularen
   - **Fix:** 5 Kriterien-Eingabefelder zu Regular/Mastery Task Erstellungsformularen hinzugefügt
   - **DB-Integration:** `assessment_criteria` Parameter korrekt an create-Funktionen übergeben

**Implementierte Fixes:**
- `app/components/ui_components.py:178-184` - "⚡ Auswählen"-Button für Abschnitts-Auswahl
- `app/components/ui_components.py:148-153` - Session State Wiederherstellung für `selected_section`
- `app/components/detail_editor.py:286,806` - Aufgabentyp-Felder aus Editoren entfernt
- `app/components/detail_editor.py:510-520,583-593` - Kriterien-Felder in Erstellungsformulare
- `app/components/detail_editor.py:558,615` - `assessment_criteria` DB-Integration

### 📁 Veränderte Dateien Phase 2 (2025-09-03)

**Hauptimplementierung:**
```
app/pages/2_Lerneinheiten.py           - Quick Actions Bar Section-ID Transfer (3 Zeilen geändert)
app/components/detail_editor.py        - Komplette funktionale Erstellung (~200 Zeilen hinzugefügt)
app/utils/db_queries.py                - Domain-Driven Design Refactoring (112 Zeilen neue Funktionen)
```

**Probleme & Lösungen:**
1. **Import-Fehler:** `get_user_supabase_client` Pfad korrigiert → `utils.session_client`
2. **is_mastery Flag entfernt:** Saubere Domain-Trennung durch separate `create_regular_task()` / `create_mastery_task()` 
3. **File-Upload Security:** Path Traversal Protection, Filename Sanitization, 20MB Limits
4. **Mastery Task Editor Platzhalter:** Vollständige `update_task()` / `delete_task()` Integration
5. **Task-Type-Trennung Compliance:** Verwendung der neuen Tabellen-Struktur ohne `is_mastery` Flag

**Code-Quality Verbesserungen:**
- Domain-Driven Design: Separate Funktionen für Regular/Mastery Tasks
- Saubere Parameter-Interfaces ohne Boolean-Flags
- Backward-Compatibility durch Legacy-Wrapper
- Umfassende Error-Handling mit Rollback-Logic

## Risiken & Mitigationen
1. **Sidebar wird zu lang**
   - Mitigation: Collapsed Expander als Default
   
2. **Performance bei vielen Abschnitten**
   - Mitigation: Lazy Loading später hinzufügen

3. **Nutzer vermissen alte UI**
   - Mitigation: Schrittweise Einführung, Feedback sammeln

## Geschätzte Gesamtzeit
- Schritt 1: Sidebar erweitern (2h)
- Schritt 2: Lerneinheiten-Seite (1.5h)
- Schritt 3: Editor anpassen (1h)
- Schritt 4: Structure Tree entfernen (0.5h)
- Schritt 5: Inline-Erstellung (1h)
- Schritt 6: Testing & Polish (1h)
- Schritt 7: DB Query Funktionen (0.5h)
- **Gesamt: ~7.5h**

## Breaking Changes & Migrationshinweise
1. **Return Type Change:** `render_sidebar_with_course_selection` gibt jetzt 3 statt 2 Werte zurück
   - Betrifft nur Lerneinheiten-Seite (verwendet neuen Parameter)
   - Andere Seiten nicht betroffen (default Parameter)
   
2. **Gelöschte Komponente:** `structure_tree.py` wird entfernt
   - Funktionalität in Sidebar integriert
   - Keine externen Abhängigkeiten

## Wartungshinweise
- Keine komplexen State-Managements
- Streamlit-native Komponenten bevorzugt
- Jede Funktion < 50 Zeilen
- Klare Kommentare bei UI-Entscheidungen
- Backward-Compatibility durch optionale Parameter

## Task-Type-Trennung Integration

### Vorteile durch die abgeschlossene Migration
1. **Klarere Queries:** Keine `is_mastery` Filter mehr nötig
2. **Bessere Performance:** Separate Views mit optimierten Indizes
3. **Type Safety:** Regular und Mastery Tasks haben klar definierte Strukturen
4. **Zukunftssicher:** Einfache Erweiterung um task-typ-spezifische Features

### Wichtige Änderungen gegenüber ursprünglichem Plan
1. **Separate Query-Funktionen:** `get_regular_tasks_for_section()` und `get_mastery_tasks_for_section()`
2. **Keine is_mastery Checks:** Views filtern automatisch
3. **Task-Erstellung:** Nutzt neue `create_task_in_new_structure()` Funktion
4. **Spezifische Formulare:** Regular Tasks haben `order_in_section` und `max_attempts` Felder

## Phase 2 Detailplan: Funktionale Inline-Erstellung

### Schritt 1: Section-ID Transfer reparieren (30 min)
**Problem:** Quick Actions bekommen keine Section-ID
```python
# In ui_components.py - Sidebar Navigation
if st.button("➕ 📄 Neues Material"):
    st.session_state.selected_section_id = section['id']  # ← FEHLT
    st.session_state.creating_type = 'material'
```

### Schritt 2: Abschnitt-Erstellungsformular (45 min)  
**Problem:** `creating_section = True` hat keinen Handler
```python 
# In detail_editor.py - Erstellungsmodus Check
if hasattr(st.session_state, 'creating_section') and st.session_state.creating_section:
    render_new_section_form(get_selected_unit_id())
    return
```

### Schritt 3: DB-Integration Material-Erstellung (1h)
**Problem:** Placeholder `st.success()` statt echte DB-Ops
- `render_new_material_form()` → `update_section_materials()` Integration
- File-Upload für Material-Typ 'file' 
- JSON-Update in unit_section.materials Array

### Schritt 4: DB-Integration Task-Erstellung (1.5h)  
**Problem:** Placeholder-Formulare ohne DB-Operationen
- `render_new_regular_task_form()` → `create_task_in_new_structure()` 
- `render_new_mastery_task_form()` → Mastery-spezifische Erstellung
- Task-Type-Trennung beim Erstellen korrekt implementieren

### Schritt 5: Speichern/Löschen aktivieren (1h)
**Problem:** Editor-Formulare haben Placeholder-Handler  
- Material-Editor → `update_section_materials()` 
- Task-Editor → `update_task()` + `delete_task()`
- Mastery-Task-Editor → angepasste Speicher-Logik

**Geschätzte Gesamtzeit Phase 2: ~4h**

## ✅ STATUS: **VOLLSTÄNDIG IMPLEMENTIERT** (2025-09-03)

**Alle Phasen abgeschlossen:**
- ✅ **Phase 1:** UI-Überarbeitung (Sidebar-Navigation, Vollbreite, Structure Tree entfernt)  
- ✅ **Phase 2:** Funktionale Inline-Erstellung (Material/Task/Mastery DB-Integration)
- ✅ **Phase 3:** Quick Actions Bar Sichtbarkeit & Editor-Fixes (Aufgabentyp entfernt, Kriterien-Felder hinzugefügt)

**End-to-End Funktionalität bestätigt:**
- Abschnitte auswählbar über "⚡ Auswählen"-Button
- Quick Actions Bar sichtbar und funktional  
- Material/Task/Mastery-Task Erstellung komplett funktional
- Editoren ohne Aufgabentyp-Feld, mit 5 Kriterien-Eingabefeldern
- Task-Type-Trennung vollständig integriert

**Feature ist production-ready für Lehrer.**