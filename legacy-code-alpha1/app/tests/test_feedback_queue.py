#!/usr/bin/env python3
"""
Tests für das asynchrone Feedback-Queue-System
"""

import os
import sys
import time
import pytest
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.timeout_wrapper import with_timeout, TimeoutException


class TestTimeoutWrapper:
    """Tests für den Timeout-Wrapper"""
    
    def test_successful_execution(self):
        """Test: Funktion läuft erfolgreich innerhalb des Timeouts"""
        @with_timeout(2)
        def quick_function():
            time.sleep(0.5)
            return "success"
        
        result = quick_function()
        assert result == "success"
    
    def test_timeout_exception(self):
        """Test: Funktion überschreitet Timeout"""
        @with_timeout(1)
        def slow_function():
            time.sleep(2)
            return "should not return"
        
        with pytest.raises(TimeoutException):
            slow_function()
    
    def test_exception_propagation(self):
        """Test: Exceptions werden korrekt weitergegeben"""
        @with_timeout(2)
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError) as exc_info:
            failing_function()
        assert str(exc_info.value) == "Test error"


class TestQueueLogic:
    """Tests für die Queue-Logik (Mock-Tests ohne echte DB)"""
    
    def test_retry_backoff_calculation(self):
        """Test: Exponential backoff Berechnung"""
        # retry_count * 5 Minuten
        assert self._calculate_backoff(0) == 0
        assert self._calculate_backoff(1) == 5 * 60  # 5 Minuten
        assert self._calculate_backoff(2) == 10 * 60  # 10 Minuten
        assert self._calculate_backoff(3) == 15 * 60  # 15 Minuten
    
    def _calculate_backoff(self, retry_count: int) -> int:
        """Helper: Berechnet Backoff in Sekunden"""
        return retry_count * 5 * 60
    
    def test_queue_position_estimation(self):
        """Test: Schätzung der Queue-Position"""
        # Annahme: 30 Sekunden pro Aufgabe
        queue_position = 5
        estimated_seconds = queue_position * 30
        assert estimated_seconds == 150  # 2.5 Minuten
        
        # Formatierung
        minutes = estimated_seconds // 60
        seconds = estimated_seconds % 60
        assert minutes == 2
        assert seconds == 30


class TestWorkerHealthCheck:
    """Tests für Worker Health-Check-Logik"""
    
    def test_stuck_job_detection(self):
        """Test: Erkennung von stuck jobs"""
        # Job gilt als stuck wenn processing_started_at > 5 Minuten alt
        now = datetime.now()
        
        # Nicht stuck (3 Minuten)
        processing_started = now - timedelta(minutes=3)
        assert not self._is_stuck(processing_started, now)
        
        # Stuck (6 Minuten)
        processing_started = now - timedelta(minutes=6)
        assert self._is_stuck(processing_started, now)
    
    def _is_stuck(self, processing_started: datetime, now: datetime) -> bool:
        """Helper: Prüft ob Job stuck ist"""
        return (now - processing_started).seconds > 5 * 60


class TestFeedbackStatusFlow:
    """Tests für den Status-Flow einer Submission"""
    
    def test_status_transitions(self):
        """Test: Erlaubte Status-Übergänge"""
        allowed_transitions = {
            'pending': ['processing'],
            'processing': ['completed', 'retry', 'failed'],
            'retry': ['processing'],
            'completed': [],  # Endstatus
            'failed': []      # Endstatus
        }
        
        # Test erlaubte Übergänge
        assert self._is_valid_transition('pending', 'processing', allowed_transitions)
        assert self._is_valid_transition('processing', 'completed', allowed_transitions)
        assert self._is_valid_transition('processing', 'retry', allowed_transitions)
        
        # Test unerlaubte Übergänge
        assert not self._is_valid_transition('pending', 'completed', allowed_transitions)
        assert not self._is_valid_transition('completed', 'processing', allowed_transitions)
    
    def _is_valid_transition(self, from_status: str, to_status: str, transitions: dict) -> bool:
        """Helper: Prüft ob Status-Übergang erlaubt ist"""
        return to_status in transitions.get(from_status, [])


if __name__ == "__main__":
    # Führe Tests aus
    pytest.main([__file__, "-v"])