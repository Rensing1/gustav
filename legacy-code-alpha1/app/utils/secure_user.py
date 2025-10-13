# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT
"""
SecureUserDict - Sicherer Wrapper für User-Daten
Bietet Attribut-Zugriff auf Dictionary-Daten mit Validierung und Sicherheit
"""

from typing import Optional, Dict, Any, List, Union
import logging

logger = logging.getLogger(__name__)


class SecureUserDict:
    """Sicherer Wrapper mit Validierung und Zugriffskontrolle"""
    
    # Whitelist erlaubter Attribute
    ALLOWED_ATTRS = {'id', 'email', 'role', 'name', 'metadata', 'created_at'}
    
    # Erwartete Typen für Validation
    ATTR_TYPES = {
        'id': str,
        'email': str,
        'role': str,
        'name': (str, type(None)),
        'metadata': (dict, type(None)),
        'created_at': (str, type(None))
    }
    
    def __init__(self, data: Dict[str, Any]):
        # Validierung vor Speicherung
        if not isinstance(data, dict):
            raise TypeError("User data must be a dictionary")
        
        # Deep copy um Mutation zu verhindern
        self._data = self._sanitize_data(data.copy())
    
    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize und validiere User-Daten"""
        sanitized = {}
        
        for key, value in data.items():
            if key not in self.ALLOWED_ATTRS:
                logger.warning(f"Ignoring unknown attribute: {key}")
                continue  # Ignoriere unbekannte Attribute
            
            # Type checking
            expected_type = self.ATTR_TYPES.get(key)
            if expected_type and not isinstance(value, expected_type):
                if key in ['id', 'email', 'role']:  # Pflichtfelder
                    raise ValueError(f"Invalid type for {key}: expected {expected_type}, got {type(value)}")
                else:
                    value = None  # Optional fields -> None
            
            # XSS Prevention für Strings
            if isinstance(value, str):
                # Basic HTML escape (in Production: use markupsafe)
                value = value.replace('<', '&lt;').replace('>', '&gt;')
            
            sanitized[key] = value
        
        # Validiere Pflichtfelder
        for required in ['id', 'email', 'role']:
            if required not in sanitized:
                raise ValueError(f"Missing required field: {required}")
        
        return sanitized
    
    def __getattr__(self, name: str) -> Any:
        """Sicherer Attribut-Zugriff mit Whitelist"""
        # Verhindere Zugriff auf private/magic attributes
        if name.startswith('_'):
            raise AttributeError(f"Access to private attribute '{name}' is not allowed")
        
        # Nur erlaubte Attribute
        if name not in self.ALLOWED_ATTRS:
            raise AttributeError(f"User has no attribute '{name}'")
        
        return self._data.get(name)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get Methode für Kompatibilität"""
        if key not in self.ALLOWED_ATTRS:
            return default
        return self._data.get(key, default)
    
    def __bool__(self) -> bool:
        """Boolean evaluation - True wenn gültiger User"""
        return bool(self._data.get('id'))
    
    def __str__(self) -> str:
        """String representation ohne sensitive Daten"""
        return f"User(id={self.id}, role={self.role})"
    
    def __repr__(self) -> str:
        """Debug representation"""
        return f"SecureUserDict(id={self.id}, email={self.email}, role={self.role})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Sicherer Export als Dictionary"""
        return self._data.copy()
    
    def __getstate__(self):
        """Für Pickle/Session Serialization"""
        return self._data
    
    def __setstate__(self, state):
        """Für Pickle/Session Deserialization mit Revalidierung"""
        self._data = self._sanitize_data(state)
    
    # Verhindere Attribute-Schreibzugriff
    def __setattr__(self, name: str, value: Any):
        """Verhindere Mutation nach Erstellung"""
        if name == '_data' and not hasattr(self, '_data'):
            # Erlaube initiale Zuweisung
            super().__setattr__(name, value)
        else:
            raise AttributeError(f"SecureUserDict is immutable")