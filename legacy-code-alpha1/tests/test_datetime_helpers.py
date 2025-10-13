# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""Tests for datetime helper functions."""

import pytest
from datetime import datetime, timezone
from app.utils.datetime_helpers import parse_iso_datetime, format_date_german, format_datetime_german


class TestParseIsoDatetime:
    """Test cases for ISO datetime parsing."""
    
    def test_parse_none_input(self):
        """Test parsing None input returns None."""
        assert parse_iso_datetime(None) is None
        assert parse_iso_datetime("") is None
        
    def test_parse_z_format(self):
        """Test parsing Z timezone format."""
        result = parse_iso_datetime("2025-09-02T06:51:51Z")
        expected = datetime(2025, 9, 2, 6, 51, 51, tzinfo=timezone.utc)
        assert result == expected
        
    def test_parse_with_full_microseconds(self):
        """Test parsing with 6-digit microseconds."""
        result = parse_iso_datetime("2025-09-02T06:51:51.123456+00:00")
        expected = datetime(2025, 9, 2, 6, 51, 51, 123456, tzinfo=timezone.utc)
        assert result == expected
        
    def test_parse_with_variable_microseconds(self):
        """Test parsing with variable microsecond digits (the problematic case)."""
        # This was causing the ValueError
        result = parse_iso_datetime("2025-09-02T06:51:51.85193+00:00")
        expected = datetime(2025, 9, 2, 6, 51, 51, 851930, tzinfo=timezone.utc)
        assert result == expected
        
    def test_parse_with_short_microseconds(self):
        """Test parsing with short microseconds gets padded."""
        result = parse_iso_datetime("2025-09-02T06:51:51.1+00:00")
        expected = datetime(2025, 9, 2, 6, 51, 51, 100000, tzinfo=timezone.utc)
        assert result == expected
        
    def test_parse_without_microseconds(self):
        """Test parsing without microseconds."""
        result = parse_iso_datetime("2025-09-02T06:51:51+00:00")
        expected = datetime(2025, 9, 2, 6, 51, 51, tzinfo=timezone.utc)
        assert result == expected
        
    def test_parse_invalid_format_raises_error(self):
        """Test that completely invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_iso_datetime("invalid-datetime-string")


class TestFormatGerman:
    """Test cases for German datetime formatting."""
    
    def test_format_date_german(self):
        """Test German date formatting."""
        dt = datetime(2025, 9, 2, 14, 30, 45)
        result = format_date_german(dt)
        assert result == "02.09.2025"
        
    def test_format_datetime_german(self):
        """Test German datetime formatting."""
        dt = datetime(2025, 9, 2, 14, 30, 45)
        result = format_datetime_german(dt)
        assert result == "02.09.2025, 14:30 Uhr"
        
    def test_format_single_digit_values(self):
        """Test formatting with single-digit day/month."""
        dt = datetime(2025, 1, 5, 8, 5, 0)
        date_result = format_date_german(dt)
        datetime_result = format_datetime_german(dt)
        
        assert date_result == "05.01.2025"
        assert datetime_result == "05.01.2025, 08:05 Uhr"


class TestEdgeCases:
    """Test edge cases and integration scenarios."""
    
    def test_round_trip_parsing_and_formatting(self):
        """Test parsing then formatting preserves expected output."""
        iso_string = "2025-09-02T06:51:51.85193+00:00"
        parsed_dt = parse_iso_datetime(iso_string)
        formatted = format_datetime_german(parsed_dt)
        
        # Should format to German locale
        assert formatted == "02.09.2025, 06:51 Uhr"
        
    def test_database_common_formats(self):
        """Test common Supabase datetime formats."""
        test_cases = [
            "2025-09-02T06:51:51.85193+00:00",  # Variable microseconds
            "2025-09-02T06:51:51.000000+00:00", # Full microseconds
            "2025-09-02T06:51:51Z",              # Z format
            "2025-09-02T06:51:51+00:00",        # No microseconds
        ]
        
        for iso_string in test_cases:
            result = parse_iso_datetime(iso_string)
            assert result is not None
            assert result.year == 2025
            assert result.month == 9
            assert result.day == 2