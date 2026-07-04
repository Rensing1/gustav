"""Small runtime configuration helpers for the web adapter."""

from __future__ import annotations

import os


def load_teaching_live_poll_interval_seconds() -> int:
    """Load and clamp the Teaching Live polling interval from environment.

    Behavior:
        - Reads `GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS`.
        - Falls back to 3 seconds when unset or invalid.
        - Clamps the value to [1, 60] so the UI neither hammers the server nor
          hides updates for too long.
    """

    raw = os.getenv("GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS", "3") or "3"
    try:
        value = int(raw)
    except Exception:
        return 3
    if value < 1:
        return 1
    if value > 60:
        return 60
    return value
