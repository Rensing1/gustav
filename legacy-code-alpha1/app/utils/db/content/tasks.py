"""Task management functions for HttpOnly Cookie support.

This module contains all task-related database functions that have been
migrated to use the RPC pattern with session-based authentication.
"""

import json
import traceback
from typing import Optional, Dict, Any, List, Tuple

from ..core.session import get_session_id, get_anon_client, handle_rpc_result


def create_regular_task(section_id: str, instruction: str, task_type: str, 
                       order_in_section: int = 1, max_attempts: int = 1,
                       assessment_criteria: list = None, solution_hints: str = None) -> tuple[dict | None, str | None]:
    """
    Creates a regular task using the new table structure (task_base + regular_tasks).
    Clean Domain-Driven Design without is_mastery flag.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('create_regular_task', {
            'p_session_id': session_id,
            'p_section_id': section_id,
            'p_instruction': instruction,
            'p_task_type': task_type,
            'p_order_in_section': order_in_section,
            'p_max_attempts': max_attempts,
            'p_assessment_criteria': assessment_criteria or []
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Erstellen der Aufgabe')
            return None, error_msg
        
        # RPC returns UUID, build full response
        if result.data:
            return {
                'id': result.data,
                'section_id': section_id,
                'instruction': instruction,
                'task_type': task_type,
                'order_in_section': order_in_section,
                'max_attempts': max_attempts,
                'assessment_criteria': assessment_criteria or [],
                'solution_hints': solution_hints
            }, None
        
        return None, "Unerwartete Antwort beim Erstellen der Aufgabe"
        
    except Exception as e:
        print(f"Error in create_regular_task: {traceback.format_exc()}")
        return None, f"Fehler beim Erstellen der Aufgabe: {str(e)}"


def create_mastery_task(section_id: str, instruction: str, task_type: str,
                       order_in_section: int = 1, assessment_criteria: list = None,
                       solution_hints: str = None) -> tuple[dict | None, str | None]:
    """
    Creates a mastery task using the new table structure (task_base + mastery_tasks).
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('create_mastery_task', {
            'p_session_id': session_id,
            'p_section_id': section_id,
            'p_instruction': instruction,
            'p_task_type': task_type,
            'p_order_in_section': order_in_section,
            'p_difficulty_level': 1,  # Default difficulty
            'p_assessment_criteria': json.dumps(assessment_criteria) if assessment_criteria else None
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Erstellen der Mastery-Aufgabe')
            return None, error_msg
        
        # RPC returns UUID, build full response
        if result.data:
            return {
                'id': result.data,
                'section_id': section_id,
                'instruction': instruction,
                'task_type': task_type,
                'order_in_section': order_in_section,
                'assessment_criteria': assessment_criteria or [],
                'solution_hints': solution_hints,
                'is_mastery': True  # Compatibility field
            }, None
        
        return None, "Unerwartete Antwort beim Erstellen der Mastery-Aufgabe"
        
    except Exception as e:
        print(f"Error in create_mastery_task: {traceback.format_exc()}")
        return None, f"Fehler beim Erstellen der Mastery-Aufgabe: {str(e)}"


def update_task_in_new_structure(task_id: str, update_data: dict) -> tuple[dict | None, str | None]:
    """
    Updates a task using the RPC pattern. Supports both regular and mastery tasks.
    
    Returns:
        tuple: (Updated task dict, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not task_id:
            return None, "Task-ID ist erforderlich."
        
        client = get_anon_client()
        
        # Map the correct field names
        # The SQL function expects 'title' and 'prompt', but we use 'instruction'
        # The SQL function expects 'grading_criteria', but we use 'assessment_criteria'
        params = {
            'p_session_id': session_id,
            'p_task_id': task_id,
            'p_title': update_data.get('instruction', update_data.get('title')),  # Use instruction, fallback to title
            'p_prompt': update_data.get('instruction', update_data.get('prompt')),  # Use instruction for prompt too
            'p_task_type': update_data.get('task_type', 'regular'),
            'p_order_in_section': update_data.get('order_in_section'),
            'p_max_attempts': update_data.get('max_attempts'),
            'p_grading_criteria': update_data.get('assessment_criteria', update_data.get('grading_criteria')),  # Map assessment_criteria to grading_criteria
            'p_difficulty_level': update_data.get('difficulty_level'),
            'p_concept_explanation': update_data.get('concept_explanation')
        }
        
        # Remove None values to use defaults
        params = {k: v for k, v in params.items() if v is not None}
        
        # Use the correct function name
        result = client.rpc('update_task_in_new_structure', params).execute()
        
        # Check for errors
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Aktualisieren der Aufgabe')
            return None, error_msg
        
        # The function returns VOID, so we construct the response
        # Return the update_data as confirmation
        return {
            'id': task_id,
            **update_data
        }, None
        
    except Exception as e:
        print(f"Error in update_task_in_new_structure: {traceback.format_exc()}")
        return None, f"Fehler beim Aktualisieren der Aufgabe: {str(e)}"


def delete_task_in_new_structure(task_id: str) -> tuple[bool, str | None]:
    """
    Deletes a task using the RPC pattern. Works with both regular and mastery tasks.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        if not task_id:
            return False, "Task-ID ist erforderlich."
        
        client = get_anon_client()
        result = client.rpc('delete_task_in_new_structure', {
            'p_session_id': session_id,
            'p_task_id': task_id
        }).execute()
        
        # RPC returns void on success, raises exception on error
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Löschen der Aufgabe')
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        print(f"Error in delete_task_in_new_structure: {traceback.format_exc()}")
        return False, f"Fehler beim Löschen der Aufgabe: {str(e)}"


def get_tasks_for_section(section_id: str) -> tuple[list | None, str | None]:
    """Holt alle Aufgaben eines Abschnitts.
    
    Returns:
        tuple: (Liste der Aufgaben, None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not section_id: 
        return [], None
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_tasks_for_section', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            return None, error
        
        # Sort tasks by order_in_section
        if data:
            data.sort(key=lambda x: x.get('order_in_section', 0))
        
        return data or [], None
        
    except Exception as e:
        print(f"Error in get_tasks_for_section: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Aufgaben: {str(e)}"


def get_regular_tasks_for_section(section_id: str) -> tuple[list[dict], str | None]:
    """Holt nur die regulären Aufgaben eines Abschnitts.
    
    Returns:
        tuple: (Liste der regulären Aufgaben, None) bei Erfolg, ([], Fehlermeldung) bei Fehler.
    """
    if not section_id:
        return [], None
    
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_regular_tasks_for_section', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            print(f"Error fetching regular tasks: {error}")
            return [], error
        
        # Ensure all tasks have expected fields
        tasks = []
        for task in (data or []):
            if task is None:
                continue
            tasks.append({
                'id': task.get('id'),
                'section_id': task.get('section_id'),
                'instruction': task.get('instruction') or task.get('prompt', ''),
                'task_type': task.get('task_type'),
                'order_in_section': task.get('order_in_section', 0),
                'max_attempts': task.get('max_attempts', 1),
                'assessment_criteria': task.get('assessment_criteria', [])
            })
        
        # Sort by order_in_section
        tasks.sort(key=lambda x: x['order_in_section'])
        return tasks, None
        
    except Exception as e:
        print(f"Error in get_regular_tasks_for_section: {traceback.format_exc()}")
        return [], f"Fehler beim Abrufen der regulären Aufgaben: {str(e)}"


def get_mastery_tasks_for_section(section_id: str) -> tuple[list[dict], str | None]:
    """Holt nur die Mastery-Aufgaben eines Abschnitts.
    
    Returns:
        tuple: (Liste der Mastery-Aufgaben, None) bei Erfolg, ([], Fehlermeldung) bei Fehler.
    """
    if not section_id:
        return [], None
    
    try:
        session_id = get_session_id()
        if not session_id:
            return [], "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_mastery_tasks_for_section', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        data, error = handle_rpc_result(result, [])
        if error:
            print(f"Error fetching mastery tasks: {error}")
            return [], error
        
        # Ensure all tasks have expected fields
        tasks = []
        for task in (data or []):
            if task is None:
                continue
            tasks.append({
                'id': task.get('id'),
                'section_id': task.get('section_id'),
                'instruction': task.get('instruction') or task.get('prompt', ''),
                'task_type': task.get('task_type'),
                'order_in_section': task.get('order_in_section', 0),
                'assessment_criteria': task.get('assessment_criteria', [])
            })
        
        # Sort by order_in_section
        tasks.sort(key=lambda x: x['order_in_section'])
        return tasks, None
        
    except Exception as e:
        print(f"Error in get_mastery_tasks_for_section: {traceback.format_exc()}")
        return [], f"Fehler beim Abrufen der Mastery-Aufgaben: {str(e)}"


def get_section_tasks(section_id: str) -> tuple[list | None, str | None]:
    """Holt alle Aufgaben eines Abschnitts.
    
    Returns:
        tuple: (Liste mit task_id, order_in_section, instruction), None) bei Erfolg, (None, Fehlermeldung) bei Fehler.
    """
    if not section_id:
        return [], None
    
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('get_section_tasks', {
            'p_session_id': session_id,
            'p_section_id': section_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Abrufen der Aufgaben')
            return None, error_msg
            
        if hasattr(result, 'data'):
            # Map fields if needed
            tasks = []
            for task in (result.data or []):
                mapped_task = {
                    'id': task.get('id'),
                    'order_in_section': task.get('order_in_section'),
                    'instruction': task.get('title') or task.get('prompt')  # Map title/prompt to instruction
                }
                tasks.append(mapped_task)
            return tasks, None
        
        return None, "Unerwartete Antwort beim Abrufen der Aufgaben."
        
    except Exception as e:
        print(f"Error in get_section_tasks: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Aufgaben: {e}"


def get_task_details(task_id: str) -> tuple[dict | None, str | None]:
    """Holt relevante Details (instruction, criteria) für eine Aufgabe mit Task-Type-Trennung."""
    try:
        session_id = get_session_id()
        if not session_id:
            return None, "Keine aktive Session gefunden"
        
        if not task_id:
            return None, "Task-ID fehlt."
        
        client = get_anon_client()
        result = client.rpc('get_task_details', {
            'p_session_id': session_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            return None, f"Fehler beim Abrufen der Task-Details: {result.error.get('message', 'Unbekannter Fehler')}"
        
        if result.data and len(result.data) > 0:
            task_data = result.data[0]
            # Map fields from RPC response to expected format
            return {
                'instruction': task_data.get('instruction'),
                'assessment_criteria': task_data.get('grading_criteria', []),
                'solution_hints': task_data.get('solution_hints'),
                'feedback_focus': task_data.get('grading_criteria', [])  # Für Kompatibilität
            }, None
        
        return None, f"Aufgabe mit ID {task_id} nicht gefunden."
        
    except Exception as e:
        print(f"Error in get_task_details: {traceback.format_exc()}")
        return None, f"Fehler beim Abrufen der Task-Details: {str(e)}"


def move_task_up(task_id: str, section_id: str) -> tuple[bool, str | None]:
    """Verschiebt eine Aufgabe um eine Position nach oben.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    if not task_id:
        return False, "Task-ID ist erforderlich."
    
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('move_task_up', {
            'p_session_id': session_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Verschieben der Aufgabe')
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        print(f"Error in move_task_up: {traceback.format_exc()}")
        return False, f"Fehler beim Verschieben der Aufgabe: {e}"


def move_task_down(task_id: str, section_id: str) -> tuple[bool, str | None]:
    """Verschiebt eine Aufgabe um eine Position nach unten.
    
    Returns:
        tuple: (True, None) bei Erfolg, (False, Fehlermeldung) bei Fehler.
    """
    if not task_id:
        return False, "Task-ID ist erforderlich."
    
    try:
        session_id = get_session_id()
        if not session_id:
            return False, "Keine aktive Session gefunden"
        
        client = get_anon_client()
        result = client.rpc('move_task_down', {
            'p_session_id': session_id,
            'p_task_id': task_id
        }).execute()
        
        if hasattr(result, 'error') and result.error:
            error_msg = result.error.get('message', 'Fehler beim Verschieben der Aufgabe')
            return False, error_msg
        
        return True, None
        
    except Exception as e:
        print(f"Error in move_task_down: {traceback.format_exc()}")
        return False, f"Fehler beim Verschieben der Aufgabe: {e}"


# --- Helper Functions ---

def _get_task_table_name() -> str:
    """
    Returns the table name to use for task operations.
    During migration, we use 'task' (old structure).
    After migration, this could switch to views or new tables.
    """
    # Phase 4: Task Type Separation completed - always use 'task'
    return 'task'


def get_regular_tasks_table_name() -> str:
    """
    Returns the view name for regular tasks (Phase 4: Always use views).
    """
    return 'all_regular_tasks'


def get_mastery_tasks_table_name() -> str:
    """
    Returns the view name for mastery tasks (Phase 4: Always use views).
    """
    return 'all_mastery_tasks'


# --- Legacy Functions (DEPRECATED) ---

def create_task_in_new_structure(task_data: dict) -> tuple[dict | None, str | None]:
    """
    Creates a task using the new table structure.
    Routes to create_regular_task or create_mastery_task based on is_mastery flag.
    
    DEPRECATED: Use create_regular_task or create_mastery_task directly.
    """
    is_mastery = task_data.get('is_mastery', False)
    
    # Common parameters
    section_id = task_data.get('section_id')
    instruction = task_data.get('instruction')
    task_type = task_data.get('task_type')
    order_in_section = task_data.get('order_in_section', 1)
    assessment_criteria = task_data.get('assessment_criteria', [])
    solution_hints = task_data.get('solution_hints')
    
    if is_mastery:
        return create_mastery_task(
            section_id=section_id,
            instruction=instruction,
            task_type=task_type,
            order_in_section=order_in_section,
            assessment_criteria=assessment_criteria,
            solution_hints=solution_hints
        )
    else:
        max_attempts = task_data.get('max_attempts', 1)
        return create_regular_task(
            section_id=section_id,
            instruction=instruction,
            task_type=task_type,
            order_in_section=order_in_section,
            max_attempts=max_attempts,
            assessment_criteria=assessment_criteria,
            solution_hints=solution_hints
        )