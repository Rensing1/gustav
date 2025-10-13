# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT

"""Datetime utilities for consistent ISO string parsing across the codebase."""

from datetime import datetime
from typing import Optional


def parse_iso_datetime(iso_string: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string with robust microseconds handling.
    
    Handles common Supabase datetime formats:
    - '2025-09-02T06:51:51.85193+00:00' (variable microseconds)
    - '2025-09-02T06:51:51Z' (no microseconds)
    - '2025-09-02T06:51:51.000000+00:00' (full microseconds)
    
    Args:
        iso_string: ISO format datetime string or None
        
    Returns:
        Parsed datetime object or None if input is None/invalid
        
    Raises:
        ValueError: If string format is completely invalid
    """
    if not iso_string:
        return None
        
    # Replace Z with +00:00 for Python compatibility
    datetime_str = iso_string.replace('Z', '+00:00')
    
    # Handle microseconds normalization
    if '.' in datetime_str and '+' in datetime_str:
        parts = datetime_str.split('.')
        if len(parts) == 2:
            # Extract microseconds and timezone parts
            microsec_part = parts[1].split('+')[0][:6].ljust(6, '0')  # Normalize to 6 digits
            timezone_part = '+' + parts[1].split('+')[1]
            datetime_str = f"{parts[0]}.{microsec_part}{timezone_part}"
    
    return datetime.fromisoformat(datetime_str)


def format_datetime_german(dt: datetime) -> str:
    """Format datetime for German locale display.
    
    Args:
        dt: Datetime object to format
        
    Returns:
        German formatted string like "02.09.2025, 08:51 Uhr"
    """
    return dt.strftime('%d.%m.%Y, %H:%M Uhr')


def format_date_german(dt: datetime) -> str:
    """Format date for German locale display.
    
    Args:
        dt: Datetime object to format
        
    Returns:
        German formatted date string like "02.09.2025"
    """
    return dt.strftime('%d.%m.%Y')