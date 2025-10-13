"""
Standardisierte UI-Komponenten gemäß GUSTAV Styleguide.

Diese Komponenten sorgen für ein konsistentes Design über alle Seiten.
"""

import streamlit as st
from typing import Optional, List, Any, Callable, Tuple
from utils.db_queries import (
    get_student_courses, get_courses_by_creator, get_assigned_units_for_course,
    get_sections_for_unit, get_regular_tasks_for_section, get_mastery_tasks_for_section
)
from utils.course_state import get_selected_course_id, set_selected_course_id
from utils.unit_state import get_selected_unit_id, set_selected_unit_id
from utils.cache_manager import CacheManager


def render_page_header(title: str, emoji: str = "📄") -> None:
    """
    Rendert einen standardisierten Seitentitel.
    
    Args:
        title: Der Seitentitel
        emoji: Das Emoji vor dem Titel
    """
    st.title(f"{emoji} {title}")


def render_sidebar_with_course_selection(
    user_id: str,
    show_unit_selection: bool = True,
    additional_content: Optional[Callable] = None,
    show_section_navigation: bool = False
) -> Tuple[Optional[Any], Optional[Any], Optional[Any]]:
    """
    Rendert die standardisierte Sidebar mit Logo, User-Info und Kurs-/Einheitenauswahl.
    
    Args:
        user_id: Die User-ID
        show_unit_selection: Ob die Einheitenauswahl angezeigt werden soll
        additional_content: Funktion für zusätzlichen Sidebar-Content
        show_section_navigation: Ob die Abschnitts-Navigation angezeigt werden soll
        
    Returns:
        Tuple von (selected_course, selected_unit, selected_section)
    """
    with st.sidebar:
        # Kursauswahl (ohne Subheader für kompakteres Design)
        st.markdown("**Kurs wählen:**")
        
        # Hole Kurse mit Cache-Manager (90 Min Cache)
        try:
            courses = CacheManager.get_user_courses(force_refresh=False)
            if courses is None:
                courses = []
        except Exception as e:
            st.error(f"Fehler beim Laden der Kurse: {e}")
            courses = []
        
        # Lade gespeicherten Kurs (mit Fallback auf Cache-Manager)
        saved_course_id = get_selected_course_id()
        
        # Fallback: User Selection Persistence (90 Min Cache)
        if not saved_course_id:
            cached_course_id, _ = CacheManager.get_user_selection()
            if cached_course_id:
                saved_course_id = cached_course_id
        
        # Finde den Index des gespeicherten Kurses
        course_index = 0
        if saved_course_id and courses:
            for i, course in enumerate(courses):
                if course['id'] == saved_course_id:
                    course_index = i + 1
                    break
        
        selected_course = st.selectbox(
            "Kurs wählen",
            options=[None] + courses,
            format_func=lambda x: "Bitte wählen..." if x is None else x['name'],
            index=course_index,
            key="sidebar_course_selector",
            label_visibility="collapsed"
        )
        
        selected_unit = None
        
        if selected_course:
            # Speichere Auswahl in beiden Systemen
            set_selected_course_id(selected_course['id'])
            # Update auch Cache-Manager für 90min Persistence
            CacheManager.save_user_selection(selected_course['id'], None)
            
            if show_unit_selection:
                # Lerneinheiten (kompaktes Design)
                st.markdown("**Lerneinheit wählen:**")
                
                # Hole Lerneinheiten mit Cache-Manager (10 Min Cache)
                try:
                    units = CacheManager.get_course_units(selected_course['id'], force_refresh=False)
                    if units is None:
                        units = []
                except Exception as e:
                    st.error(f"Fehler beim Laden der Lerneinheiten: {e}")
                    units = []
                
                # Lade gespeicherte Einheit (mit Fallback auf Cache-Manager)
                saved_unit_id = get_selected_unit_id()
                
                # Fallback: User Selection Persistence (90 Min Cache)
                if not saved_unit_id:
                    _, cached_unit_id = CacheManager.get_user_selection()
                    if cached_unit_id:
                        saved_unit_id = cached_unit_id
                
                # Finde den Index der gespeicherten Einheit
                unit_index = 0
                if saved_unit_id and units:
                    for i, unit in enumerate(units):
                        if unit['id'] == saved_unit_id:
                            unit_index = i + 1
                            break
                
                selected_unit = st.selectbox(
                    "Einheit wählen",
                    options=[None] + units,
                    format_func=lambda x: "Bitte wählen..." if x is None else x['title'],
                    index=unit_index,
                    key="sidebar_unit_selector",
                    label_visibility="collapsed"
                )
                
                if selected_unit:
                    # Speichere Auswahl in beiden Systemen
                    set_selected_unit_id(selected_unit['id'])
                    # Update Cache-Manager mit vollständiger Selection
                    CacheManager.save_user_selection(selected_course['id'], selected_unit['id'])
        
        selected_section = None
        
        if show_section_navigation and selected_unit:
            st.divider()
            st.markdown("**📚 Abschnitte**")
            
            # Lade Abschnitte
            sections, error = get_sections_for_unit(selected_unit['id'])
            
            # Wiederherstellen der ausgewählten Section aus Session State
            if hasattr(st.session_state, 'selected_section_id') and st.session_state.selected_section_id:
                for section in sections if not error else []:
                    if section['id'] == st.session_state.selected_section_id:
                        selected_section = section
                        break
            if error:
                st.error(f"Fehler beim Laden der Abschnitte: {error}")
                sections = []
            
            # Render Abschnitte als Expander
            for section in sections:
                with st.expander(f"📁 {section['title']}", expanded=False):
                    # Task-Type-Trennung: Separate Queries für Regular und Mastery Tasks
                    regular_tasks, _ = get_regular_tasks_for_section(section['id'])
                    mastery_tasks, _ = get_mastery_tasks_for_section(section['id'])
                    materials = section.get('materials', []) or []
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.caption(f"📚 {len(materials)}")
                    with col2:
                        st.caption(f"✏️ {len(regular_tasks)}")
                    with col3:
                        st.caption(f"🎯 {len(mastery_tasks)}")
                    with col4:
                        if st.button("⚡", key=f"select_section_{section['id']}", use_container_width=True):
                            st.session_state.selected_section_id = section['id']
                            st.session_state.selected_item_type = None
                            st.session_state.selected_item_id = None
                            selected_section = section
                            st.rerun()
                    
                    # Auswählbare Inhalte
                    st.markdown("**Materialien:**")
                    for material in materials:
                        if st.button(f"📄 {material.get('title', 'Unbenannt')}", key=f"mat_{material['id']}", use_container_width=True):
                            st.session_state.selected_section_id = section['id']
                            st.session_state.selected_item_type = 'material'
                            st.session_state.selected_item_id = material['id']
                            selected_section = section
                            st.rerun()
                    
                    st.markdown("**Aufgaben:**")
                    for task in regular_tasks:
                        if st.button(f"✏️ {task.get('instruction', 'Unbenannte Aufgabe')[:30]}...", key=f"task_{task['id']}", use_container_width=True):
                            st.session_state.selected_section_id = section['id']
                            st.session_state.selected_item_type = 'task'
                            st.session_state.selected_item_id = task['id']
                            selected_section = section
                            st.rerun()
                    
                    st.markdown("**Wissensfestiger:**")
                    for task in mastery_tasks:
                        if st.button(f"🎯 {task.get('instruction', 'Unbenannter Wissensfestiger')[:30]}...", key=f"mastery_{task['id']}", use_container_width=True):
                            st.session_state.selected_section_id = section['id']
                            st.session_state.selected_item_type = 'mastery_task'
                            st.session_state.selected_item_id = task['id']
                            selected_section = section
                            st.rerun()
            
            # Neuer Abschnitt Button
            if st.button("➕ Neuer Abschnitt", use_container_width=True):
                st.session_state.creating_section = True
                st.rerun()
        
        # Zusätzlicher Content
        if additional_content and selected_course:
            st.divider()
            additional_content(selected_course, selected_unit)
    
    return selected_course, selected_unit, selected_section


def render_empty_state(message: str, help_text: Optional[str] = None) -> None:
    """
    Zeigt eine standardisierte Nachricht für leere Zustände.
    
    Args:
        message: Die Hauptnachricht
        help_text: Optionaler Hilfetext
    """
    st.info(f"ℹ️ {message}")
    if help_text:
        st.caption(help_text)


def render_card(
    title: str,
    content: Optional[str] = None,
    actions: Optional[List[dict]] = None,
    metrics: Optional[List[dict]] = None
) -> None:
    """
    Rendert eine standardisierte Karte.
    
    Args:
        title: Kartentitel
        content: Optionaler Textinhalt
        actions: Liste von Button-Definitionen [{"label": str, "key": str, "type": str}]
        metrics: Liste von Metriken [{"label": str, "value": str, "delta": str}]
    """
    with st.container(border=True):
        # Titel und Aktionen in einer Zeile
        if actions:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(title)
            with col2:
                for action in actions:
                    button_type = action.get("type", "secondary")
                    if button_type == "primary":
                        st.button(
                            action["label"],
                            key=action["key"],
                            type="primary",
                            use_container_width=True
                        )
                    else:
                        st.button(
                            action["label"],
                            key=action["key"],
                            use_container_width=True
                        )
        else:
            st.subheader(title)
        
        # Content
        if content:
            st.text(content)
        
        # Metriken
        if metrics:
            metric_row(metrics)


def render_metric_row(metrics: List[dict]) -> None:
    """
    Rendert eine Reihe von Metriken mit automatischem Column-Layout.
    
    Args:
        metrics: Liste von Metriken [{"label": str, "value": str, "delta": str}]
    """
    cols = st.columns(len(metrics))
    for i, metric in enumerate(metrics):
        with cols[i]:
            st.metric(
                metric["label"],
                metric["value"],
                metric.get("delta")
            )