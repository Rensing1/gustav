# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""
Submission Input Component

Rendert Submission-UI für Text-Eingaben.
"""

import streamlit as st
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from utils.db_queries import create_submission
from utils.session_client import get_user_supabase_client


def render_submission_input(task: Dict[str, Any], student_id: str) -> Optional[Dict]:
    """
    Rendert Submission-Input Component mit Text oder Datei-Upload.
    
    Args:
        task: Task-Dictionary mit id, title, etc.
        student_id: ID des Schülers
        
    Returns:
        Dictionary mit submission result oder None
    """
    task_id = task["id"]
    task_type = task.get("task_type", "practice_task")
    
    # Mastery Tasks: nur Text
    if task_type == "mastery_task":
        return _render_text_submission(task_id)
    
    # Regular Tasks: Text oder Upload
    submission_mode = st.radio(
        "Wie möchtest du deine Lösung einreichen?",
        ["📝 Text eingeben", "📎 Datei hochladen (Bild/PDF)"],
        horizontal=True,
        key=f"mode_{task_id}"
    )
    
    # Experimenteller Hinweis für Datei-Upload
    if submission_mode == "📎 Datei hochladen (Bild/PDF)":
        st.caption("⚗️ **Experimentell**: Datei-Upload befindet sich im Beta-Test. Bei Problemen nutze bitte die Text-Eingabe.")
    
    if submission_mode == "📝 Text eingeben":
        return _render_text_submission(task_id)
    else:
        return _render_file_submission(task_id, student_id)


def _render_text_submission(task_id: str) -> Optional[Dict]:
    """Rendert Text-Eingabe für Submissions."""
    
    with st.form(key=f"text_form_{task_id}"):
        solution_text = st.text_area(
            "Deine Antwort:",
            key=f"solution_{task_id}",
            height=150,
            placeholder="Schreibe hier deine Lösung..."
        )
        
        submit_button = st.form_submit_button("📝 Antwort einreichen")
        
        if submit_button:
            if not solution_text.strip():
                st.error("Bitte gib eine Antwort ein.")
                return None
                
            return {
                "type": "text",
                "content": solution_text.strip(),
                "task_id": task_id
            }
    
    return None


def _render_file_submission(task_id: str, student_id: str) -> Optional[Dict]:
    """Rendert Datei-Upload für Submissions."""
    
    with st.form(key=f"file_form_{task_id}"):
        uploaded_file = st.file_uploader(
            "Lade deine Lösung hoch",
            type=["jpg", "jpeg", "png", "pdf"],
            help="Maximale Dateigröße: 10MB",
            key=f"file_{task_id}"
        )
        
        if uploaded_file:
            # Dateigröße prüfen
            if uploaded_file.size > 10 * 1024 * 1024:
                st.error("❌ Datei zu groß! Maximal 10MB erlaubt.")
                return None
            
            # Magic Number Check - File-Type-Validation
            header = uploaded_file.read(1024)
            uploaded_file.seek(0)  # Reset file pointer
            if not (header.startswith(b'\xff\xd8') or    # JPEG
                    header.startswith(b'\x89PNG') or      # PNG  
                    header.startswith(b'%PDF')):          # PDF
                st.error("❌ Nur JPG, PNG und PDF Dateien erlaubt!")
                return None
            
            # Dateiinfo anzeigen
            st.info(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        submit_button = st.form_submit_button("📎 Datei einreichen")
        
        if submit_button:
            if not uploaded_file:
                st.error("Bitte wähle eine Datei aus.")
                return None
            
            return {
                "type": "file_upload",
                "file": uploaded_file,
                "filename": uploaded_file.name,
                "task_id": task_id,
                "student_id": student_id
            }
    
    return None


def handle_file_submission(submission: Dict) -> bool:
    """Verarbeitet Datei-Upload Submissions und erstellt Submission-Eintrag."""
    try:
        uploaded_file = submission["file"]
        task_id = submission["task_id"]
        student_id = submission["student_id"]
        
        # Rate limiting check
        from utils.rate_limiter import check_upload_rate_limit, RateLimitExceeded
        try:
            check_upload_rate_limit(student_id, uploaded_file.size)
        except RateLimitExceeded as e:
            st.error(f"🚫 Upload-Limit erreicht: {str(e)}")
            return False
        
        # Debug: Auth und IDs prüfen
        print(f"[DEBUG] Upload - Student ID: {student_id}")
        print(f"[DEBUG] Upload - Session exists: {bool(st.session_state.get('session'))}")
        if st.session_state.get('session'):
            print(f"[DEBUG] Upload - Session user: {st.session_state.session.user}")
        if st.session_state.get('user'):
            print(f"[DEBUG] Upload - App user ID: {st.session_state.user.id}")
            print(f"[DEBUG] Upload - ID match: {student_id == str(st.session_state.user.id)}")
        
        # Storage-Pfad generieren (entspricht RLS-Policy)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_id = str(uuid.uuid4())[:8]
        ext = submission["filename"].split('.')[-1].lower()
        file_path = f"student_{student_id}/task_{task_id}/{timestamp}_{file_id}.{ext}"
        
        # Upload zu Storage mit Service Client (temporärer Fix für RLS-Problem)
        from supabase_client import get_supabase_service_client
        supabase = get_supabase_service_client()
        
        if not supabase:
            st.error("Service-Client nicht verfügbar. Bitte Administrator kontaktieren.")
            return False
        
        # Debug: Storage-Auth prüfen
        print(f"[DEBUG] Upload - File path: {file_path}")
        print(f"[DEBUG] Upload - Using service client for upload (temporary fix)")
        
        # Datei hochladen mit Service-Rechten (umgeht RLS)
        result = supabase.storage.from_('submissions').upload(
            path=file_path,
            file=uploaded_file.read(),
            file_options={"content-type": uploaded_file.type}
        )
        
        # Submission erstellen
        submission_data = {
            "text": "[Wird verarbeitet...]",  # Platzhalter
            "file_path": file_path,
            "file_type": ext,
            "original_filename": submission["filename"]
        }
        
        create_submission(
            student_id=student_id,
            task_id=task_id,
            submission_data=submission_data
        )
        
        st.success("✅ Datei erfolgreich eingereicht!")
        st.info("🔄 **Einreichung wird ausgewertet...**")
        return True
        
    except Exception as e:
        st.error(f"❌ Upload fehlgeschlagen: {str(e)}")
        return False