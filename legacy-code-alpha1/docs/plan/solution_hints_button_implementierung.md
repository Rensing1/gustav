# Implementierungsplan: "Lösungshinweise anzeigen" Button

## Übersicht
Implementierung eines Buttons zum Anzeigen von Lösungshinweisen für Schüler, der nur erscheint wenn:
- Bei Regular Tasks: Keine weiteren Versuche mehr möglich sind (max_attempts erreicht)
- Bei Mastery Tasks: Nach jeder Abgabe (da es keine max_attempts Beschränkung gibt)

## Status der Analyse

### Vorhandene Infrastruktur
1. **Datenbank**:
   - `solution_hints` TEXT Feld existiert in `task_base` Tabelle
   - Wurde eingeführt in Migration `20250801123332_split_feedback_focus_into_criteria_and_hints.sql`
   - Wird bereits von beiden relevanten RPC-Funktionen zurückgegeben:
     - `get_published_section_details_for_student` (Zeile 80)
     - `get_next_mastery_task_or_unviewed_feedback` (Zeile 75)

2. **Lehrer-Interface**:
   - Eingabefeld für Lösungshinweise existiert in `/app/components/detail_editor.py`
   - Zeilen 372, 608, 673, 929: Text-Area für solution_hints Input

3. **Schüler-Interface**:
   - Regular Tasks: `/app/pages/3_Meine_Aufgaben.py`
   - Mastery Tasks: `/app/pages/7_Wissensfestiger.py`

## Implementierungsdetails

### 1. Regular Tasks - `/app/pages/3_Meine_Aufgaben.py`

**Position**: Nach Zeile 264 (nach der Prüfung der verbleibenden Versuche)

```python
# Nach Zeile 264 einfügen:
# Zeige Lösungshinweise-Button wenn keine Versuche mehr übrig sind
if remaining == 0 and task.get('solution_hints'):
    # Toggle-State im Session State verwalten
    hint_key = f"show_hints_{task_id}"
    if hint_key not in st.session_state:
        st.session_state[hint_key] = False
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("💡 Lösungshinweise anzeigen", key=f"btn_hints_{task_id}", use_container_width=True):
            st.session_state[hint_key] = not st.session_state[hint_key]
    
    if st.session_state[hint_key]:
        with st.expander("Lösungshinweise vom Lehrer", expanded=True):
            st.info(task['solution_hints'])
```

### 2. Mastery Tasks - `/app/pages/7_Wissensfestiger.py`

**Position**: Nach dem Feedback-Bereich (nach Zeile 262), innerhalb des `if course_state['answer_submitted']:` Blocks

```python
# Im answer_submitted Block einfügen:
# Zeige Lösungshinweise-Button nach Abgabe
if task.get('solution_hints'):
    st.divider()
    
    # Toggle-State im Session State verwalten
    hint_key = f"show_mastery_hints_{selected_course_id}_{task['id']}"
    if hint_key not in st.session_state:
        st.session_state[hint_key] = False
    
    if st.button("💡 Lösungshinweise anzeigen", key=f"btn_mastery_hints_{task['id']}", use_container_width=True):
        st.session_state[hint_key] = not st.session_state[hint_key]
    
    if st.session_state[hint_key]:
        with st.container(border=True):
            st.markdown("### 💡 Lösungshinweise")
            st.info(task['solution_hints'])
```

### 3. Session State Management

**Wichtige Überlegungen**:
- Keys müssen eindeutig sein (task_id verwenden)
- Bei Mastery Tasks zusätzlich course_id einbeziehen
- State sollte erhalten bleiben während der Session
- Bei Kurswechsel sollte der State zurückgesetzt werden

### 4. UI/UX Verbesserungen

1. **Visuelle Gestaltung**:
   - Button mit 💡 Icon
   - Info-Box für die Hinweise
   - Klare Abgrenzung vom restlichen Content

2. **Conditional Rendering**:
   - Button nur zeigen wenn `solution_hints` nicht leer ist
   - Bei Regular Tasks: nur wenn `remaining == 0`
   - Bei Mastery Tasks: nur wenn `answer_submitted == True`

3. **Accessibility**:
   - Aussagekräftige Button-Beschriftung
   - Expandable Container für bessere Übersicht

## Test-Szenarien

1. **Regular Tasks**:
   - Task ohne solution_hints → kein Button
   - Task mit solution_hints aber remaining > 0 → kein Button
   - Task mit solution_hints und remaining = 0 → Button sichtbar
   - Button-Toggle funktioniert korrekt

2. **Mastery Tasks**:
   - Task ohne solution_hints → kein Button
   - Task mit solution_hints vor Abgabe → kein Button
   - Task mit solution_hints nach Abgabe → Button sichtbar
   - State bleibt bei Feedback-Updates erhalten

## Nächste Schritte

1. Implementierung in `/app/pages/3_Meine_Aufgaben.py`
2. Implementierung in `/app/pages/7_Wissensfestiger.py`
3. Manuelles Testen beider Szenarien
4. Optional: Erweiterte Formatierung für Markdown in solution_hints

## Offene Fragen

- Sollen Lösungshinweise auch im Lehrer-Feedback-Bereich sichtbar sein?
- Brauchen wir Analytics darüber, wie oft Hinweise angezeigt werden?
- Soll der Toggle-State zwischen Sessions persistiert werden?