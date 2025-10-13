"""
Timeout Wrapper für KI-Aufrufe

Stellt sicher, dass KI-Aufrufe nicht endlos blockieren.
Verwendet Thread-basiertes Timeout statt Signal-basiertes,
da Signals in Multi-Thread-Umgebungen problematisch sind.
"""

import os
import time
import threading
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class TimeoutException(Exception):
    """Exception für Timeout-Fälle"""
    pass

def with_timeout(seconds: int = None):
    """
    Thread-basierter Timeout Decorator für Funktionen.
    
    Args:
        seconds: Timeout in Sekunden (default: AI_TIMEOUT env var oder 300)
    """
    if seconds is None:
        seconds = int(os.getenv('AI_TIMEOUT', '30'))  # Default auf 30s reduziert
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            
            start_time = time.time()
            thread.start()
            thread.join(timeout=seconds)
            
            if thread.is_alive():
                # Thread läuft noch -> Timeout
                logger.error(f"{func.__name__} timed out after {seconds}s")
                # Hinweis: Thread kann nicht sauber beendet werden in Python
                # Er läuft weiter im Hintergrund bis er fertig ist
                raise TimeoutException(f"Operation timed out after {seconds}s")
            
            # Thread ist fertig
            elapsed = time.time() - start_time
            
            if elapsed > seconds * 0.8:  # Warnung bei 80% der Zeit
                logger.warning(f"{func.__name__} took {elapsed:.2f}s (close to timeout of {seconds}s)")
            
            # Prüfe auf Exception im Thread
            if exception[0] is not None:
                raise exception[0]
                
            return result[0]
                
        return wrapper
    return decorator

def call_with_timeout(func: Callable[..., T], args: tuple = (), kwargs: dict = None, timeout: int = 300) -> T:
    """
    Ruft eine Funktion mit Timeout auf.
    
    Args:
        func: Die aufzurufende Funktion
        args: Positionsargumente
        kwargs: Keyword-Argumente
        timeout: Timeout in Sekunden
        
    Returns:
        Das Ergebnis der Funktion
        
    Raises:
        TimeoutException: Wenn die Funktion das Timeout überschreitet
    """
    if kwargs is None:
        kwargs = {}
        
    # Erstelle temporäre Wrapper-Funktion
    @with_timeout(timeout)
    def wrapped():
        return func(*args, **kwargs)
        
    return wrapped()