# app/components/detail_editor.py
import streamlit as st
import uuid
import requests
import bleach
from utils.session_client import get_user_supabase_client
from utils.validators import sanitize_filename, validate_file_upload, ValidationError
from utils.db_queries import (
    update_section_materials,
    update_task,
    delete_task,
    create_section,
    get_sections_for_unit,
    create_regular_task,
    create_mastery_task,
    get_regular_tasks_for_section
)
from utils.unit_state import UnitEditorState

def render_detail_editor(unit_id: str):
    """Rendert die Detailansicht/Editor für das ausgewählte Element.
    
    Args:
        unit_id: ID der Lerneinheit
    """
    state = UnitEditorState()
    
    # Erstellungsmodus?
    if hasattr(st.session_state, 'creating_section') and st.session_state.creating_section:
        render_new_section_form(unit_id)
        return
    
    if hasattr(st.session_state, 'creating_type') and st.session_state.creating_type:
        if st.session_state.creating_type == 'material':
            render_new_material_form(getattr(st.session_state, 'selected_section_id', None))
        elif st.session_state.creating_type == 'task':
            render_new_regular_task_form(getattr(st.session_state, 'selected_section_id', None))
        elif st.session_state.creating_type == 'mastery':
            render_new_mastery_task_form(getattr(st.session_state, 'selected_section_id', None))
        return
    
    # Header für Detailansicht
    st.markdown("### DETAILANSICHT")
    
    # Prüfe Session State für ausgewähltes Element
    selected_item_id = getattr(st.session_state, 'selected_item_id', None)
    selected_item_type = getattr(st.session_state, 'selected_item_type', None)
    
    # Fallback auf UnitEditorState
    if not selected_item_id and state.selected_item:
        selected_item_id = state.selected_item.get('id')
        selected_item_type = state.selected_item.get('type')
    
    # Prüfe ob ein Element ausgewählt ist
    if not selected_item_id:
        render_empty_state()
        return
    
    # Rendere basierend auf dem Typ des ausgewählten Elements
    item_type = selected_item_type
    
    if item_type == 'section':
        render_section_details({'id': selected_item_id})
    elif item_type == 'material':
        render_material_editor_by_id(selected_item_id)
    elif item_type == 'task' or item_type == 'mastery_task':
        render_task_editor_by_id(selected_item_id)
    else:
        st.error(f"Unbekannter Element-Typ: {item_type}")

def render_empty_state():
    """Zeigt den leeren Zustand wenn nichts ausgewählt ist."""
    with st.container():
        st.info("👈 Wählen Sie links ein Element aus, um es hier zu bearbeiten")
        
        # Hilfreiche Tipps
        with st.expander("💡 Tipps zur Verwendung"):
            st.markdown("""
            **Navigation:**
            - Klicken Sie auf einen Abschnitt, um ihn auf-/zuzuklappen
            - Klicken Sie auf ein Material oder eine Aufgabe, um sie zu bearbeiten
            
            **Neue Inhalte erstellen:**
            - Nutzen Sie die ➕ Buttons im Strukturbaum
            - Abschnitte können Materialien und Aufgaben enthalten
            
            **Kurszuweisungen:**
            - Nutzen Sie den Button "Kurs zuweisen" oben, um diese Lerneinheit Kursen zuzuordnen
            """)

def render_section_details(selected_item: dict):
    """Zeigt Details eines Abschnitts an.
    
    Args:
        selected_item: Dictionary mit Abschnittsdaten
    """
    section = selected_item.get('data', {})
    
    st.markdown(f"#### 📁 {section.get('title', 'Unbenannter Abschnitt')}")
    
    # Statistiken
    col1, col2 = st.columns(2)
    with col1:
        materials_count = len(section.get('materials', []))
        st.metric("Materialien", materials_count)
    
    with col2:
        # TODO: Aufgaben zählen
        st.metric("Aufgaben", "—")
    
    # Abschnitts-Einstellungen
    with st.expander("⚙️ Abschnitts-Einstellungen"):
        st.info("Abschnitts-Einstellungen werden in einer späteren Version verfügbar sein.")
        # Hier könnten später Optionen wie:
        # - Abschnitt umbenennen
        # - Reihenfolge ändern
        # - Sichtbarkeitseinstellungen
        # hinzugefügt werden

def render_material_editor(selected_item: dict, unit_id: str):
    """Rendert den Editor für ein Material."""
    material = selected_item.get('data', {})
    section_id = selected_item.get('section_id')
    material_id = selected_item.get('id')
    
    from utils.db_queries import get_sections_for_unit
    sections, _ = get_sections_for_unit(unit_id)
    current_section = next((s for s in sections if s['id'] == section_id), None)
    
    if not current_section:
        st.error("Abschnitt nicht gefunden")
        return
    
    materials = current_section.get('materials', [])
    
    mat_type = material.get('type')
    type_icon = {"markdown": "📄", "link": "🔗", "file": "📁", "applet": "</>"}.get(mat_type, "📄")
    st.markdown(f"#### {type_icon} {material.get('title', 'Unbenanntes Material')}")
    
    with st.form(f"edit_material_{material_id}"):
        new_title = st.text_input("Titel", value=material.get('title', ''))
        
        new_content = None
        uploaded_file = None
        if mat_type == 'markdown':
            new_content = st.text_area(
                "Inhalt (Markdown)", 
                value=material.get('content', ''), 
                height=400,
                help="Unterstützt Markdown-Formatierung"
            )
            st.markdown("")  # Extra Whitespace
        elif mat_type == 'link':
            new_content = st.text_input("URL", value=material.get('content', ''))
        elif mat_type == 'file':
            st.caption("Laden Sie eine neue Datei hoch, um eine bestehende zu ersetzen.")
            uploaded_file = st.file_uploader("Datei auswählen", key=f"file_uploader_{material_id}")
            if material.get('filename'):
                st.info(f"Aktuelle Datei: `{material.get('filename')}`")
        elif mat_type == 'applet':
            new_content = st.text_area(
                "HTML/JS/CSS Code", 
                value=material.get('content', ''), 
                height=400,
                help="Fügen Sie hier den kompletten HTML-Code ein, inklusive <style> und <script> Tags."
            )

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            if st.form_submit_button("Abbrechen", use_container_width=True):
                st.rerun()
        with col2:
            save = st.form_submit_button("Speichern", type="primary", use_container_width=True)
        with col3:
            delete = st.form_submit_button("🗑️ Löschen", use_container_width=True)
        
        if save and new_title:
            updated_materials = []
            for mat in materials:
                if mat.get('id') == material_id:
                    updated_mat = mat.copy()
                    updated_mat['title'] = new_title.strip()

                    if mat_type == 'file' and uploaded_file is not None:
                        MAX_FILE_SIZE = 20 * 1024 * 1024
                        if uploaded_file.size > MAX_FILE_SIZE:
                            st.error(f"Datei zu groß. Max. 20 MB.")
                            return

                        from utils.session_client import get_user_supabase_client
                        from supabase_client import get_supabase_service_client
                        import re
                        from pathlib import Path
                        
                        file_bytes = uploaded_file.getvalue()
                        
                        # Rate limiting check
                        from utils.rate_limiter import check_upload_rate_limit, RateLimitExceeded
                        try:
                            check_upload_rate_limit(str(st.session_state.user.id), uploaded_file.size)
                        except RateLimitExceeded as e:
                            st.error(f"🚫 Upload-Limit erreicht: {str(e)}")
                            return
                        
                        # Validate and sanitize file
                        try:
                            validate_file_upload(uploaded_file)
                        except ValidationError as e:
                            st.error(str(e))
                            return
                        
                        # Filename Sanitization - Path Traversal Protection
                        safe_filename = sanitize_filename(uploaded_file.name)
                        file_path = f"unit_{unit_id}/section_{section_id}/{uuid.uuid4()}_{safe_filename}"
                        
                        # Use service client for upload (temporary RLS fix)
                        service_client = get_supabase_service_client()
                        if not service_client:
                            st.error("Service-Client nicht verfügbar. Bitte Administrator kontaktieren.")
                            return
                        
                        service_client.storage.from_("section_materials").upload(path=file_path, file=file_bytes)
                        
                        updated_mat['path'] = file_path
                        updated_mat['filename'] = uploaded_file.name
                        updated_mat['mime_type'] = uploaded_file.type
                    
                    elif mat_type in ['markdown', 'link', 'applet']:
                        # .strip() can break indentation in code, so we don't use it for applets
                        updated_mat['content'] = new_content if mat_type == 'applet' else new_content.strip()

                    updated_materials.append(updated_mat)
                else:
                    updated_materials.append(mat)
            
            success, error = update_section_materials(section_id, updated_materials)
            if success:
                st.success("Material gespeichert!")
                st.rerun()
            else:
                st.error(f"Fehler beim Speichern: {error}")
        
        if delete:
            # TODO: Delete file from storage
            updated_materials = [m for m in materials if m.get('id') != material_id]
            success, error = update_section_materials(section_id, updated_materials)
            if success:
                st.success("Material gelöscht!")
                UnitEditorState().selected_item = None
                st.rerun()
            else:
                st.error(f"Fehler beim Löschen: {error}")
    
    st.divider()
    st.markdown("##### Vorschau")
    with st.container(border=True):
        if mat_type == 'markdown':
            st.markdown(material.get('content', '*Kein Inhalt*'))
        elif mat_type == 'link':
            url = material.get('content')
            st.link_button(f"🔗 {url}", url) if url else st.caption('*Keine URL*')
        elif mat_type == 'file':
            if file_path := material.get('path'):
                # Nutze Session-Client für Storage-Zugriff
                from utils.session_client import get_user_supabase_client
                supabase = get_user_supabase_client()
                try:
                    signed_url = supabase.storage.from_("section_materials").create_signed_url(file_path, 60)['signedURL']
                    
                    response = requests.get(signed_url)
                    response.raise_for_status()
                    file_data = response.content

                    mime_type = material.get('mime_type', '')
                    if 'image' in mime_type:
                        # Use 3 columns to center the image and control its width
                        _col1, col_img, _col2 = st.columns([1, 4, 1])
                        with col_img:
                            st.image(file_data, caption=material.get('filename'), use_container_width=True)
                    else:
                        st.download_button(
                            label=f"📥 {material.get('filename')} herunterladen",
                            data=file_data,
                            file_name=material.get('filename'),
                            mime=mime_type
                        )
                except Exception as e:
                    st.error(f"Fehler bei Vorschau: {e}")
            else:
                st.caption('*Keine Datei hochgeladen*')
        elif mat_type == 'applet':
            applet_code = material.get('content', '')
            if applet_code:
                # Sanitize HTML to prevent XSS
                allowed_tags = [
                    'html', 'head', 'body', 'title', 'meta', 'style', 'script',
                    'div', 'span', 'p', 'a', 'img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    'ul', 'ol', 'li', 'table', 'tr', 'td', 'th', 'thead', 'tbody',
                    'button', 'input', 'form', 'label', 'select', 'option', 'textarea',
                    'canvas', 'svg', 'path', 'g', 'circle', 'rect', 'line', 'polygon',
                    'br', 'hr', 'strong', 'em', 'u', 'i', 'b', 'code', 'pre'
                ]
                allowed_attrs = {
                    '*': ['class', 'id', 'style'],
                    'a': ['href', 'title', 'target'],
                    'img': ['src', 'alt', 'width', 'height'],
                    'input': ['type', 'name', 'value', 'placeholder'],
                    'button': ['type', 'onclick'],
                    'form': ['action', 'method'],
                    'meta': ['name', 'content', 'charset'],
                    'script': ['src', 'type'],
                    'link': ['rel', 'href', 'type'],
                    'canvas': ['width', 'height'],
                    'svg': ['width', 'height', 'viewBox', 'xmlns'],
                    'path': ['d', 'fill', 'stroke'],
                    'circle': ['cx', 'cy', 'r', 'fill', 'stroke'],
                    'rect': ['x', 'y', 'width', 'height', 'fill', 'stroke']
                }
                
                # Clean the HTML while preserving necessary functionality
                # Note: This allows style and script tags for educational applets
                # In a more restrictive environment, you might want to remove these
                safe_html = bleach.clean(
                    applet_code,
                    tags=allowed_tags,
                    attributes=allowed_attrs,
                    strip=False,
                    strip_comments=False
                )
                
                # Display with sanitized HTML
                st.components.v1.html(safe_html, height=600, scrolling=True)
            else:
                st.caption('*Kein Code für Applet vorhanden*')

def render_task_editor(selected_item: dict):
    """Rendert den Editor für eine Aufgabe.
    
    Args:
        selected_item: Dictionary mit Aufgabendaten
    """
    task = selected_item.get('data', {})
    task_id = selected_item.get('id')
    
    st.markdown(f"#### 📝 Aufgabe")
    
    # Bearbeitungsformular
    with st.form(f"edit_task_{task_id}"):
        new_instruction = st.text_area(
            "Aufgabenstellung",
            value=task.get('instruction', ''),
            height=200,
            help="Beschreiben Sie die Aufgabe präzise"
        )
        st.markdown("")  # Extra Whitespace
        
        # Bewertungskriterien
        st.markdown("**Bewertungskriterien** (max. 5)")
        existing_criteria = task.get('assessment_criteria', [])
        criteria_list = []
        for i in range(5):
            default_value = existing_criteria[i] if i < len(existing_criteria) else ""
            criterion = st.text_input(
                f"Kriterium {i+1}",
                value=default_value,
                key=f"edit_criterion_{task_id}_{i}"
            )
            if criterion and criterion.strip():
                criteria_list.append(criterion.strip())
        
        # Lösungshinweise
        new_solution_hints = st.text_area(
            "Lösungshinweise",
            value=task.get('solution_hints', ''),
            height=150,
            help="Musterlösung oder Hinweise für die KI-Bewertung"
        )
        st.markdown("")  # Extra Whitespace
        
        # Maximale Abgaben
        max_attempts = st.number_input(
            "Maximale Abgaben",
            min_value=1,
            max_value=10,
            value=task.get('max_attempts', 1),
            help="Wie oft dürfen Schüler diese Aufgabe einreichen?"
        )
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            cancel = st.form_submit_button("Abbrechen", use_container_width=True)
        with col2:
            save = st.form_submit_button("Speichern", type="primary", use_container_width=True)
        with col3:
            delete = st.form_submit_button("🗑️ Löschen", use_container_width=True)
        
        if save and new_instruction:
            success, error = update_task(
                task_id=task_id,
                instruction=new_instruction.strip(),
                assessment_criteria=criteria_list if criteria_list else None,
                solution_hints=new_solution_hints.strip() if new_solution_hints else None,
                max_attempts=max_attempts
            )
            if success:
                st.success("Aufgabe gespeichert!")
                st.rerun()
            else:
                st.error(f"Fehler beim Speichern: {error}")
        
        if delete:
            success, error = delete_task(task_id)
            if success:
                st.success("Aufgabe gelöscht!")
                # Reset selected item
                state = UnitEditorState()
                state.selected_item = None
                st.rerun()
            else:
                st.error(f"Fehler beim Löschen: {error}")
    
    # Vorschau der Aufgabenstellung
    if task.get('instruction'):
        st.divider()
        st.markdown("##### Vorschau der Aufgabenstellung")
        with st.container(border=True):
            st.markdown(task.get('instruction'))


def render_new_material_form(section_id: str):
    """Rendert das Formular für neues Material."""
    st.markdown("### ➕ Neues Material erstellen")
    
    if not section_id:
        st.error("Bitte wählen Sie einen Abschnitt aus.")
        if st.button("Abbrechen"):
            st.session_state.creating_type = None
            st.rerun()
        return
    
    with st.form("new_material_form"):
        title = st.text_input("Titel des Materials")
        
        mat_type = st.selectbox(
            "Material-Art",
            options=['markdown', 'link', 'file', 'applet'],
            format_func=lambda x: {
                'markdown': 'Markdown Text',
                'link': 'Weblink',
                'file': 'Datei-Upload',
                'applet': 'HTML/JS Applet'
            }[x]
        )
        
        content = None
        if mat_type == 'markdown':
            content = st.text_area("Inhalt (Markdown)", height=300)
        elif mat_type == 'link':
            content = st.text_input("URL")
        elif mat_type == 'file':
            uploaded_file = st.file_uploader("Datei auswählen")
        elif mat_type == 'applet':
            content = st.text_area("HTML/JS/CSS Code", height=400)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Abbrechen", use_container_width=True):
                st.session_state.creating_type = None
                st.rerun()
        with col2:
            if st.form_submit_button("Erstellen", type="primary", use_container_width=True):
                if not title.strip():
                    st.error("Der Titel darf nicht leer sein.")
                    return
                
                # Für File-Upload: verarbeite Datei zuerst
                if mat_type == 'file' and 'uploaded_file' in locals() and uploaded_file is not None:
                    MAX_FILE_SIZE = 20 * 1024 * 1024
                    if uploaded_file.size > MAX_FILE_SIZE:
                        st.error(f"Datei zu groß. Max. 20 MB erlaubt.")
                        return
                    
                    # File Upload zu Supabase Storage
                    from utils.session_client import get_user_supabase_client
                    from supabase_client import get_supabase_service_client
                    import re
                    from pathlib import Path
                    from utils.unit_state import get_selected_unit_id
                    
                    file_bytes = uploaded_file.getvalue()
                    
                    # Rate limiting check
                    from utils.rate_limiter import check_upload_rate_limit, RateLimitExceeded
                    try:
                        check_upload_rate_limit(str(st.session_state.user.id), uploaded_file.size)
                    except RateLimitExceeded as e:
                        st.error(f"🚫 Upload-Limit erreicht: {str(e)}")
                        return
                    
                    # Validate and sanitize file
                    try:
                        validate_file_upload(uploaded_file)
                    except ValidationError as e:
                        st.error(str(e))
                        return
                    
                    # Filename Sanitization - Path Traversal Protection
                    safe_filename = sanitize_filename(uploaded_file.name)
                    
                    unit_id_for_path = get_selected_unit_id()
                    file_path = f"unit_{unit_id_for_path}/section_{section_id}/{uuid.uuid4()}_{safe_filename}"
                    
                    # Use service client for upload (temporary RLS fix)
                    service_client = get_supabase_service_client()
                    if not service_client:
                        st.error("Service-Client nicht verfügbar. Bitte Administrator kontaktieren.")
                        return
                    
                    try:
                        service_client.storage.from_("section_materials").upload(path=file_path, file=file_bytes)
                    except Exception as e:
                        st.error(f"Fehler beim Datei-Upload: {str(e)}")
                        return
                
                # Lade aktuelle Section
                try:
                    from utils.session_client import get_user_supabase_client
                    client = get_user_supabase_client()
                    response = client.table('unit_section')\
                        .select('materials')\
                        .eq('id', section_id)\
                        .single()\
                        .execute()
                    
                    if hasattr(response, 'data') and response.data:
                        current_materials = response.data.get('materials', []) or []
                    else:
                        current_materials = []
                except Exception as e:
                    st.error(f"Fehler beim Laden der Materialien: {str(e)}")
                    return
                
                # Erstelle neues Material-Objekt
                new_material = {
                    'id': str(uuid.uuid4()),
                    'title': title.strip(),
                    'type': mat_type,
                    'created_at': st.session_state.get('user_tz', 'UTC')
                }
                
                # Typ-spezifische Felder
                if mat_type == 'file' and 'uploaded_file' in locals() and uploaded_file:
                    new_material.update({
                        'path': file_path,
                        'filename': uploaded_file.name,
                        'mime_type': uploaded_file.type
                    })
                elif mat_type in ['markdown', 'link', 'applet'] and content:
                    new_material['content'] = content.strip() if mat_type != 'applet' else content
                
                # Material zu Liste hinzufügen
                updated_materials = current_materials + [new_material]
                
                # Speichere in Datenbank
                success, error = update_section_materials(section_id, updated_materials)
                if success:
                    st.success(f"Material '{title.strip()}' erfolgreich erstellt!")
                    st.session_state.creating_type = None
                    st.rerun()
                else:
                    st.error(f"Fehler beim Speichern: {error}")


def render_new_regular_task_form(section_id: str):
    """Rendert das Formular für eine neue reguläre Aufgabe."""
    st.markdown("### ➕ Neue Aufgabe erstellen")
    
    if not section_id:
        st.error("Bitte wählen Sie einen Abschnitt aus.")
        if st.button("Abbrechen"):
            st.session_state.creating_type = None
            st.rerun()
        return
    
    with st.form("new_regular_task_form"):
        instruction = st.text_area("Aufgabenstellung", height=200)
        
        # Bewertungskriterien
        st.markdown("**Bewertungskriterien** (max. 5)")
        criteria_list = []
        for i in range(5):
            criterion = st.text_input(
                f"Kriterium {i+1}",
                key=f"new_regular_criterion_{i}",
                placeholder=f"Bewertungskriterium {i+1} (optional)"
            )
            if criterion and criterion.strip():
                criteria_list.append(criterion.strip())
        
        max_attempts = st.number_input(
            "Maximale Abgaben",
            min_value=1,
            max_value=10,
            value=3,
            help="Wie oft dürfen Schüler die Aufgabe abgeben?"
        )
        
        solution_hints = st.text_area("Lösungshinweise", height=150)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Abbrechen", use_container_width=True):
                st.session_state.creating_type = None
                st.rerun()
        with col2:
            if st.form_submit_button("Erstellen", type="primary", use_container_width=True):
                if not instruction.strip():
                    st.error("Die Aufgabenstellung darf nicht leer sein.")
                    return
                
                # Hole bestehende Tasks für Order-Index
                existing_tasks, error = get_regular_tasks_for_section(section_id)
                if error:
                    st.error(f"Fehler beim Laden der Aufgaben: {error}")
                    return
                
                next_order = len(existing_tasks) + 1
                
                # Erstelle Regular Task mit sauberer Domain-spezifischer Funktion
                new_task, create_error = create_regular_task(
                    section_id=section_id,
                    instruction=instruction.strip(),
                    task_type='text',  # Standard-Typ nach Task-Type-Trennung
                    order_in_section=next_order,
                    max_attempts=max_attempts,
                    assessment_criteria=criteria_list if criteria_list else None,
                    solution_hints=solution_hints.strip() if solution_hints else None
                )
                if create_error:
                    st.error(f"Fehler beim Erstellen der Aufgabe: {create_error}")
                else:
                    st.success("Aufgabe erfolgreich erstellt!")
                    st.session_state.creating_type = None
                    st.rerun()


def render_new_mastery_task_form(section_id: str):
    """Rendert das Formular für eine neue Wissensfestiger-Aufgabe."""
    st.markdown("### ➕ Neuer Wissensfestiger erstellen")
    
    if not section_id:
        st.error("Bitte wählen Sie einen Abschnitt aus.")
        if st.button("Abbrechen"):
            st.session_state.creating_type = None
            st.rerun()
        return
    
    with st.form("new_mastery_task_form"):
        instruction = st.text_area("Aufgabenstellung", height=200)
        
        # Bewertungskriterien
        st.markdown("**Bewertungskriterien** (max. 5)")
        criteria_list = []
        for i in range(5):
            criterion = st.text_input(
                f"Kriterium {i+1}",
                key=f"new_mastery_criterion_{i}",
                placeholder=f"Bewertungskriterium {i+1} (optional)"
            )
            if criterion and criterion.strip():
                criteria_list.append(criterion.strip())
        
        solution_hints = st.text_area("Lösungshinweise", height=150)
        
        st.info("🎯 Wissensfestiger verwenden Spaced Repetition - die Wiederholungen werden automatisch verwaltet.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Abbrechen", use_container_width=True):
                st.session_state.creating_type = None
                st.rerun()
        with col2:
            if st.form_submit_button("Erstellen", type="primary", use_container_width=True):
                if not instruction.strip():
                    st.error("Die Aufgabenstellung darf nicht leer sein.")
                    return
                
                # Erstelle Mastery Task mit sauberer Domain-spezifischer Funktion
                new_task, create_error = create_mastery_task(
                    section_id=section_id,
                    instruction=instruction.strip(),
                    task_type='text',  # Standard-Typ nach Task-Type-Trennung
                    assessment_criteria=criteria_list if criteria_list else None,
                    solution_hints=solution_hints.strip() if solution_hints else None
                )
                if create_error:
                    st.error(f"Fehler beim Erstellen des Wissensfestigers: {create_error}")
                else:
                    st.success("Wissensfestiger erfolgreich erstellt!")
                    st.session_state.creating_type = None
                    st.rerun()


def render_new_section_form(unit_id: str):
    """Rendert das Formular für einen neuen Abschnitt."""
    st.markdown("### ➕ Neuen Abschnitt erstellen")
    
    if not unit_id:
        st.error("Keine Lerneinheit ausgewählt.")
        if st.button("Abbrechen"):
            st.session_state.creating_section = False
            st.rerun()
        return
    
    with st.form("new_section_form"):
        title = st.text_input(
            "Titel des Abschnitts",
            placeholder="z.B. Grundlagen der Algebra"
        )
        
        description = st.text_area(
            "Beschreibung (optional)",
            height=100,
            placeholder="Kurze Beschreibung was in diesem Abschnitt behandelt wird..."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Abbrechen", use_container_width=True):
                st.session_state.creating_section = False
                st.rerun()
        with col2:
            if st.form_submit_button("Erstellen", type="primary", use_container_width=True):
                if not title.strip():
                    st.error("Der Titel darf nicht leer sein.")
                else:
                    # Hole bestehende Abschnitte für Order-Index
                    existing_sections, error = get_sections_for_unit(unit_id)
                    if error:
                        st.error(f"Fehler beim Laden der Abschnitte: {error}")
                    else:
                        next_order = len(existing_sections or []) + 1
                        
                        # Erstelle neuen Abschnitt
                        new_section, create_error = create_section(unit_id, title.strip(), next_order)
                        if create_error:
                            st.error(f"Fehler beim Erstellen: {create_error}")
                        else:
                            st.success(f"Abschnitt '{title.strip()}' erfolgreich erstellt!")
                            st.session_state.creating_section = False
                            st.rerun()


def render_material_editor_by_id(material_id: str):
    """Rendert den Material-Editor basierend auf der ID."""
    from utils.db_queries import get_sections_for_unit
    from utils.unit_state import get_selected_unit_id
    
    # Direkt Section-ID aus Session State verwenden wenn verfügbar
    section_id = getattr(st.session_state, 'selected_section_id', None)
    if section_id:
        # Lade nur diesen spezifischen Abschnitt
        from utils.db_queries import get_user_supabase_client
        try:
            client = get_user_supabase_client()
            response = client.table('unit_section')\
                .select('id, title, materials')\
                .eq('id', section_id)\
                .single()\
                .execute()
            
            if hasattr(response, 'data') and response.data:
                section = response.data
                materials = section.get('materials', []) or []
                st.write(f"**Gefundene Materialien in Section:** {len(materials)}")
                
                material_found = None
                for material in materials:
                    if material.get('id') == material_id:
                        material_found = material
                        break
                
                if material_found:
                    fake_item = {
                        'id': material_id, 
                        'section_id': section_id,
                        'data': material_found
                    }
                    unit_id = get_selected_unit_id() or ""
                    render_material_editor(fake_item, unit_id)
                    return
                else:
                    st.error(f"Material {material_id} nicht in Section {section_id} gefunden")
                    return
            else:
                st.error("Section nicht gefunden")
                return
        except Exception as e:
            st.error(f"Fehler beim Laden der Section: {str(e)}")
            return
    
    # Fallback: Hole Unit-ID und lade alle Abschnitte
    unit_id = get_selected_unit_id()
    st.write(f"**Fallback: Unit-ID = {unit_id}**")
    
    if not unit_id:
        st.error("Keine Lerneinheit oder Section ausgewählt")
        return
    
    # Lade Abschnitte der aktuellen Lerneinheit
    sections, error = get_sections_for_unit(unit_id)
    if error:
        st.error(f"Fehler beim Laden der Abschnitte: {error}")
        return
    
    if not sections:
        st.error("Keine Abschnitte gefunden")
        return
    
    st.write(f"**Gefundene Abschnitte:** {len(sections)}")
    
    # Suche das Material in den Abschnitten
    material_found = None
    found_section_id = None
    
    for section in sections:
        materials = section.get('materials', []) or []
        for material in materials:
            if material.get('id') == material_id:
                material_found = material
                found_section_id = section['id']
                break
        if material_found:
            break
    
    if material_found:
        st.write("**Material über Fallback gefunden!**")
        fake_item = {
            'id': material_id,
            'section_id': found_section_id, 
            'data': material_found
        }
        render_material_editor(fake_item, unit_id)
    else:
        st.error("Material nicht gefunden")


def render_task_editor_by_id(task_id: str):
    """Rendert den Task-Editor basierend auf der ID."""
    # Tasks sind in separaten Tabellen, verwende direkte DB-Abfrage
    from utils.db_queries import get_user_supabase_client
    
    try:
        client = get_user_supabase_client()
        # Prüfe zuerst regular_tasks (über all_regular_tasks View)
        response = client.table('all_regular_tasks')\
            .select('*')\
            .eq('id', task_id)\
            .execute()
        
        task_found = None
        if hasattr(response, 'data') and response.data and len(response.data) > 0:
            task_found = response.data[0]
            task_type = 'regular'
        else:
            # Prüfe mastery_tasks (über all_mastery_tasks View)  
            response = client.table('all_mastery_tasks')\
                .select('*')\
                .eq('id', task_id)\
                .execute()
            
            if hasattr(response, 'data') and response.data and len(response.data) > 0:
                task_found = response.data[0]
                task_type = 'mastery'
        
        if task_found:
            # Verwende korrekte Datenstruktur für render_task_editor
            fake_item = {
                'id': task_id,
                'data': task_found,
                'type': task_type
            }
            # Mastery tasks haben andere Felder, verwende angepasste Funktion
            if task_type == 'mastery':
                render_mastery_task_editor(fake_item)
            else:
                render_task_editor(fake_item)
        else:
            st.error("Aufgabe nicht gefunden")
            
    except Exception as e:
        st.error(f"Fehler beim Laden der Aufgabe: {str(e)}")


def render_mastery_task_editor(selected_item: dict):
    """Rendert den Editor für eine Mastery-Task (Wissensfestiger)."""
    task = selected_item.get('data', {})
    task_id = selected_item.get('id')
    
    st.markdown(f"#### 🎯 Wissensfestiger")
    st.info("🔄 Wissensfestiger verwenden Spaced Repetition - Wiederholungen werden automatisch verwaltet")
    
    # Bearbeitungsformular mit eindeutiger Key
    with st.form(f"edit_mastery_task_{task_id}"):
        new_instruction = st.text_area(
            "Aufgabenstellung",
            value=task.get('instruction', ''),
            height=200,
            help="Beschreiben Sie die Wissensfestiger-Aufgabe präzise"
        )
        st.markdown("")  # Extra Whitespace
        
        # Bewertungskriterien
        st.markdown("**Bewertungskriterien** (max. 5)")
        existing_criteria = task.get('assessment_criteria', [])
        criteria_list = []
        for i in range(5):
            default_value = existing_criteria[i] if i < len(existing_criteria) else ""
            criterion = st.text_input(
                f"Kriterium {i+1}",
                value=default_value,
                key=f"edit_mastery_criterion_{task_id}_{i}"
            )
            if criterion and criterion.strip():
                criteria_list.append(criterion.strip())
        st.markdown("")  # Extra Whitespace
        
        # Lösungshinweise
        new_solution_hints = st.text_area(
            "Lösungshinweise",
            value=task.get('solution_hints', ''),
            height=150,
            help="Musterlösung oder Hinweise für die KI-Bewertung"
        )
        st.markdown("")  # Extra Whitespace
        
        # Buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            cancel = st.form_submit_button("Abbrechen", use_container_width=True)
        with col2:
            save = st.form_submit_button("Speichern", type="primary", use_container_width=True)
        with col3:
            delete = st.form_submit_button("🗑️ Löschen", use_container_width=True)
        
        # Verarbeitung für Mastery Tasks
        if save and new_instruction:
            # Mastery Tasks haben keine max_attempts oder order_in_section
            success, error = update_task(
                task_id=task_id,
                instruction=new_instruction.strip(),
                assessment_criteria=criteria_list if criteria_list else None,
                solution_hints=new_solution_hints.strip() if new_solution_hints else None
            )
            if success:
                st.success("Wissensfestiger gespeichert!")
                st.rerun()
            else:
                st.error(f"Fehler beim Speichern: {error}")
        elif delete:
            success, error = delete_task(task_id)
            if success:
                st.success("Wissensfestiger gelöscht!")
                # Reset selected item
                state = UnitEditorState()
                state.selected_item = None
                st.rerun()
            else:
                st.error(f"Fehler beim Löschen: {error}")
        elif cancel:
            st.rerun()
    
    # Vorschau der Aufgabenstellung
    if task.get('instruction'):
        st.divider()
        st.markdown("##### Vorschau der Aufgabenstellung")
        with st.container(border=True):
            st.markdown(task.get('instruction'))