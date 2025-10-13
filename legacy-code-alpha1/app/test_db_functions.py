#!/usr/bin/env python3
"""
Umfassendes CLI Test Script für alle migrierten DB-Funktionen
Testet systematisch ALLE Funktionen, die in der UI verwendet werden.
Mit echter Session-Authentifizierung, längeren Timeouts und Verbose Logging.

Verwendung:
    docker compose exec app python test_db_functions.py
"""

import os
import sys
import json
import traceback
from datetime import datetime, timedelta
import time
import logging

# Konfiguriere Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from colorama import init, Fore, Style, Back
    init()
except ImportError:
    # Fallback ohne colorama
    class Fore:
        RED = ''
        GREEN = ''
        YELLOW = ''
        BLUE = ''
        CYAN = ''
        MAGENTA = ''
        RESET = ''
    
    class Style:
        RESET_ALL = ''
        BRIGHT = ''
        DIM = ''
    
    class Back:
        RESET = ''

# Füge app-Verzeichnis zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importiere alle benötigten Module
try:
    from utils.db_queries import *
    from utils.db.platform.feedback import get_all_feedback
    from utils.session_client import get_user_supabase_client
    from utils.db.core.session import get_session_id, get_anon_client
    from config import SUPABASE_URL, SUPABASE_ANON_KEY
    import streamlit as st
    from supabase import create_client, Client
    
except ImportError as e:
    logger.error(f"Import-Fehler: {e}")
    print(f"{Fore.RED}Import-Fehler: {e}{Style.RESET_ALL}")
    sys.exit(1)

# Test-Konfiguration
TEST_TEACHER_EMAIL = "test2@test.de"
TEST_TEACHER_PASSWORD = "123456"
TEST_STUDENT_EMAIL = "test1@test.de"  
TEST_STUDENT_PASSWORD = "123456"
TEST_PREFIX = "🧪 TEST"  # Prefix für alle Test-Daten
AI_PROCESSING_TIMEOUT = 30  # 30 Sekunden für AI-Processing


class MockCookies:
    """Mock für Cookie-Dictionary"""
    def __init__(self):
        self._cookies = {}
    
    def get(self, key, default=None):
        return self._cookies.get(key, default)
    
    def __setitem__(self, key, value):
        self._cookies[key] = value
    
    def __getitem__(self, key):
        return self._cookies[key]
    
    def __contains__(self, key):
        return key in self._cookies


class MockContext:
    """Mock für st.context um Cookie-Zugriff zu simulieren"""
    def __init__(self):
        self.cookies = MockCookies()


class ComprehensiveDBTester:
    def __init__(self):
        self.results = []
        self.teacher_session = None
        self.student_session = None
        self.teacher_id = None
        self.student_id = None
        self.test_data = {}
        self.cleanup_items = []  # Track items for cleanup
        self.verbose = True
        self.original_context = None
        
        # Speichere original context und ersetze mit Mock
        if hasattr(st, 'context'):
            self.original_context = st.context
        st.context = MockContext()
        self.log_verbose("Mock Context für Cookies erstellt", "DEBUG")
    
    def log_verbose(self, message, level="INFO"):
        """Verbose Logging mit Farben"""
        if self.verbose:
            colors = {
                "INFO": Fore.CYAN,
                "SUCCESS": Fore.GREEN,
                "WARNING": Fore.YELLOW,
                "ERROR": Fore.RED,
                "DEBUG": Fore.MAGENTA
            }
            color = colors.get(level, Fore.WHITE)
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"{color}[{timestamp}] [{level}] {message}{Style.RESET_ALL}")
            logger.log(getattr(logging, level, logging.INFO), message)
        
    def log_test(self, function_name, ui_page, result, error=None, details=None):
        """Loggt ein Test-Ergebnis mit verbessertem Output"""
        self.results.append({
            'function': function_name,
            'ui_page': ui_page,
            'result': result,
            'error': error,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
        
        # Konsolen-Ausgabe
        status = f"{Fore.GREEN}✅ PASS{Style.RESET_ALL}" if result == "PASS" else f"{Fore.RED}❌ FAIL{Style.RESET_ALL}"
        print(f"\n{status} {function_name} ({ui_page})")
        
        if error:
            print(f"  {Fore.YELLOW}Error: {error}{Style.RESET_ALL}")
            logger.error(f"{function_name}: {error}")
        if details:
            print(f"  {Fore.CYAN}Details: {details}{Style.RESET_ALL}")
            logger.info(f"{function_name}: {details}")
    
    def create_real_session(self, email: str, password: str) -> dict:
        """
        Erstellt eine echte Session durch Supabase Auth und simuliert Cookie-Auth.
        """
        try:
            self.log_verbose(f"Erstelle echte Session für {email}", "INFO")
            
            # Erstelle Supabase Client
            supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            
            # Authentifiziere User
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not auth_response.user:
                raise Exception("Authentication failed")
            
            user = auth_response.user
            session = auth_response.session
            
            self.log_verbose(f"Auth erfolgreich - User ID: {user.id}", "SUCCESS")
            
            # Hole User-Details aus profiles
            client = get_anon_client()
            try:
                profile_result = client.table('profiles').select('*').eq('id', user.id).execute()
                self.log_verbose(f"Profile query result: {profile_result.data}", "DEBUG")
                
                if profile_result.data and len(profile_result.data) > 0:
                    profile = profile_result.data[0]
                else:
                    raise Exception("Kein Profil gefunden")
            except Exception as e:
                # Wenn kein Profil existiert, verwende die Email und setze role auf 'student' oder 'teacher'
                self.log_verbose(f"Fehler beim Profil-Abruf: {e}", "WARNING")
                # Bestimme Rolle basierend auf Email (test2 = teacher, test1 = student)
                role = 'teacher' if 'test2' in email else 'student'
                profile = {
                    'id': user.id,
                    'email': email,
                    'role': role,
                    'full_name': email.split('@')[0]
                }
            
            # Erstelle einen Session-Eintrag in auth_sessions
            session_id = f"test_{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Erstelle Session in auth_sessions Tabelle
            # HINWEIS: Wir nutzen hier den Service-Role-Key NUR für die Session-Erstellung,
            # da dies normalerweise vom Auth-Service (nginx) gemacht wird.
            # Alle weiteren DB-Operationen laufen mit normaler RLS-Überprüfung!
            try:
                from config import SUPABASE_SERVICE_ROLE_KEY
                if SUPABASE_SERVICE_ROLE_KEY:
                    # Service-Client nur für Session-Setup
                    service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
                    session_result = service_client.table('auth_sessions').insert({
                        'session_id': session_id,
                        'user_id': user.id,
                        'user_email': email,
                        'user_role': profile['role'],
                        'expires_at': (datetime.now() + timedelta(hours=1)).isoformat(),
                        'data': {
                            'access_token': session.access_token,
                            'refresh_token': session.refresh_token
                        }
                    }).execute()
                    
                    self.log_verbose(f"Session in auth_sessions erstellt: {session_id}", "SUCCESS")
                    self.cleanup_items.append(('auth_session', session_id))
                else:
                    self.log_verbose("FEHLER: Service-Role-Key benötigt für Session-Setup", "ERROR")
                    self.log_verbose("Setze SUPABASE_SERVICE_ROLE_KEY in .env", "ERROR")
                    raise Exception("Service-Role-Key benötigt für Test-Setup")
            except Exception as e:
                self.log_verbose(f"Fehler beim Erstellen der auth_session: {e}", "ERROR")
                raise
            
            # Simuliere Cookie-Auth durch setzen der session_id als Cookie
            st.context.cookies['gustav_session'] = session_id
            self.log_verbose(f"Mock Cookie gesetzt: gustav_session={session_id}", "DEBUG")
            
            # Setze session_state für get_user_supabase_client()
            st.session_state.session = {
                'access_token': session.access_token,
                'refresh_token': session.refresh_token,
                'user': {
                    'id': user.id,
                    'email': email,
                    'role': profile['role']
                }
            }
            st.session_state.user = {
                'id': user.id,
                'email': email,
                'role': profile['role']
            }
            
            self.log_verbose(f"Session State konfiguriert", "SUCCESS")
            
            return {
                'id': user.id,
                'email': profile['email'],
                'role': profile['role'],
                'display_name': profile.get('full_name', email.split('@')[0]),
                'session_id': session_id,  # Use the auth_sessions ID
                'access_token': session.access_token,
                'refresh_token': session.refresh_token,
                'is_test': False
            }
            
        except Exception as e:
            self.log_verbose(f"Fehler bei Session-Erstellung: {e}", "ERROR")
            logger.exception("Session creation failed")
            raise
    
    def setup_sessions(self):
        """Erstellt echte Test-Sessions für Lehrer und Schüler"""
        print(f"\n{Fore.BLUE}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}=== SETUP: Erstelle echte Sessions ==={Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*60}{Style.RESET_ALL}\n")
        
        try:
            # Streamlit Session State initialisieren
            st.session_state.clear()
            
            # Erstelle Lehrer-Session
            self.log_verbose(f"Erstelle Session für Lehrer: {TEST_TEACHER_EMAIL}", "INFO")
            self.teacher_session = self.create_real_session(TEST_TEACHER_EMAIL, TEST_TEACHER_PASSWORD)
            self.teacher_id = self.teacher_session['id']
            print(f"  {Fore.GREEN}✓ Lehrer-Session erstellt{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}  ID: {self.teacher_id}{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}  Session: {self.teacher_session['session_id'][:16]}...{Style.RESET_ALL}")
            
            # Erstelle Schüler-Session  
            self.log_verbose(f"Erstelle Session für Schüler: {TEST_STUDENT_EMAIL}", "INFO")
            self.student_session = self.create_real_session(TEST_STUDENT_EMAIL, TEST_STUDENT_PASSWORD)
            self.student_id = self.student_session['id']
            print(f"  {Fore.GREEN}✓ Schüler-Session erstellt{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}  ID: {self.student_id}{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}  Session: {self.student_session['session_id'][:16]}...{Style.RESET_ALL}")
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Setup fehlgeschlagen: {e}{Style.RESET_ALL}")
            logger.exception("Setup failed")
            return False
    
    def set_session_id(self, session_id):
        """Setzt die Session-ID für DB-Operationen"""
        # Update Cookie
        st.context.cookies['gustav_session'] = session_id
        
        # Finde die richtige Session-Info
        session_info = None
        if self.teacher_session and self.teacher_session['session_id'] == session_id:
            session_info = self.teacher_session
        elif self.student_session and self.student_session['session_id'] == session_id:
            session_info = self.student_session
        
        if session_info:
            # Update session_state
            st.session_state.session = {
                'access_token': session_info['access_token'],
                'refresh_token': session_info['refresh_token'],
                'user': {
                    'id': session_info['id'],
                    'email': session_info['email'],
                    'role': session_info['role']
                }
            }
            st.session_state.user = {
                'id': session_info['id'],
                'email': session_info['email'],
                'role': session_info['role']
            }
            # Clear cached client to force recreation with new session
            if 'user_supabase_client' in st.session_state:
                del st.session_state.user_supabase_client
                
        self.log_verbose(f"Session gewechselt zu: {session_id[:16]}...", "DEBUG")
    
    def create_test_data(self):
        """Erstellt alle benötigten Test-Daten mit Logging"""
        print(f"\n{Fore.BLUE}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}=== ERSTELLE TEST-DATEN ==={Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*60}{Style.RESET_ALL}\n")
        
        try:
            # Als Lehrer einloggen
            self.set_session_id(self.teacher_session['session_id'])
            
            # 1. Test-Kurs erstellen
            course_name = f"{TEST_PREFIX} Kurs {datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.log_verbose(f"Erstelle Test-Kurs: {course_name}", "INFO")
            
            course, error = create_course(course_name, self.teacher_id)
            if error:
                self.log_verbose(f"Fehler beim Kurs erstellen: {error}", "ERROR")
                return False
            
            self.test_data['course'] = course
            self.cleanup_items.append(('course', course['id']))
            print(f"  {Fore.GREEN}✓ Kurs erstellt: {course['id']}{Style.RESET_ALL}")
            self.log_verbose(f"Kurs erfolgreich erstellt: {json.dumps(course)}", "DEBUG")
            
            # 2. Schüler zum Kurs hinzufügen
            self.log_verbose(f"Füge Schüler {self.student_id} zum Kurs hinzu", "INFO")
            success, error = add_user_to_course(self.test_data['course']['id'], self.student_id, 'student')
            if not success:
                self.log_verbose(f"Fehler beim Hinzufügen des Schülers: {error}", "ERROR")
            else:
                print(f"  {Fore.GREEN}✓ Schüler hinzugefügt{Style.RESET_ALL}")
            
            # 3. Test-Lerneinheit erstellen
            unit_title = f"{TEST_PREFIX} Lerneinheit {datetime.now().strftime('%H%M%S')}"
            print(f"Erstelle Test-Lerneinheit: {unit_title}")
            unit, error = create_learning_unit(unit_title, self.teacher_id)
            if error:
                print(f"  {Fore.RED}✗ Fehler: {error}{Style.RESET_ALL}")
                return False
            self.test_data['unit'] = unit
            self.cleanup_items.append(('unit', unit['id']))
            print(f"  {Fore.GREEN}✓ Lerneinheit erstellt: {unit['id']}{Style.RESET_ALL}")
            
            # 4. Lerneinheit zum Kurs zuweisen
            print(f"Weise Lerneinheit dem Kurs zu")
            success, error = assign_unit_to_course(self.test_data['unit']['id'], self.test_data['course']['id'])
            if not success:
                print(f"  {Fore.RED}✗ Fehler: {error}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.GREEN}✓ Lerneinheit zugewiesen{Style.RESET_ALL}")
            
            # 5. Test-Section erstellen
            section_title = f"{TEST_PREFIX} Abschnitt 1"
            print(f"Erstelle Test-Section: {section_title}")
            section, error = create_section(self.test_data['unit']['id'], section_title, 0)
            if error:
                print(f"  {Fore.RED}✗ Fehler: {error}{Style.RESET_ALL}")
                return False
            self.test_data['section'] = section
            self.cleanup_items.append(('section', section['id']))
            print(f"  {Fore.GREEN}✓ Section erstellt: {section['id']}{Style.RESET_ALL}")
            
            # 6. Test-Materials hinzufügen
            materials = [
                {'type': 'markdown', 'title': 'Test Material', 'content': '# Test Content\nDies ist ein Test.'},
                {'type': 'link', 'title': 'Test Link', 'content': 'https://example.com'}
            ]
            print(f"Füge Materialien zur Section hinzu")
            success, error = update_section_materials(self.test_data['section']['id'], materials)
            if not success:
                print(f"  {Fore.RED}✗ Fehler: {error}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.GREEN}✓ Materialien hinzugefügt{Style.RESET_ALL}")
            
            # 7. Test-Task (Regular) erstellen
            print(f"Erstelle Regular Task")
            task_data = {
                'title': f"{TEST_PREFIX} Regular Task",
                'prompt': 'Was ist 2+2?',
                'max_attempts': 3,
                'grading_criteria': ['Die Antwort sollte 4 sein.']
            }
            task, error = create_regular_task(
                self.test_data['section']['id'],
                task_data['prompt'],  # instruction
                'text_input',  # task_type
                1,  # order_in_section
                task_data['max_attempts'],
                task_data['grading_criteria'],  # assessment_criteria als Liste
                'Denke an die Grundrechenarten'  # solution_hints
            )
            if error:
                print(f"  {Fore.RED}✗ Fehler: {error}{Style.RESET_ALL}")
            else:
                self.test_data['regular_task'] = task
                self.cleanup_items.append(('task', task['id']))
                print(f"  {Fore.GREEN}✓ Regular Task erstellt: {task['id']}{Style.RESET_ALL}")
            
            # 8. Test-Task (Mastery) erstellen
            print(f"Erstelle Mastery Task")
            mastery_data = {
                'title': f"{TEST_PREFIX} Mastery Task",
                'prompt': 'Erkläre das Konzept der Addition.',
                'difficulty_level': 1,
                'concept_explanation': 'Addition ist eine Grundrechenart...'
            }
            mastery_task, error = create_mastery_task(
                self.test_data['section']['id'],
                mastery_data['prompt'],  # instruction
                'text_input',  # task_type
                ['Erklärung sollte klar und verständlich sein'],  # assessment_criteria
                'Addition bedeutet Zusammenzählen'  # solution_hints
            )
            if error:
                print(f"  {Fore.RED}✗ Fehler: {error}{Style.RESET_ALL}")
            else:
                self.test_data['mastery_task'] = mastery_task
                self.cleanup_items.append(('task', mastery_task['id']))
                print(f"  {Fore.GREEN}✓ Mastery Task erstellt: {mastery_task['id']}{Style.RESET_ALL}")
            
            # 9. Section für Kurs veröffentlichen
            print(f"Veröffentliche Section für Kurs")
            success, error = publish_section_for_course(self.test_data['section']['id'], self.test_data['course']['id'])
            if not success:
                print(f"  {Fore.RED}✗ Fehler: {error}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.GREEN}✓ Section veröffentlicht{Style.RESET_ALL}")
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Fehler beim Erstellen der Test-Daten: {e}{Style.RESET_ALL}")
            logger.exception("Test data creation failed")
            return False
    
    def wait_for_ai_processing(self, submission_id: str, timeout: int = AI_PROCESSING_TIMEOUT):
        """Wartet auf AI-Processing mit Progress-Anzeige"""
        start_time = time.time()
        print(f"\n  {Fore.YELLOW}⏳ Warte auf AI-Processing (max. {timeout}s)...{Style.RESET_ALL}")
        
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            
            # Progress Bar
            progress = elapsed / timeout
            bar_length = 40
            filled = int(bar_length * progress)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"\r  [{bar}] {elapsed}s / {timeout}s", end='', flush=True)
            
            # Check submission status
            submission, error = get_submission_by_id(submission_id)
            if submission and not submission.get('is_processing', True):
                print(f"\r  {Fore.GREEN}✓ AI-Processing abgeschlossen nach {elapsed}s{Style.RESET_ALL}" + " " * 20)
                return submission
            
            time.sleep(1)
        
        print(f"\r  {Fore.YELLOW}⚠ Timeout nach {timeout}s erreicht{Style.RESET_ALL}" + " " * 20)
        return None

    def test_all_functions(self):
        """Testet systematisch ALLE DB-Funktionen"""
        
        # Test-Kategorien nach UI-Seiten und Modulen
        self.test_auth_and_core_functions()
        self.test_kurse_functions()
        self.test_lerneinheiten_functions() 
        self.test_schueler_functions()
        self.test_live_unterricht_functions()
        self.test_meine_aufgaben_functions()
        self.test_wissensfestiger_functions()
        self.test_feedback_functions()
        self.test_sections_tasks_functions()
        self.test_enrollment_functions()
        self.test_progress_functions()
        self.test_mastery_functions()

    def test_kurse_functions(self):
        """Testet alle Funktionen von 1_Kurse.py"""
        print(f"\n{Fore.BLUE}=== TESTE: Kurse Funktionen (1_Kurse.py) ==={Style.RESET_ALL}")
        
        self.set_session_id(self.teacher_session['session_id'])
        
        # Test: get_courses_by_creator
        try:
            courses, error = get_courses_by_creator(self.teacher_id)
            if error:
                self.log_test('get_courses_by_creator', '1_Kurse.py', 'FAIL', error)
            else:
                # Sollte mindestens unseren Test-Kurs finden
                test_courses = [c for c in courses if TEST_PREFIX in c.get('name', '')]
                self.log_test('get_courses_by_creator', '1_Kurse.py', 'PASS',
                            details=f"Found {len(courses)} courses, {len(test_courses)} test courses")
        except Exception as e:
            self.log_test('get_courses_by_creator', '1_Kurse.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_course_by_id  
        try:
            if 'course' in self.test_data:
                course, error = get_course_by_id(self.test_data['course']['id'])
                if error:
                    self.log_test('get_course_by_id', '1_Kurse.py', 'FAIL', error)
                else:
                    self.log_test('get_course_by_id', '1_Kurse.py', 'PASS',
                                details=f"Got course: {course.get('name')}")
        except Exception as e:
            self.log_test('get_course_by_id', '1_Kurse.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: update_course
        try:
            if 'course' in self.test_data:
                new_name = f"{self.test_data['course']['name']} - Updated"
                success, error = update_course(self.test_data['course']['id'], new_name)
                if not success:
                    self.log_test('update_course', '1_Kurse.py', 'FAIL', error)
                else:
                    self.log_test('update_course', '1_Kurse.py', 'PASS',
                                details=f"Updated name to: {new_name}")
        except Exception as e:
            self.log_test('update_course', '1_Kurse.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_course_students
        try:
            if 'course' in self.test_data:
                students, error = get_course_students(self.test_data['course']['id'])
                if error:
                    self.log_test('get_course_students', '1_Kurse.py', 'FAIL', error)
                else:
                    self.log_test('get_course_students', '1_Kurse.py', 'PASS',
                                details=f"Found {len(students) if students else 0} students")
        except Exception as e:
            self.log_test('get_course_students', '1_Kurse.py', 'FAIL', str(e))
            traceback.print_exc()

        # create_course wurde bereits in create_test_data getestet

    def test_lerneinheiten_functions(self):
        """Testet alle Funktionen von 2_Lerneinheiten.py"""
        print(f"\n{Fore.BLUE}=== TESTE: Lerneinheiten Funktionen (2_Lerneinheiten.py) ==={Style.RESET_ALL}")
        
        self.set_session_id(self.teacher_session['session_id'])
        
        # Test: get_learning_units_by_creator
        try:
            units, error = get_learning_units_by_creator(self.teacher_id)
            if error:
                self.log_test('get_learning_units_by_creator', '2_Lerneinheiten.py', 'FAIL', error)
            else:
                test_units = [u for u in units if TEST_PREFIX in u.get('title', '')]
                self.log_test('get_learning_units_by_creator', '2_Lerneinheiten.py', 'PASS',
                            details=f"Found {len(units)} units, {len(test_units)} test units")
        except Exception as e:
            self.log_test('get_learning_units_by_creator', '2_Lerneinheiten.py', 'FAIL', str(e))
            traceback.print_exc()
        
        # Test: get_learning_unit_by_id
        try:
            if 'unit' in self.test_data:
                unit, error = get_learning_unit_by_id(self.test_data['unit']['id'])
                if error:
                    self.log_test('get_learning_unit_by_id', '2_Lerneinheiten.py', 'FAIL', error)
                else:
                    self.log_test('get_learning_unit_by_id', '2_Lerneinheiten.py', 'PASS',
                                details=f"Got unit: {unit.get('title')}")
        except Exception as e:
            self.log_test('get_learning_unit_by_id', '2_Lerneinheiten.py', 'FAIL', str(e))
            traceback.print_exc()
        
        # Test: get_assigned_units_for_course
        try:
            if 'course' in self.test_data:
                units, error = get_assigned_units_for_course(self.test_data['course']['id'])
                if error:
                    self.log_test('get_assigned_units_for_course', '2_Lerneinheiten.py', 'FAIL', error)
                else:
                    self.log_test('get_assigned_units_for_course', '2_Lerneinheiten.py', 'PASS',
                                details=f"Found {len(units) if units else 0} assigned units")
        except Exception as e:
            self.log_test('get_assigned_units_for_course', '2_Lerneinheiten.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: update_learning_unit
        try:
            if 'unit' in self.test_data:
                new_title = f"{self.test_data['unit']['title']} - Updated"
                success, error = update_learning_unit(self.test_data['unit']['id'], new_title)
                if not success:
                    self.log_test('update_learning_unit', '2_Lerneinheiten.py', 'FAIL', error)
                else:
                    self.log_test('update_learning_unit', '2_Lerneinheiten.py', 'PASS',
                                details=f"Updated title to: {new_title}")
        except Exception as e:
            self.log_test('update_learning_unit', '2_Lerneinheiten.py', 'FAIL', str(e))
            traceback.print_exc()

    def test_schueler_functions(self):
        """Testet alle Funktionen von 5_Schueler.py"""
        print(f"\n{Fore.BLUE}=== TESTE: Schüler Funktionen (5_Schueler.py) ==={Style.RESET_ALL}")
        
        self.set_session_id(self.teacher_session['session_id'])
        
        # Test: get_students_in_course
        try:
            if 'course' in self.test_data:
                students, error = get_students_in_course(self.test_data['course']['id'])
                if error:
                    self.log_test('get_students_in_course', '5_Schueler.py', 'FAIL', error)
                else:
                    # Sollte mindestens unseren Test-Schüler enthalten
                    has_test_student = any(s['id'] == self.student_id for s in students)
                    self.log_test('get_students_in_course', '5_Schueler.py', 'PASS',
                                details=f"Found {len(students)} students, test student included: {has_test_student}")
        except Exception as e:
            self.log_test('get_students_in_course', '5_Schueler.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_teachers_in_course
        try:
            if 'course' in self.test_data:
                teachers, error = get_teachers_in_course(self.test_data['course']['id'])
                if error:
                    self.log_test('get_teachers_in_course', '5_Schueler.py', 'FAIL', error)
                else:
                    # Sollte mindestens unseren Test-Lehrer enthalten
                    has_test_teacher = any(t['id'] == self.teacher_id for t in teachers)
                    self.log_test('get_teachers_in_course', '5_Schueler.py', 'PASS',
                                details=f"Found {len(teachers)} teachers, test teacher included: {has_test_teacher}")
        except Exception as e:
            self.log_test('get_teachers_in_course', '5_Schueler.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: remove_user_from_course und wieder hinzufügen
        try:
            if 'course' in self.test_data:
                # Entfernen
                success, error = remove_user_from_course(self.test_data['course']['id'], self.student_id, 'student')
                if not success:
                    self.log_test('remove_user_from_course', '5_Schueler.py', 'FAIL', error)
                else:
                    self.log_test('remove_user_from_course', '5_Schueler.py', 'PASS',
                                details=f"Removed student from course")
                    
                # Wieder hinzufügen
                success, error = add_user_to_course(self.test_data['course']['id'], self.student_id, 'student')
                if not success:
                    self.log_test('add_user_to_course', '5_Schueler.py', 'FAIL', error)
                else:
                    self.log_test('add_user_to_course', '5_Schueler.py', 'PASS',
                                details=f"Re-added student to course")
        except Exception as e:
            self.log_test('remove_user_from_course', '5_Schueler.py', 'FAIL', str(e))
            traceback.print_exc()

    def test_live_unterricht_functions(self):
        """Testet alle Funktionen von 6_Live-Unterricht.py"""
        print(f"\n{Fore.BLUE}=== TESTE: Live-Unterricht Funktionen (6_Live-Unterricht.py) ==={Style.RESET_ALL}")
        
        self.set_session_id(self.teacher_session['session_id'])
        
        # Test: get_sections_for_unit
        try:
            if 'unit' in self.test_data:
                sections, error = get_sections_for_unit(self.test_data['unit']['id'])
                if error:
                    self.log_test('get_sections_for_unit', '6_Live-Unterricht.py', 'FAIL', error)
                else:
                    self.log_test('get_sections_for_unit', '6_Live-Unterricht.py', 'PASS', 
                                details=f"Found {len(sections) if sections else 0} sections")
        except Exception as e:
            self.log_test('get_sections_for_unit', '6_Live-Unterricht.py', 'FAIL', str(e))
            traceback.print_exc()
        
        # Test: get_section_statuses_for_unit_in_course
        try:
            if all(key in self.test_data for key in ['unit', 'course']):
                statuses, error = get_section_statuses_for_unit_in_course(
                    self.test_data['unit']['id'], 
                    self.test_data['course']['id']
                )
                if error:
                    self.log_test('get_section_statuses_for_unit_in_course', '6_Live-Unterricht.py', 'FAIL', error)
                else:
                    # Sollte unsere veröffentlichte Section enthalten
                    published_count = sum(1 for status in statuses.values() if status) if isinstance(statuses, dict) else 0
                    self.log_test('get_section_statuses_for_unit_in_course', '6_Live-Unterricht.py', 'PASS',
                                details=f"Status type: {type(statuses)}, published sections: {published_count}")
        except Exception as e:
            self.log_test('get_section_statuses_for_unit_in_course', '6_Live-Unterricht.py', 'FAIL', str(e))
            traceback.print_exc()
        
        # Test: unpublish_section_for_course und wieder publish
        try:
            if all(key in self.test_data for key in ['section', 'course']):
                # Unpublish
                success, error = unpublish_section_for_course(
                    self.test_data['section']['id'],
                    self.test_data['course']['id']
                )
                if not success:
                    self.log_test('unpublish_section_for_course', '6_Live-Unterricht.py', 'FAIL', error)
                else:
                    self.log_test('unpublish_section_for_course', '6_Live-Unterricht.py', 'PASS',
                                details="Section unpublished")
                
                # Re-publish
                success, error = publish_section_for_course(
                    self.test_data['section']['id'],
                    self.test_data['course']['id']
                )
                if not success:
                    self.log_test('publish_section_for_course', '6_Live-Unterricht.py', 'FAIL', error)
                else:
                    self.log_test('publish_section_for_course', '6_Live-Unterricht.py', 'PASS',
                                details="Section re-published")
        except Exception as e:
            self.log_test('unpublish_section_for_course', '6_Live-Unterricht.py', 'FAIL', str(e))
            traceback.print_exc()
        
        # Test: get_submission_status_matrix
        try:
            if all(key in self.test_data for key in ['course', 'unit']):
                matrix, error = get_submission_status_matrix(
                    self.test_data['course']['id'],
                    self.test_data['unit']['id']
                )
                if error:
                    self.log_test('get_submission_status_matrix', '6_Live-Unterricht.py', 'FAIL', error)
                elif not matrix:
                    self.log_test('get_submission_status_matrix', '6_Live-Unterricht.py', 'FAIL', 
                                "Matrix ist None/leer")
                else:
                    sections_count = len(matrix.get('sections', []))
                    students_count = len(matrix.get('students', []))
                    total_tasks = matrix.get('total_tasks', 0)
                    
                    self.log_test('get_submission_status_matrix', '6_Live-Unterricht.py', 'PASS',
                                details=f"Sections: {sections_count}, Students: {students_count}, Tasks: {total_tasks}")
                    
                    # Debug-Info ausgeben falls vorhanden
                    if 'debug_info' in matrix:
                        print(f"  {Fore.MAGENTA}Debug-Info: {json.dumps(matrix['debug_info'], indent=2)}{Style.RESET_ALL}")
        except Exception as e:
            self.log_test('get_submission_status_matrix', '6_Live-Unterricht.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_task_details (wird nach Task-Erstellung getestet)
        try:
            if 'regular_task' in self.test_data:
                task, error = get_task_details(self.test_data['regular_task']['id'])
                if error:
                    self.log_test('get_task_details', '6_Live-Unterricht.py', 'FAIL', error)
                else:
                    self.log_test('get_task_details', '6_Live-Unterricht.py', 'PASS',
                                details=f"Got task: {task.get('title')}, type: {task.get('task_type')}")
        except Exception as e:
            self.log_test('get_task_details', '6_Live-Unterricht.py', 'FAIL', str(e))
            traceback.print_exc()

    def test_meine_aufgaben_functions(self):
        """Testet alle Funktionen von 3_Meine_Aufgaben.py mit AI-Timeout"""
        print(f"\n{Fore.BLUE}=== TESTE: Meine Aufgaben Funktionen (3_Meine_Aufgaben.py) ==={Style.RESET_ALL}")
        
        # Als Schüler einloggen
        self.set_session_id(self.student_session['session_id'])
        
        # Test: get_published_section_details_for_student
        try:
            self.log_verbose("Teste get_published_section_details_for_student", "INFO")
            if all(key in self.test_data for key in ['unit', 'course']):
                details, error = get_published_section_details_for_student(
                    self.test_data['unit']['id'],
                    self.test_data['course']['id'],
                    self.student_id
                )
                if error:
                    self.log_test('get_published_section_details_for_student', '3_Meine_Aufgaben.py', 'FAIL', error)
                else:
                    section_count = len(details) if details else 0
                    task_count = sum(len(s.get('tasks', [])) for s in details) if details else 0
                    self.log_test('get_published_section_details_for_student', '3_Meine_Aufgaben.py', 'PASS',
                                details=f"Found {section_count} sections with {task_count} tasks")
                    self.log_verbose(f"Section details: {json.dumps(details, indent=2)}", "DEBUG")
        except Exception as e:
            self.log_test('get_published_section_details_for_student', '3_Meine_Aufgaben.py', 'FAIL', str(e))
            logger.exception("Test failed")

        # Test: get_remaining_attempts
        try:
            if 'regular_task' in self.test_data:
                remaining, max_attempts, error = get_remaining_attempts(self.student_id, self.test_data['regular_task']['id'])
                if error:
                    self.log_test('get_remaining_attempts', '3_Meine_Aufgaben.py', 'FAIL', error)
                else:
                    self.log_test('get_remaining_attempts', '3_Meine_Aufgaben.py', 'PASS',
                                details=f"Remaining: {remaining}, Max: {max_attempts}")
        except Exception as e:
            self.log_test('get_remaining_attempts', '3_Meine_Aufgaben.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: create_submission mit AI-Processing Timeout
        submission_id = None
        try:
            self.log_verbose("Teste create_submission", "INFO")
            if 'regular_task' in self.test_data:
                submission, error = create_submission(
                    self.student_id,
                    self.test_data['regular_task']['id'],
                    "Die Antwort ist 4"
                )
                if error:
                    self.log_test('create_submission', '3_Meine_Aufgaben.py', 'FAIL', error)
                else:
                    submission_id = submission.get('id')
                    self.test_data['submission'] = submission
                    self.cleanup_items.append(('submission', submission_id))
                    self.log_test('create_submission', '3_Meine_Aufgaben.py', 'PASS',
                                details=f"Created submission: {submission_id}")
                    
                    # Warte auf AI-Processing mit verbessertem Timeout
                    processed_submission = self.wait_for_ai_processing(submission_id)
                    if processed_submission:
                        self.log_verbose(f"AI-Feedback erhalten: {processed_submission.get('ai_feedback', 'Kein Feedback')}", "SUCCESS")
                    else:
                        self.log_verbose("AI-Processing Timeout erreicht", "WARNING")
                        
        except Exception as e:
            self.log_test('create_submission', '3_Meine_Aufgaben.py', 'FAIL', str(e))
            logger.exception("Test failed")

        # Test: get_submission_by_id
        try:
            if submission_id:
                self.log_verbose("Teste get_submission_by_id", "INFO")
                submission, error = get_submission_by_id(submission_id)
                if error:
                    self.log_test('get_submission_by_id', '3_Meine_Aufgaben.py', 'FAIL', error)
                else:
                    self.log_test('get_submission_by_id', '3_Meine_Aufgaben.py', 'PASS',
                                details=f"Got submission, is_processing: {submission.get('is_processing')}")
        except Exception as e:
            self.log_test('get_submission_by_id', '3_Meine_Aufgaben.py', 'FAIL', str(e))
            logger.exception("Test failed")

        # Test: get_submission_history
        try:
            if 'regular_task' in self.test_data:
                history, error = get_submission_history(self.student_id, self.test_data['regular_task']['id'])
                if error:
                    self.log_test('get_submission_history', '3_Meine_Aufgaben.py', 'FAIL', error)
                else:
                    self.log_test('get_submission_history', '3_Meine_Aufgaben.py', 'PASS',
                                details=f"Found {len(history) if history else 0} submissions in history")
        except Exception as e:
            self.log_test('get_submission_history', '3_Meine_Aufgaben.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_submission_for_task (als Lehrer)
        self.set_session_id(self.teacher_session['session_id'])
        try:
            if 'regular_task' in self.test_data:
                submission, error = get_submission_for_task(self.student_id, self.test_data['regular_task']['id'])
                if error:
                    self.log_test('get_submission_for_task', '6_Live-Unterricht.py', 'FAIL', error)
                else:
                    self.log_test('get_submission_for_task', '6_Live-Unterricht.py', 'PASS',
                                details=f"Got submission: {submission.get('id') if submission else 'None'}")
        except Exception as e:
            self.log_test('get_submission_for_task', '6_Live-Unterricht.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: update_submission_teacher_override
        try:
            if submission_id:
                success, error = update_submission_teacher_override(
                    submission_id,
                    "Sehr gut gemacht!",
                    "100"
                )
                if not success:
                    self.log_test('update_submission_teacher_override', '6_Live-Unterricht.py', 'FAIL', error)
                else:
                    self.log_test('update_submission_teacher_override', '6_Live-Unterricht.py', 'PASS',
                                details="Teacher override added")
        except Exception as e:
            self.log_test('update_submission_teacher_override', '6_Live-Unterricht.py', 'FAIL', str(e))
            traceback.print_exc()

    def test_wissensfestiger_functions(self):
        """Testet alle Funktionen von 7_Wissensfestiger.py"""
        print(f"\n{Fore.BLUE}=== TESTE: Wissensfestiger Funktionen (7_Wissensfestiger.py) ==={Style.RESET_ALL}")
        
        # Als Schüler einloggen
        self.set_session_id(self.student_session['session_id'])

        # Test: get_user_course_ids
        try:
            course_ids = get_user_course_ids(self.student_id)
            has_test_course = self.test_data.get('course', {}).get('id') in course_ids if course_ids else False
            self.log_test('get_user_course_ids', '7_Wissensfestiger.py', 'PASS',
                            details=f"Found {len(course_ids) if course_ids else 0} course IDs, test course included: {has_test_course}")
        except Exception as e:
            self.log_test('get_user_course_ids', '7_Wissensfestiger.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_next_mastery_task_or_unviewed_feedback
        try:
            if 'course' in self.test_data:
                result = get_next_mastery_task_or_unviewed_feedback(
                    self.student_id,
                    self.test_data['course']['id']
                )
                if result.get('error'):
                    self.log_test('get_next_mastery_task_or_unviewed_feedback', '7_Wissensfestiger.py', 'FAIL', result.get('error'))
                else:
                    result_type = result.get('type') if result else 'None'
                    self.log_test('get_next_mastery_task_or_unviewed_feedback', '7_Wissensfestiger.py', 'PASS',
                                details=f"Result type: {result_type}")
        except Exception as e:
            self.log_test('get_next_mastery_task_or_unviewed_feedback', '7_Wissensfestiger.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: create mastery submission
        mastery_submission_id = None
        try:
            self.log_verbose("Teste create_submission für Mastery Task", "INFO")
            if 'mastery_task' in self.test_data:
                submission, error = create_submission(
                    self.student_id,
                    self.test_data['mastery_task']['id'],
                    {'answer': 'Addition bedeutet, dass man zwei oder mehr Zahlen zusammenzählt.'}
                )
                if error:
                    self.log_test('create_submission (mastery)', '7_Wissensfestiger.py', 'FAIL', error)
                else:
                    mastery_submission_id = submission.get('id')
                    self.test_data['mastery_submission'] = submission
                    self.cleanup_items.append(('submission', mastery_submission_id))
                    self.log_test('create_submission (mastery)', '7_Wissensfestiger.py', 'PASS',
                                details=f"Created mastery submission: {mastery_submission_id}")
                    
                    # Warte auf AI-Processing für Mastery Task
                    processed_submission = self.wait_for_ai_processing(mastery_submission_id)
                    if processed_submission:
                        self.log_verbose(f"Mastery AI-Feedback erhalten: {processed_submission.get('ai_feedback', 'Kein Feedback')}", "SUCCESS")
                    else:
                        self.log_verbose("Mastery AI-Processing Timeout erreicht", "WARNING")
                        
        except Exception as e:
            self.log_test('create_submission (mastery)', '7_Wissensfestiger.py', 'FAIL', str(e))
            logger.exception("Test failed")

        # Test: mark_feedback_as_viewed_safe
        try:
            if mastery_submission_id:
                self.log_verbose("Teste mark_feedback_as_viewed_safe", "INFO")
                success, error = mark_feedback_as_viewed_safe(mastery_submission_id)
                if not success:
                    self.log_test('mark_feedback_as_viewed_safe', '7_Wissensfestiger.py', 'FAIL', error)
                else:
                    self.log_test('mark_feedback_as_viewed_safe', '7_Wissensfestiger.py', 'PASS',
                                details="Marked feedback as viewed")
        except Exception as e:
            self.log_test('mark_feedback_as_viewed_safe', '7_Wissensfestiger.py', 'FAIL', str(e))
            traceback.print_exc()

    def test_feedback_functions(self):
        """Testet Feedback-Funktionen"""
        print(f"\n{Fore.BLUE}=== TESTE: Feedback Funktionen (9_Feedback_einsehen.py) ==={Style.RESET_ALL}")
        
        # Als Lehrer einloggen
        self.set_session_id(self.teacher_session['session_id'])
        
        # Test: get_all_feedback
        try:
            feedback = get_all_feedback()
            self.log_test('get_all_feedback', '9_Feedback_einsehen.py', 'PASS',
                        details=f"Found {len(feedback) if feedback else 0} feedback entries")
        except Exception as e:
            self.log_test('get_all_feedback', '9_Feedback_einsehen.py', 'FAIL', str(e))
            traceback.print_exc()

        # Test: submit_feedback (als Schüler)
        self.set_session_id(self.student_session['session_id'])
        try:
            success = submit_feedback('bug', f'{TEST_PREFIX} Test-Feedback: Das ist ein Test-Bug-Report')
            if not success:
                self.log_test('submit_feedback', '8_Feedback.py', 'FAIL', "Submit feedback returned False")
            else:
                self.log_test('submit_feedback', '8_Feedback.py', 'PASS',
                            details="Feedback submitted")
        except Exception as e:
            self.log_test('submit_feedback', '8_Feedback.py', 'FAIL', str(e))
            traceback.print_exc()

    def test_sections_tasks_functions(self):
        """Testet weitere Section und Task Funktionen"""
        print(f"\n{Fore.BLUE}=== TESTE: Section & Task Management Funktionen ==={Style.RESET_ALL}")
        
        self.set_session_id(self.teacher_session['session_id'])

        # Test: get_tasks_for_section
        try:
            if 'section' in self.test_data:
                tasks, error = get_tasks_for_section(self.test_data['section']['id'])
                if error:
                    self.log_test('get_tasks_for_section', 'intern', 'FAIL', error)
                else:
                    self.log_test('get_tasks_for_section', 'intern', 'PASS',
                                details=f"Found {len(tasks) if tasks else 0} tasks")
        except Exception as e:
            self.log_test('get_tasks_for_section', 'intern', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_regular_tasks_for_section
        try:
            if 'section' in self.test_data:
                tasks, error = get_regular_tasks_for_section(self.test_data['section']['id'])
                if error:
                    self.log_test('get_regular_tasks_for_section', 'intern', 'FAIL', error)
                else:
                    self.log_test('get_regular_tasks_for_section', 'intern', 'PASS',
                                details=f"Found {len(tasks) if tasks else 0} regular tasks")
        except Exception as e:
            self.log_test('get_regular_tasks_for_section', 'intern', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_mastery_tasks_for_section
        try:
            if 'section' in self.test_data:
                tasks, error = get_mastery_tasks_for_section(self.test_data['section']['id'])
                if error:
                    self.log_test('get_mastery_tasks_for_section', 'intern', 'FAIL', error)
                else:
                    self.log_test('get_mastery_tasks_for_section', 'intern', 'PASS',
                                details=f"Found {len(tasks) if tasks else 0} mastery tasks")
        except Exception as e:
            self.log_test('get_mastery_tasks_for_section', 'intern', 'FAIL', str(e))
            traceback.print_exc()

        # Test: create_task_in_new_structure
        try:
            if 'section' in self.test_data:
                task_data = {
                    'section_id': self.test_data['section']['id'],
                    'is_mastery': False,
                    'instruction': 'Test prompt',
                    'task_type': 'regular',
                    'order_in_section': 1,
                    'max_attempts': 2,
                    'assessment_criteria': ['Test criteria'],
                    'solution_hints': 'Test hints'
                }
                task, error = create_task_in_new_structure(task_data)
                if error:
                    self.log_test('create_task_in_new_structure', 'intern', 'FAIL', error)
                else:
                    self.cleanup_items.append(('task', task['id']))
                    self.log_test('create_task_in_new_structure', 'intern', 'PASS',
                                details=f"Created task via router: {task['id']}")
        except Exception as e:
            self.log_test('create_task_in_new_structure', 'intern', 'FAIL', str(e))
            traceback.print_exc()

        # Test: move_task_up / move_task_down
        try:
            if 'regular_task' in self.test_data:
                # Move down
                success, error = move_task_down(self.test_data['regular_task']['id'], self.test_data['section']['id'])
                if not success:
                    self.log_test('move_task_down', 'intern', 'FAIL', error)
                else:
                    self.log_test('move_task_down', 'intern', 'PASS', details="Task moved down")
                
                # Move up
                success, error = move_task_up(self.test_data['regular_task']['id'], self.test_data['section']['id'])
                if not success:
                    self.log_test('move_task_up', 'intern', 'FAIL', error)
                else:
                    self.log_test('move_task_up', 'intern', 'PASS', details="Task moved up")
        except Exception as e:
            self.log_test('move_task_up/down', 'intern', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_section_tasks
        try:
            if 'section' in self.test_data:
                tasks, error = get_section_tasks(self.test_data['section']['id'])
                if error:
                    self.log_test('get_section_tasks', 'intern', 'FAIL', error)
                else:
                    self.log_test('get_section_tasks', 'intern', 'PASS',
                                details=f"Found {len(tasks) if tasks else 0} task items")
        except Exception as e:
            self.log_test('get_section_tasks', 'intern', 'FAIL', str(e))
            traceback.print_exc()

        # Test: update_task_in_new_structure
        try:
            if 'regular_task' in self.test_data:
                task_data = {
                    'instruction': f"{self.test_data['regular_task']['instruction']} - Updated",
                    'max_attempts': 5,
                    'assessment_criteria': ['Updated criteria 1', 'Updated criteria 2']  # Array, not string
                }
                task, error = update_task_in_new_structure(
                    self.test_data['regular_task']['id'],
                    task_data
                )
                success = task is not None
                if not success:
                    self.log_test('update_task_in_new_structure', 'intern', 'FAIL', error)
                else:
                    self.log_test('update_task_in_new_structure', 'intern', 'PASS',
                                details="Task updated")
        except Exception as e:
            self.log_test('update_task_in_new_structure', 'intern', 'FAIL', str(e))
            traceback.print_exc()

    def cleanup(self):
        """Räumt alle Test-Daten auf mit verbessertem Error-Handling"""
        print(f"\n{Fore.BLUE}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}=== CLEANUP: Lösche Test-Daten ==={Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*60}{Style.RESET_ALL}\n")
        
        if self.teacher_session:
            self.set_session_id(self.teacher_session['session_id'])
        
        # Sessions werden über Auth verwaltet, kein explizites Cleanup nötig
        self.log_verbose("Sessions werden automatisch über Supabase Auth verwaltet", "INFO")
        
        # Cleanup Test-Daten in umgekehrter Reihenfolge
        for item_type, item_id in reversed(self.cleanup_items):
            try:
                self.log_verbose(f"Lösche {item_type}: {item_id}", "DEBUG")
                
                if item_type == 'auth_session':
                    # Lösche Session aus auth_sessions (mit Service-Role, da wir sie auch damit erstellt haben)
                    try:
                        from config import SUPABASE_SERVICE_ROLE_KEY
                        if SUPABASE_SERVICE_ROLE_KEY:
                            service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
                            result = service_client.table('auth_sessions').delete().eq('session_id', item_id).execute()
                            print(f"  {Fore.GREEN}✓ Auth-Session gelöscht: {item_id}{Style.RESET_ALL}")
                        else:
                            print(f"  {Fore.YELLOW}⚠ Kann Auth-Session nicht löschen (kein Service-Role-Key){Style.RESET_ALL}")
                    except Exception as e:
                        print(f"  {Fore.YELLOW}⚠ Auth-Session konnte nicht gelöscht werden: {e}{Style.RESET_ALL}")
                elif item_type == 'submission':
                    # Submissions werden automatisch mit Tasks gelöscht
                    continue
                elif item_type == 'task':
                    success, error = delete_task_in_new_structure(item_id)
                    if success:
                        print(f"  {Fore.GREEN}✓ Task gelöscht: {item_id}{Style.RESET_ALL}")
                    else:
                        print(f"  {Fore.YELLOW}⚠ Task konnte nicht gelöscht werden: {error}{Style.RESET_ALL}")
                elif item_type == 'section':
                    # Sections werden mit Unit gelöscht
                    continue  
                elif item_type == 'unit':
                    success, error = delete_learning_unit(item_id)
                    if success:
                        print(f"  {Fore.GREEN}✓ Lerneinheit gelöscht: {item_id}{Style.RESET_ALL}")
                    else:
                        print(f"  {Fore.YELLOW}⚠ Lerneinheit konnte nicht gelöscht werden: {error}{Style.RESET_ALL}")
                elif item_type == 'course':
                    success, error = delete_course(item_id)
                    if success:
                        print(f"  {Fore.GREEN}✓ Kurs gelöscht: {item_id}{Style.RESET_ALL}")
                    else:
                        print(f"  {Fore.YELLOW}⚠ Kurs konnte nicht gelöscht werden: {error}{Style.RESET_ALL}")
            except Exception as e:
                print(f"  {Fore.RED}✗ Fehler beim Löschen von {item_type} {item_id}: {e}{Style.RESET_ALL}")
                logger.exception(f"Cleanup failed for {item_type}")

    def print_summary(self):
        """Gibt eine detaillierte Zusammenfassung aus"""
        print(f"\n{Fore.BLUE}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{Style.BRIGHT}=== ZUSAMMENFASSUNG ==={Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*80}{Style.RESET_ALL}\n")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['result'] == 'PASS')
        failed = total - passed
        
        print(f"{Style.BRIGHT}Getestete Funktionen: {total}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ Erfolgreich: {passed}{Style.RESET_ALL}")
        print(f"{Fore.RED}❌ Fehlgeschlagen: {failed}{Style.RESET_ALL}")
        
        if passed > 0:
            success_rate = (passed / total * 100)
            color = Fore.GREEN if success_rate > 80 else Fore.YELLOW if success_rate > 60 else Fore.RED
            print(f"{color}📊 Erfolgsquote: {success_rate:.1f}%{Style.RESET_ALL}")
        
        # Gruppiere nach UI-Seiten
        by_page = {}
        for r in self.results:
            page = r['ui_page']
            if page not in by_page:
                by_page[page] = {'pass': 0, 'fail': 0, 'functions': []}
            if r['result'] == 'PASS':
                by_page[page]['pass'] += 1
            else:
                by_page[page]['fail'] += 1
            by_page[page]['functions'].append(r['function'])
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}Nach UI-Seiten:{Style.RESET_ALL}")
        for page, counts in sorted(by_page.items()):
            total_page = counts['pass'] + counts['fail']
            success_rate = (counts['pass'] / total_page * 100) if total_page > 0 else 0
            
            # Farbcodierung basierend auf Erfolgsquote
            if success_rate == 100:
                color = Fore.GREEN
                symbol = "✅"
            elif success_rate >= 80:
                color = Fore.YELLOW
                symbol = "⚠️"
            else:
                color = Fore.RED
                symbol = "❌"
            
            print(f"  {color}{symbol} {page}: {counts['pass']}/{total_page} ({success_rate:.0f}%){Style.RESET_ALL}")
        
        if failed > 0:
            print(f"\n{Fore.RED}{Style.BRIGHT}Fehlgeschlagene Tests:{Style.RESET_ALL}")
            for r in self.results:
                if r['result'] == 'FAIL':
                    print(f"  {Fore.RED}❌ {r['function']} ({r['ui_page']}){Style.RESET_ALL}")
                    if r['error']:
                        # Kürze lange Fehlermeldungen
                        error_msg = r['error']
                        if len(error_msg) > 100:
                            error_msg = error_msg[:97] + "..."
                        print(f"     {Fore.YELLOW}└─ {error_msg}{Style.RESET_ALL}")
        
        # Speichere detaillierte Ergebnisse
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'db_test_results_{timestamp}.json'
        with open(filename, 'w') as f:
            json.dump({
                'test_run': timestamp,
                'summary': {
                    'total': total,
                    'passed': passed,
                    'failed': failed,
                    'success_rate': (passed / total * 100) if total > 0 else 0,
                    'by_page': by_page
                },
                'configuration': {
                    'ai_timeout': AI_PROCESSING_TIMEOUT,
                    'verbose_logging': self.verbose,
                    'real_sessions': True
                },
                'results': self.results
            }, f, indent=2)
            print(f"\n{Fore.CYAN}📄 Detaillierte Ergebnisse gespeichert in: {filename}{Style.RESET_ALL}")
        
        # Zusammenfassung der kritischen Issues
        if failed > 0:
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}⚠️ Bekannte Issues (laut Dokumentation):{Style.RESET_ALL}")
            known_issues = {
                'get_submission_status_matrix': 'Gibt 0 sections zurück',
                'get_all_feedback': 'Schema-Inkompatibilitäten',
                'get_published_section_details_for_student': 'Tabellennamen-Probleme',
                'add_user_to_course': 'Validierungsprobleme'
            }
            
            for func, issue in known_issues.items():
                failed_test = next((r for r in self.results if r['function'] == func and r['result'] == 'FAIL'), None)
                if failed_test:
                    print(f"  {Fore.YELLOW}• {func}: {issue}{Style.RESET_ALL}")
    
    def run(self):
        """Führt alle Tests mit verbessertem Error Handling aus"""
        print(f"{Fore.MAGENTA}{Style.BRIGHT}{'='*80}")
        print(f"Comprehensive DB Functions Test Runner - Improved Version")
        print(f"Testing ALL functions with real sessions and extended timeouts")
        print(f"{'='*80}{Style.RESET_ALL}\n")
        
        print(f"{Fore.CYAN}Konfiguration:{Style.RESET_ALL}")
        print(f"  • AI Processing Timeout: {AI_PROCESSING_TIMEOUT}s")
        print(f"  • Verbose Logging: Aktiviert")
        print(f"  • Real Session Auth: Aktiviert")
        print(f"  • Test Accounts: {TEST_TEACHER_EMAIL}, {TEST_STUDENT_EMAIL}\n")
        
        if not self.setup_sessions():
            print(f"\n{Fore.RED}❌ Setup fehlgeschlagen. Tests abgebrochen.{Style.RESET_ALL}")
            return
        
        if not self.create_test_data():
            print(f"\n{Fore.RED}❌ Konnte Test-Daten nicht erstellen. Tests abgebrochen.{Style.RESET_ALL}")
            return
        
        # Führe alle Tests aus
        self.test_all_functions()
        
        # Zusammenfassung
        self.print_summary()
        
        # Cleanup
        self.cleanup()
        
        # Restore original context
        if self.original_context:
            st.context = self.original_context
            self.log_verbose("Original st.context wiederhergestellt", "DEBUG")
        
        print(f"\n{Fore.GREEN}{Style.BRIGHT}✅ Test-Durchlauf abgeschlossen!{Style.RESET_ALL}\n")


    def test_auth_and_core_functions(self):
        """Testet Auth und Core DB-Funktionen"""
        print(f"\n{Fore.BLUE}=== TESTE: Auth & Core Funktionen ==={Style.RESET_ALL}")
        
        self.set_session_id(self.teacher_session['session_id'])
        
        # Test: get_users_by_role
        try:
            teachers, error = get_users_by_role('teacher')
            if error:
                self.log_test('get_users_by_role', 'core/auth', 'FAIL', error)
            else:
                # Sollte mindestens unseren Test-Lehrer enthalten
                has_test_teacher = any(t['id'] == self.teacher_id for t in teachers) if teachers else False
                self.log_test('get_users_by_role', 'core/auth', 'PASS',
                            details=f"Found {len(teachers) if teachers else 0} teachers, test teacher included: {has_test_teacher}")
        except Exception as e:
            self.log_test('get_users_by_role', 'core/auth', 'FAIL', str(e))
            traceback.print_exc()

        # Test: is_teacher_authorized_for_course
        try:
            if 'course' in self.test_data:
                authorized, error = is_teacher_authorized_for_course(self.teacher_id, self.test_data['course']['id'])
                if error:
                    self.log_test('is_teacher_authorized_for_course', 'core/auth', 'FAIL', error)
                else:
                    self.log_test('is_teacher_authorized_for_course', 'core/auth', 'PASS',
                                details=f"Teacher authorized: {authorized}")
        except Exception as e:
            self.log_test('is_teacher_authorized_for_course', 'core/auth', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_session_id
        try:
            session_id = get_session_id()
            if not session_id:
                self.log_test('get_session_id', 'core/session', 'FAIL', "No session ID found")
            else:
                self.log_test('get_session_id', 'core/session', 'PASS',
                            details=f"Session ID: {session_id[:16]}...")
        except Exception as e:
            self.log_test('get_session_id', 'core/session', 'FAIL', str(e))
            traceback.print_exc()
    
    def test_enrollment_functions(self):
        """Testet Enrollment-spezifische Funktionen"""
        print(f"\n{Fore.BLUE}=== TESTE: Enrollment Funktionen ==={Style.RESET_ALL}")
        
        # Test: get_student_courses (als Schüler)
        self.set_session_id(self.student_session['session_id'])
        try:
            courses, error = get_student_courses(self.student_id)
            if error:
                self.log_test('get_student_courses', 'enrollment', 'FAIL', error)
            else:
                has_test_course = any(c['id'] == self.test_data.get('course', {}).get('id') for c in courses) if courses else False
                self.log_test('get_student_courses', 'enrollment', 'PASS',
                            details=f"Found {len(courses) if courses else 0} courses, test course included: {has_test_course}")
        except Exception as e:
            self.log_test('get_student_courses', 'enrollment', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_courses_assigned_to_unit (als Lehrer)
        self.set_session_id(self.teacher_session['session_id'])
        try:
            if 'unit' in self.test_data:
                courses, error = get_courses_assigned_to_unit(self.test_data['unit']['id'])
                if error:
                    self.log_test('get_courses_assigned_to_unit', 'enrollment', 'FAIL', error)
                else:
                    has_test_course = any(c['id'] == self.test_data.get('course', {}).get('id') for c in courses) if courses else False
                    self.log_test('get_courses_assigned_to_unit', 'enrollment', 'PASS',
                                details=f"Found {len(courses) if courses else 0} courses using this unit")
        except Exception as e:
            self.log_test('get_courses_assigned_to_unit', 'enrollment', 'FAIL', str(e))
            traceback.print_exc()
    
    def test_progress_functions(self):
        """Testet Progress und Tracking Funktionen"""
        print(f"\n{Fore.BLUE}=== TESTE: Progress & Tracking Funktionen ==={Style.RESET_ALL}")
        
        self.set_session_id(self.teacher_session['session_id'])
        
        # Test: get_submissions_for_course_and_unit
        try:
            if all(key in self.test_data for key in ['course', 'unit']):
                submissions, error = get_submissions_for_course_and_unit(
                    self.test_data['course']['id'],
                    self.test_data['unit']['id']
                )
                if error:
                    self.log_test('get_submissions_for_course_and_unit', 'progress', 'FAIL', error)
                else:
                    self.log_test('get_submissions_for_course_and_unit', 'progress', 'PASS',
                                details=f"Found {len(submissions) if submissions else 0} submissions")
        except Exception as e:
            self.log_test('get_submissions_for_course_and_unit', 'progress', 'FAIL', str(e))
            traceback.print_exc()

        # Test: calculate_learning_streak
        try:
            current_streak, error = calculate_learning_streak(self.student_id)
            if error:
                self.log_test('calculate_learning_streak', 'progress', 'FAIL', error)
            else:
                self.log_test('calculate_learning_streak', 'progress', 'PASS',
                            details=f"Current streak: {current_streak} days")
        except Exception as e:
            self.log_test('calculate_learning_streak', 'progress', 'FAIL', str(e))
            traceback.print_exc()

        # Test: update_submission_ai_results
        try:
            if 'submission' in self.test_data:
                success, error = update_submission_ai_results(
                    self.test_data['submission']['id'],
                    '{"criteria": "Test criteria analysis"}',  # criteria_analysis
                    "Das ist ein automatisch generiertes Test-Feedback.",  # feedback
                    "korrekt"  # rating_suggestion
                )
                if not success:
                    self.log_test('update_submission_ai_results', 'progress', 'FAIL', error)
                else:
                    self.log_test('update_submission_ai_results', 'progress', 'PASS',
                                details="AI results updated")
        except Exception as e:
            self.log_test('update_submission_ai_results', 'progress', 'FAIL', str(e))
            traceback.print_exc()
    
    def test_mastery_functions(self):
        """Testet alle Mastery Learning Funktionen"""
        print(f"\n{Fore.BLUE}=== TESTE: Mastery Learning Funktionen ==={Style.RESET_ALL}")
        
        # Als Schüler einloggen für Mastery-Tests
        self.set_session_id(self.student_session['session_id'])
        
        # Test: get_mastery_tasks_for_course
        try:
            if 'course' in self.test_data:
                tasks, error = get_mastery_tasks_for_course(
                    self.test_data['course']['id']
                )
                if error:
                    self.log_test('get_mastery_tasks_for_course', 'mastery', 'FAIL', error)
                else:
                    self.log_test('get_mastery_tasks_for_course', 'mastery', 'PASS',
                                details=f"Found {len(tasks) if tasks else 0} mastery tasks")
        except Exception as e:
            self.log_test('get_mastery_tasks_for_course', 'mastery', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_next_due_mastery_task
        try:
            if 'course' in self.test_data:
                task, error = get_next_due_mastery_task(self.student_id, self.test_data['course']['id'])
                if error:
                    self.log_test('get_next_due_mastery_task', 'mastery', 'FAIL', error)
                else:
                    task_title = task.get('title') if task else 'None'
                    self.log_test('get_next_due_mastery_task', 'mastery', 'PASS',
                                details=f"Next due task: {task_title}")
        except Exception as e:
            self.log_test('get_next_due_mastery_task', 'mastery', 'FAIL', str(e))
            traceback.print_exc()

        # Test: submit_mastery_answer
        try:
            if 'mastery_task' in self.test_data:
                result, error = submit_mastery_answer(
                    self.student_id,
                    self.test_data['mastery_task']['id'],
                    "Dies ist eine Test-Antwort für die Mastery-Aufgabe."
                )
                if error:
                    self.log_test('submit_mastery_answer', 'mastery', 'FAIL', error)
                else:
                    self.test_data['mastery_result'] = result
                    self.log_test('submit_mastery_answer', 'mastery', 'PASS',
                                details=f"Submission created, is_correct: {result.get('is_correct')}")
        except Exception as e:
            self.log_test('submit_mastery_answer', 'mastery', 'FAIL', str(e))
            traceback.print_exc()

        # Test: save_mastery_submission
        try:
            if 'mastery_task' in self.test_data:
                assessment = {
                    "feedback": "Automatisches Test-Feedback",
                    "is_correct": True,
                    "confidence_score": 0.9
                }
                result, error = save_mastery_submission(
                    self.student_id,
                    self.test_data['mastery_task']['id'],
                    "Weitere Test-Antwort",
                    assessment
                )
                if error:
                    self.log_test('save_mastery_submission', 'mastery', 'FAIL', error)
                else:
                    self.log_test('save_mastery_submission', 'mastery', 'PASS',
                                details=f"Saved with confidence: 0.9")
        except Exception as e:
            self.log_test('save_mastery_submission', 'mastery', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_mastery_stats_for_student
        try:
            if 'course' in self.test_data:
                stats, error = get_mastery_stats_for_student(self.student_id, self.test_data['course']['id'])
                if error:
                    self.log_test('get_mastery_stats_for_student', 'mastery', 'FAIL', error)
                else:
                    self.log_test('get_mastery_stats_for_student', 'mastery', 'PASS',
                                details=f"Total tasks: {stats.get('total_mastery_tasks', 0)}, Mastered: {stats.get('mastered_count', 0)}")
        except Exception as e:
            self.log_test('get_mastery_stats_for_student', 'mastery', 'FAIL', str(e))
            traceback.print_exc()

        # Test: get_mastery_overview_for_teacher (als Lehrer)
        self.set_session_id(self.teacher_session['session_id'])
        try:
            if 'course' in self.test_data:
                overview, error = get_mastery_overview_for_teacher(self.test_data['course']['id'])
                if error:
                    self.log_test('get_mastery_overview_for_teacher', 'mastery', 'FAIL', error)
                else:
                    self.log_test('get_mastery_overview_for_teacher', 'mastery', 'PASS',
                                details=f"Overview for {len(overview) if overview else 0} students")
        except Exception as e:
            self.log_test('get_mastery_overview_for_teacher', 'mastery', 'FAIL', str(e))
            traceback.print_exc()


if __name__ == "__main__":
    tester = ComprehensiveDBTester()
    tester.run()