"""
Shared upload policy for the learning domain.

Centralises MIME/type/size/path constraints so that routers stay slim and both
tests and documentation can reference a single source of truth.
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass
from typing import Iterable, Mapping

from .verification import VerificationConfig

ALLOWED_IMAGE_MIME = frozenset({"image/jpeg", "image/png"})
ALLOWED_FILE_MIME = frozenset({"application/pdf"})
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
STORAGE_KEY_RE = re.compile(r"(?!(?:.*\.\.))[a-z0-9][a-z0-9_./\-]{0,255}")


@dataclass(frozen=True, slots=True)
class LearningUploadPolicy:
    """Immutable policy object used at request-handling time."""

    allowed_mime_types: frozenset[str]
    max_size_bytes: int
    storage_key_pattern: re.Pattern[str]

    def accepted_for_kind(self, kind: str) -> list[str]:
        mapping: Mapping[str, Iterable[str]] = {
            "image": ALLOWED_IMAGE_MIME,
            "file": ALLOWED_FILE_MIME,
        }
        return sorted(set(mapping.get(kind, ())))


DEFAULT_POLICY = LearningUploadPolicy(
    allowed_mime_types=frozenset(ALLOWED_IMAGE_MIME | ALLOWED_FILE_MIME),
    max_size_bytes=MAX_UPLOAD_BYTES,
    storage_key_pattern=STORAGE_KEY_RE,
)


def verification_config_from_env() -> VerificationConfig:
    """Build verification configuration based on environment defaults."""

    bucket = (os.getenv("LEARNING_STORAGE_BUCKET") or "submissions").strip()
    require = (os.getenv("REQUIRE_STORAGE_VERIFY", "false") or "").lower() == "true"
    root = (os.getenv("STORAGE_VERIFY_ROOT") or "").strip() or None
    return VerificationConfig(storage_bucket=bucket, require_remote=require, local_verify_root=root)
