"""
Centralized storage configuration for buckets and policies.

Intent:
    Provide a single source of truth for default bucket names and their
    environment-variable overrides used by teaching (materials) and learning
    (submissions) domains. Prevents drift across modules and enables simple
    testing.

Behavior:
    - MATERIALS_BUCKET_DEFAULT and SUBMISSIONS_BUCKET_DEFAULT define canonical
      defaults ("materials" / "submissions").
    - get_materials_bucket() and get_submissions_bucket() read env overrides
      (SUPABASE_STORAGE_BUCKET / LEARNING_STORAGE_BUCKET) with sane fallbacks.

Permissions:
    Pure configuration; no external calls or privileges required.
"""
from __future__ import annotations

import os


MATERIALS_BUCKET_DEFAULT = "materials"
SUBMISSIONS_BUCKET_DEFAULT = "submissions"


def get_materials_bucket() -> str:
    """Return the configured materials bucket name.

    Env:
        SUPABASE_STORAGE_BUCKET – optional override; otherwise defaults to
        MATERIALS_BUCKET_DEFAULT.
    """
    return (os.getenv("SUPABASE_STORAGE_BUCKET") or MATERIALS_BUCKET_DEFAULT).strip()


def get_submissions_bucket() -> str:
    """Return the configured submissions bucket name.

    Env:
        LEARNING_STORAGE_BUCKET – optional override; otherwise defaults to
        SUBMISSIONS_BUCKET_DEFAULT.
    """
    return (os.getenv("LEARNING_STORAGE_BUCKET") or SUBMISSIONS_BUCKET_DEFAULT).strip()


__all__ = [
    "MATERIALS_BUCKET_DEFAULT",
    "SUBMISSIONS_BUCKET_DEFAULT",
    "get_materials_bucket",
    "get_submissions_bucket",
]

# --- Size limits --------------------------------------------------------------

def _parse_int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def get_learning_max_upload_bytes() -> int:
    """Maximum upload size for learning submissions (default 10 MiB)."""
    return _parse_int_env("LEARNING_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)


def get_materials_max_upload_bytes() -> int:
    """Maximum upload size for teaching materials (default 20 MiB)."""
    return _parse_int_env("MATERIALS_MAX_UPLOAD_BYTES", 20 * 1024 * 1024)


__all__ += [
    "get_learning_max_upload_bytes",
    "get_materials_max_upload_bytes",
]
