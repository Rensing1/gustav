# app/components/course_users.py
import streamlit as st
from utils.db_queries import (
    get_students_in_course,
    get_teachers_in_course,
    get_users_by_role,
    add_user_to_course,
    remove_user_from_course
)

def render_course_users_tab(course_id: str, course_name: str, current_teacher_id: str):
    """Rendert den Tab für Nutzerverwaltung.
    
    Args:
        course_id: ID des ausgewählten Kurses
        course_name: Name des Kurses
        current_teacher_id: ID des aktuellen Lehrers (für Sicherheitschecks)
    """
    col1, col2 = st.columns(2)
    
    with col1:
        render_student_management(course_id)
    
    with col2:
        render_teacher_management(course_id, current_teacher_id)

def render_student_management(course_id: str):
    """Rendert die Schülerverwaltung."""
    st.markdown("#### 👥 Schüler verwalten")
    
    # Aktuelle Schüler laden
    current_students, error = get_students_in_course(course_id)
    if error:
        st.error(f"Fehler beim Laden der Schüler: {error}")
        current_students = []
    
    # Zeige eingeschriebene Schüler
    st.markdown("**Eingeschriebene Schüler:**")
    if current_students:
        for student in current_students:
            st.caption(f"• {student.get('email', student['id'])}")
        st.caption(f"_Gesamt: {len(current_students)} Schüler_")
    else:
        st.caption("_Keine Schüler eingeschrieben_")
    
    # Schüler hinzufügen/entfernen
    with st.popover("👥 Schüler verwalten", use_container_width=True):
        render_student_management_form(course_id, current_students)

def render_student_management_form(course_id: str, current_students: list):
    """Formular für Schülerverwaltung."""
    # Alle Schüler laden
    all_students, error = get_users_by_role('student')
    if error:
        st.error(f"Fehler beim Laden aller Schüler: {error}")
        return
    
    current_ids = {s['id'] for s in current_students}
    
    # Tab für Hinzufügen/Entfernen
    tab_add, tab_remove = st.tabs(["Hinzufügen", "Entfernen"])
    
    with tab_add:
        available_students = [s for s in all_students if s['id'] not in current_ids]
        
        if available_students:
            student_options = {s['id']: s['email'] for s in available_students}
            
            selected_add = st.multiselect(
                "Schüler auswählen:",
                options=list(student_options.keys()),
                format_func=lambda x: student_options[x],
                key=f"add_students_{course_id}"
            )
            
            if st.button("Hinzufügen", key=f"btn_add_students_{course_id}", use_container_width=True):
                if selected_add:
                    success_count = 0
                    for student_id in selected_add:
                        success, _ = add_user_to_course(course_id, student_id, 'student')
                        if success:
                            success_count += 1
                    
                    if success_count > 0:
                        st.success(f"{success_count} Schüler hinzugefügt!")
                        st.rerun()
                else:
                    st.warning("Keine Schüler ausgewählt.")
        else:
            st.info("Alle Schüler sind bereits eingeschrieben.")
    
    with tab_remove:
        if current_students:
            student_options = {s['id']: s['email'] for s in current_students}
            
            selected_remove = st.multiselect(
                "Schüler auswählen:",
                options=list(student_options.keys()),
                format_func=lambda x: student_options[x],
                key=f"remove_students_{course_id}"
            )
            
            if st.button("Entfernen", key=f"btn_remove_students_{course_id}", use_container_width=True):
                if selected_remove:
                    success_count = 0
                    for student_id in selected_remove:
                        success, _ = remove_user_from_course(course_id, student_id, 'student')
                        if success:
                            success_count += 1
                    
                    if success_count > 0:
                        st.success(f"{success_count} Schüler entfernt!")
                        st.rerun()
                else:
                    st.warning("Keine Schüler ausgewählt.")
        else:
            st.info("Keine Schüler zum Entfernen vorhanden.")

def render_teacher_management(course_id: str, current_teacher_id: str):
    """Rendert die Lehrerverwaltung."""
    st.markdown("#### 👨‍🏫 Lehrer verwalten")
    
    # Aktuelle Lehrer laden
    current_teachers, error = get_teachers_in_course(course_id)
    if error:
        st.error(f"Fehler beim Laden der Lehrer: {error}")
        current_teachers = []
    
    # Zeige zugewiesene Lehrer
    st.markdown("**Zugewiesene Lehrer:**")
    if current_teachers:
        for teacher in current_teachers:
            email = teacher.get('email', teacher['id'])
            if teacher['id'] == current_teacher_id:
                st.caption(f"• {email} _(Sie)_")
            else:
                st.caption(f"• {email}")
        st.caption(f"_Gesamt: {len(current_teachers)} Lehrer_")
    else:
        st.caption("_Keine Lehrer zugewiesen_")
    
    # Lehrer hinzufügen/entfernen
    with st.popover("👨‍🏫 Lehrer verwalten", use_container_width=True):
        render_teacher_management_form(course_id, current_teachers, current_teacher_id)

def render_teacher_management_form(course_id: str, current_teachers: list, current_teacher_id: str):
    """Formular für Lehrerverwaltung."""
    # Alle Lehrer laden
    all_teachers, error = get_users_by_role('teacher')
    if error:
        st.error(f"Fehler beim Laden aller Lehrer: {error}")
        return
    
    current_ids = {t['id'] for t in current_teachers}
    
    # Tab für Hinzufügen/Entfernen
    tab_add, tab_remove = st.tabs(["Hinzufügen", "Entfernen"])
    
    with tab_add:
        available_teachers = [t for t in all_teachers if t['id'] not in current_ids]
        
        if available_teachers:
            teacher_options = {t['id']: t['email'] for t in available_teachers}
            
            selected_add = st.multiselect(
                "Lehrer auswählen:",
                options=list(teacher_options.keys()),
                format_func=lambda x: teacher_options[x],
                key=f"add_teachers_{course_id}"
            )
            
            if st.button("Hinzufügen", key=f"btn_add_teachers_{course_id}", use_container_width=True):
                if selected_add:
                    success_count = 0
                    for teacher_id in selected_add:
                        success, _ = add_user_to_course(course_id, teacher_id, 'teacher')
                        if success:
                            success_count += 1
                    
                    if success_count > 0:
                        st.success(f"{success_count} Lehrer hinzugefügt!")
                        st.rerun()
                else:
                    st.warning("Keine Lehrer ausgewählt.")
        else:
            st.info("Alle Lehrer sind bereits zugewiesen.")
    
    with tab_remove:
        # Prüfe ob es nur einen Lehrer gibt
        if len(current_teachers) == 1 and current_teachers[0]['id'] == current_teacher_id:
            st.warning("Sie sind der einzige Lehrer in diesem Kurs und können sich nicht selbst entfernen.")
        elif current_teachers:
            # Filtere den aktuellen Lehrer raus, wenn er der einzige ist
            removable_teachers = current_teachers
            if len(current_teachers) == 1:
                removable_teachers = []
            
            if removable_teachers:
                teacher_options = {t['id']: t['email'] for t in removable_teachers}
                
                selected_remove = st.multiselect(
                    "Lehrer auswählen:",
                    options=list(teacher_options.keys()),
                    format_func=lambda x: teacher_options[x],
                    key=f"remove_teachers_{course_id}"
                )
                
                if st.button("Entfernen", key=f"btn_remove_teachers_{course_id}", use_container_width=True):
                    if selected_remove:
                        # Sicherheitscheck: Verhindere Selbstentfernung als letzter Lehrer
                        if current_teacher_id in selected_remove and len(current_teachers) <= 1:
                            st.error("Sie können sich nicht als letzten Lehrer entfernen.")
                        else:
                            success_count = 0
                            for teacher_id in selected_remove:
                                # Skip wenn es der letzte Lehrer wäre
                                if teacher_id == current_teacher_id and len(current_teachers) - len(selected_remove) < 1:
                                    continue
                                    
                                success, _ = remove_user_from_course(course_id, teacher_id, 'teacher')
                                if success:
                                    success_count += 1
                            
                            if success_count > 0:
                                st.success(f"{success_count} Lehrer entfernt!")
                                st.rerun()
                    else:
                        st.warning("Keine Lehrer ausgewählt.")
            else:
                st.info("Keine Lehrer können entfernt werden.")
        else:
            st.info("Keine Lehrer zum Entfernen vorhanden.")