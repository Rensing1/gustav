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
    """Return cookie flags for the given environment.

    Parameters
    ----------
    environment:
        Environment name (e.g., "dev" or "prod"). Values are case-insensitive.

    Returns
    -------
    dict
        Mapping with keys "secure" and "samesite" configured as follows:
        - prod:  secure=True,  samesite="strict"
        - other: secure=False, samesite="lax"
    """
    env = (environment or "").lower()
    secure = env == "prod"
    samesite = "strict" if secure else "lax"
    return {"secure": secure, "samesite": samesite}

