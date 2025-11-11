"""
Shared authentication utilities.

Why:
    Avoid duplicating environment-dependent cookie policy logic across modules
    (e.g., main app and auth router). Keeping a single helper improves
    consistency and makes teaching/testing easier.

Design:
    The helper is framework-agnostic and pure: it accepts an environment string
    and returns the corresponding cookie flags. Callers decide where the
    environment comes from (e.g., settings object).
"""

from __future__ import annotations


def cookie_opts(environment: str) -> dict:
    """Return hardened cookie flags (dev = prod).

    Intent: Unify environments to production-grade flags to prevent CSRF and
    cookie leakage regardless of local/prod settings.

    Returns a mapping with keys:
      - secure: True
      - samesite: "strict"
    """
    return {"secure": True, "samesite": "strict"}
