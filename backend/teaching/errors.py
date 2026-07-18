"""Stable Teaching errors shared by application and infrastructure adapters."""

from __future__ import annotations


class TeachingRepositoryUnavailable(RuntimeError):
    """Signal that the required Teaching repository is temporarily unavailable."""
