"""
Storage ports used by vision/learning subsystems.

Keep these small and framework-agnostic so tests can supply simple fakes.
"""
from __future__ import annotations

from typing import Protocol


class BinaryWriteStorage(Protocol):
    """Minimal interface to write binary objects to a bucket/path.

    Intent:
        Allow pipeline code to persist derived artifacts (e.g., rendered pages)
        without depending on a specific cloud SDK.

    Permissions:
        Implementations must enforce bucket/key ACLs and validation.
    """

    def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None: ...


__all__ = ["BinaryWriteStorage"]

