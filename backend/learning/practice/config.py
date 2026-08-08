"""Configuration boundary for the practice-session rollout."""

from __future__ import annotations

import os


def practice_sessions_enabled() -> bool:
    """Return whether learners may start new practice sessions.

    The secure default is disabled. Existing sessions remain readable and can
    still be continued or ended when the flag is switched off.
    """

    return (os.getenv("ENABLE_PRACTICE_SESSIONS", "false") or "").strip().lower() == "true"
