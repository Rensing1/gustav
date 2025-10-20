"""
Identity domain constants and simple helpers.

Why:
- Centralize allowed roles to avoid drift between tools and web layer.
- Keep terms aligned with GLOSSARY.md and used consistently across modules.
"""

from __future__ import annotations

# Keep roles minimal and explicit. Immutable to prevent accidental mutation.
ALLOWED_ROLES = frozenset({"student", "teacher", "admin"})

__all__ = ["ALLOWED_ROLES"]

