"""
Cache-Manager für GUSTAV Performance-Optimierung
Implementiert smart caching für häufig abgerufene, aber selten geänderte Daten + User Selection Persistence.

Sicherheitsregeln:
- ✅ Erlaubt: Kursstrukturen, Einheitenlisten, öffentliche Metadaten
- ❌ Verboten: Personenbezogene Daten, Einreichungen, private Informationen  
- ⚠️ User-spezifisch: Alles in st.session_state = automatisch user-isoliert

Cache-TTL-Strategie basierend auf realen Nutzungsmustern:
- Kursliste: 90 Min (ändert sich nie während Unterrichtsstunde)
- Lerneinheiten: 10 Min (selten spontane Änderungen)
- User-Auswahl: 90 Min (persistente Navigation für ganze Unterrichtsstunde)
- Freigabe-Status: 0 Min (kein Cache - ändert sich laufend im Unterricht)
"""

import streamlit as st
import time
from typing import Optional, List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Zentrale Cache-Verwaltung für Navigation Performance + User Selection Persistence."""
    
    @staticmethod
    def _get_user_id() -> Optional[str]:
        """Holt aktuelle User-ID aus Session."""
        if 'user' in st.session_state and st.session_state.user:
            user = st.session_state.user
            # Handle both SecureUserDict and legacy formats
            if hasattr(user, 'id'):
                return user.id
            elif isinstance(user, dict):
                return user.get('id')
        return None
    
    @staticmethod
    def _is_cache_valid(cache_data: Tuple, ttl_minutes: int) -> bool:
        """Prüft ob Cache-Eintrag noch gültig ist."""
        if not cache_data or len(cache_data) != 2:
            return False
        data, timestamp = cache_data
        return (time.time() - timestamp) < (ttl_minutes * 60)
    
    # === KURSE CACHING (90 Min TTL) ===
    
    @classmethod
    def get_user_courses(cls, force_refresh: bool = False) -> List[Dict]:
        """Holt Kursliste für aktuellen User mit 90 Min Cache."""
        logger.info("=== CACHE MANAGER: GET USER COURSES START ===")
        
        user_id = cls._get_user_id()
        if not user_id:
            logger.warning("No user_id found, returning empty course list")
            logger.info("=== CACHE MANAGER: GET USER COURSES END (NO USER) ===")
            return []
        
        logger.info(f"User ID: {user_id}")
        cache_key = f'courses_cache_{user_id}'
        
        # Prüfe Cache (außer bei force_refresh)
        if not force_refresh and cache_key in st.session_state:
            cache_data = st.session_state[cache_key]
            if cls._is_cache_valid(cache_data, ttl_minutes=90):
                logger.info(f"Returning cached courses (count: {len(cache_data[0])})")
                logger.info("=== CACHE MANAGER: GET USER COURSES END (CACHED) ===")
                return cache_data[0]  # Return cached data
        
        logger.info("Cache miss or force refresh, fetching fresh data")
        
        # Fresh fetch via DataFetcher
        try:
            # Import here to avoid circular imports
            from .data_fetcher import data_fetcher
            
            logger.debug("Calling data_fetcher.get_courses()")
            courses = data_fetcher.get_courses()
            
            logger.info(f"Fetched {len(courses)} courses from DataFetcher")
            
            # Cache speichern
            st.session_state[cache_key] = (courses, time.time())
            logger.info(f"Cached {len(courses)} courses for user {user_id}")
            logger.info("=== CACHE MANAGER: GET USER COURSES END (FRESH) ===")
            return courses
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Kurse über DataFetcher: {e}", exc_info=True)
            logger.info("=== CACHE MANAGER: GET USER COURSES END (ERROR) ===")
            return []
    
    # === LERNEINHEITEN CACHING (10 Min TTL) ===
    
    @classmethod
    def get_course_units(cls, course_id: str, force_refresh: bool = False) -> List[Dict]:
        """Holt Lerneinheitenliste für Kurs mit 10 Min Cache."""
        user_id = cls._get_user_id()
        if not user_id or not course_id:
            return []
        
        cache_key = f'units_cache_{user_id}_{course_id}'
        
        # Prüfe Cache
        if not force_refresh and cache_key in st.session_state:
            cache_data = st.session_state[cache_key]
            if cls._is_cache_valid(cache_data, ttl_minutes=10):
                return cache_data[0]
        
        # Fresh fetch via DataFetcher
        try:
            # Import here to avoid circular imports
            from .data_fetcher import data_fetcher
            
            # DataFetcher is now synchronous
            units = data_fetcher.get_course_units(course_id)
            
            # Cache speichern
            st.session_state[cache_key] = (units, time.time())
            return units
        except Exception as e:
            print(f"Fehler beim Abrufen der Lerneinheiten über DataFetcher: {e}")
            return []
    
    # === USER SELECTION PERSISTENCE (90 Min TTL) ===
    
    @staticmethod
    def save_user_selection(course_id: str, unit_id: str = None):
        """Speichert User-Auswahl für 90 Minuten (ganze Unterrichtsstunde)."""
        selection_data = {
            'course_id': course_id,
            'unit_id': unit_id,
            'timestamp': time.time()
        }
        st.session_state['selected_course_cache'] = selection_data
    
    @classmethod
    def get_user_selection(cls) -> Tuple[Optional[str], Optional[str]]:
        """Holt letzte User-Auswahl wenn noch gültig (90 Min)."""
        if 'selected_course_cache' not in st.session_state:
            return None, None
        
        cache = st.session_state['selected_course_cache']
        if cls._is_cache_valid((cache, cache.get('timestamp', 0)), ttl_minutes=90):
            return cache.get('course_id'), cache.get('unit_id')
        
        # Cache abgelaufen
        return None, None
    
    @staticmethod
    def clear_user_selection():
        """Löscht User-Auswahl Cache (für manuellen Reset)."""
        if 'selected_course_cache' in st.session_state:
            del st.session_state['selected_course_cache']
    
    # === CACHE MANAGEMENT ===
    
    @classmethod
    def invalidate_user_courses(cls, user_id: str = None):
        """Invalidiert Kurse-Cache (bei Course-Erstellung)."""
        if not user_id:
            user_id = cls._get_user_id()
        if user_id:
            cache_key = f'courses_cache_{user_id}'
            if cache_key in st.session_state:
                del st.session_state[cache_key]
    
    @classmethod
    def invalidate_course_units(cls, course_id: str, user_id: str = None):
        """Invalidiert Einheiten-Cache für spezifischen Kurs."""
        if not user_id:
            user_id = cls._get_user_id()
        if user_id and course_id:
            cache_key = f'units_cache_{user_id}_{course_id}'
            if cache_key in st.session_state:
                del st.session_state[cache_key]
    
    @staticmethod
    def clear_all_caches():
        """Löscht alle Navigation-Caches (für 🔄 Jetzt aktualisieren Button)."""
        keys_to_remove = []
        for key in st.session_state.keys():
            if key.startswith(('courses_cache_', 'units_cache_', 'selected_course_cache')):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del st.session_state[key]
    
    # === DEBUG & MONITORING ===
    
    @classmethod 
    def get_cache_stats(cls) -> Dict[str, any]:
        """Debug-Informationen über Cache-Performance."""
        user_id = cls._get_user_id()
        stats = {
            "user_id": user_id,
            "cache_enabled": True,
            "ttl_courses": "90 min",
            "ttl_units": "10 min", 
            "ttl_selection": "90 min",
            "active_caches": []
        }
        
        # Zähle aktive Cache-Einträge
        for key in st.session_state.keys():
            if key.startswith(('courses_cache_', 'units_cache_')):
                cache_data = st.session_state[key]
                if len(cache_data) == 2:
                    data, timestamp = cache_data
                    age_minutes = (time.time() - timestamp) / 60
                    stats["active_caches"].append({
                        "key": key,
                        "age_minutes": round(age_minutes, 1),
                        "size": len(data) if isinstance(data, list) else 1
                    })
        
        # User Selection Status
        cached_course, cached_unit = cls.get_user_selection()
        stats["user_selection"] = {
            "course_id": cached_course,
            "unit_id": cached_unit,
            "active": bool(cached_course)
        }
        
        return stats
    
    @staticmethod
    def render_debug_panel():
        """Zeigt Cache-Debug-Informationen in Sidebar-Expander."""
        with st.sidebar.expander("🐛 Cache Debug", expanded=False):
            stats = CacheManager.get_cache_stats()
            st.json(stats)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Clear Selection", use_container_width=True):
                    CacheManager.clear_user_selection()
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear All", use_container_width=True):
                    CacheManager.clear_all_caches()
                    st.rerun()