"""Pytest import-path guard helpers.

Why:
    Tests now use the same package-oriented imports as Docker and production:
    `backend.*`. This module stays as a small compatibility surface for
    `conftest.py`, but it must not add extra import roots.
"""

from __future__ import annotations



def configure_test_import_paths() -> None:
    """Keep the historical hook as a no-op while tests use package imports."""


def canonicalize_legacy_route_aliases() -> None:
    """Keep the historical hook as a no-op after route aliases were removed."""
