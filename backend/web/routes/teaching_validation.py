"""Pure validation helpers for Teaching route adapters.

These helpers intentionally avoid FastAPI response objects so they can be reused
from route adapters, BFF code, and tests without pulling in more Teaching
hotspot implementation detail.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


def canonical_uuid(value: str) -> str:
    """Return a canonical lowercase UUID string."""

    return str(UUID(str(value)))


def safe_int(value: Any) -> Optional[int]:
    """Parse an optional integer defensively."""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clamp_limit_offset(
    *,
    limit: int | None,
    offset: int | None,
    default_limit: int,
    max_limit: int = 50,
    zero_means_default: bool = True,
) -> tuple[int, int]:
    """Clamp list pagination consistently across Teaching endpoints."""

    try:
        norm_limit = int(limit) if limit is not None else default_limit
    except (TypeError, ValueError):
        norm_limit = default_limit
    if zero_means_default and norm_limit == 0:
        norm_limit = default_limit
    norm_limit = max(1, min(max_limit, norm_limit))
    try:
        norm_offset = int(offset) if offset is not None else 0
    except (TypeError, ValueError):
        norm_offset = 0
    norm_offset = max(0, norm_offset)
    return norm_limit, norm_offset
