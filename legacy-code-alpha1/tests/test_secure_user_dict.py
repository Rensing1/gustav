"""
Unit Tests für SecureUserDict
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from utils.secure_user import SecureUserDict


class TestSecureUserDict:
    def test_valid_user_creation(self):
        """Test normale User-Erstellung"""
        user_data = {
            "id": "123",
            "email": "test@example.com",
            "role": "student"
        }
        user = SecureUserDict(user_data)
        assert user.id == "123"
        assert user.email == "test@example.com"
        assert user.role == "student"
    
    def test_xss_prevention(self):
        """Test XSS-Schutz"""
        user_data = {
            "id": "<script>alert('xss')</script>",
            "email": "test@example.com",
            "role": "student"
        }
        user = SecureUserDict(user_data)
        assert user.id == "&lt;script&gt;alert('xss')&lt;/script&gt;"
    
    def test_private_attribute_access(self):
        """Test Schutz vor private attribute access"""
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        with pytest.raises(AttributeError):
            _ = user._data
        with pytest.raises(AttributeError):
            _ = user.__class__
    
    def test_unknown_attribute_access(self):
        """Test Schutz vor unbekannten Attributen"""
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        with pytest.raises(AttributeError):
            _ = user.password
    
    def test_immutability(self):
        """Test dass User-Objekt unveränderlich ist"""
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        with pytest.raises(AttributeError):
            user.email = "new@example.com"
    
    def test_type_validation(self):
        """Test Typ-Validierung"""
        # Invalid type for required field
        with pytest.raises(ValueError):
            SecureUserDict({"id": ["list"], "email": "test@example.com", "role": "student"})
        
        # Missing required field
        with pytest.raises(ValueError):
            SecureUserDict({"id": "123", "email": "test@example.com"})
    
    def test_dict_compatibility(self):
        """Test dict-like Interface"""
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        assert user.get('email') == "test@example.com"
        assert user.get('nonexistent', 'default') == 'default'
    
    def test_optional_fields(self):
        """Test optional fields handling"""
        user_data = {
            "id": "123",
            "email": "test@example.com",
            "role": "student",
            "name": "Test User",
            "metadata": {"key": "value"},
            "created_at": "2025-01-01T00:00:00"
        }
        user = SecureUserDict(user_data)
        assert user.name == "Test User"
        assert user.metadata == {"key": "value"}
        assert user.created_at == "2025-01-01T00:00:00"
    
    def test_none_optional_fields(self):
        """Test None handling for optional fields"""
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        assert user.name is None
        assert user.metadata is None
        assert user.created_at is None
    
    def test_bool_evaluation(self):
        """Test boolean evaluation"""
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        assert bool(user) is True
    
    def test_string_representation(self):
        """Test string representations"""
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        assert str(user) == "User(id=123, role=student)"
        assert repr(user) == "SecureUserDict(id=123, email=test@example.com, role=student)"
    
    def test_to_dict(self):
        """Test export as dictionary"""
        user_data = {"id": "123", "email": "test@example.com", "role": "student"}
        user = SecureUserDict(user_data)
        exported = user.to_dict()
        assert exported == user_data
        # Ensure it's a copy
        exported['id'] = "456"
        assert user.id == "123"
    
    def test_serialization(self):
        """Test pickle serialization/deserialization"""
        import pickle
        user = SecureUserDict({"id": "123", "email": "test@example.com", "role": "student"})
        serialized = pickle.dumps(user)
        deserialized = pickle.loads(serialized)
        assert deserialized.id == "123"
        assert deserialized.email == "test@example.com"
        assert deserialized.role == "student"
    
    def test_invalid_data_type(self):
        """Test invalid data type handling"""
        with pytest.raises(TypeError):
            SecureUserDict("not a dict")
    
    def test_unknown_attributes_ignored(self):
        """Test that unknown attributes are ignored"""
        user_data = {
            "id": "123",
            "email": "test@example.com",
            "role": "student",
            "unknown_field": "should be ignored"
        }
        user = SecureUserDict(user_data)
        # Should not raise error
        with pytest.raises(AttributeError):
            _ = user.unknown_field


if __name__ == "__main__":
    pytest.main([__file__, "-v"])