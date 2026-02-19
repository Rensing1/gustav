"""
Scratch `.sb3` validation helpers.

Why:
    Scratch projects are submitted as `.sb3` files (ZIP archives). For security
    and predictable evaluation we validate the container and require the
    presence of `project.json` (the source-of-truth for sprites/blocks/etc.).

Security:
    - Never extract to disk.
    - Enforce strict limits to mitigate zip bombs (entry count, total
      uncompressed size, project.json size).
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any


SCRATCH_SB3_MIME = "application/x.scratch.sb3"


class SB3ValidationError(ValueError):
    """Raised when an SB3 archive fails validation.

    The exception message is a stable, API-facing detail code.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SB3Limits:
    """Hard limits used during SB3 validation."""

    max_zip_entries: int = 2048
    max_total_uncompressed_bytes: int = 50_000_000
    max_project_json_bytes: int = 5_000_000


def _bounded_read(zf: zipfile.ZipFile, info: zipfile.ZipInfo, *, max_bytes: int) -> bytes:
    if info.file_size is None:
        raise SB3ValidationError("invalid_sb3_archive")
    try:
        size = int(info.file_size)
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")
    if size < 0 or size > int(max_bytes):
        raise SB3ValidationError("invalid_sb3_archive")
    try:
        with zf.open(info, "r") as fh:
            data = fh.read(size + 1)
    except SB3ValidationError:
        raise
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")
    if len(data) != size:
        # Unexpected truncated/expanded read indicates a broken archive.
        raise SB3ValidationError("invalid_sb3_archive")
    return data


def extract_project_json_bytes(sb3_bytes: bytes, *, limits: SB3Limits | None = None) -> bytes:
    """Return `project.json` bytes from an SB3 archive or raise SB3ValidationError."""
    if not isinstance(sb3_bytes, (bytes, bytearray)) or not sb3_bytes:
        raise SB3ValidationError("invalid_sb3_archive")
    limits = limits or SB3Limits()
    try:
        zf = zipfile.ZipFile(io.BytesIO(bytes(sb3_bytes)))
    except zipfile.BadZipFile:
        raise SB3ValidationError("invalid_sb3_archive")
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")

    try:
        infos = zf.infolist()
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")
    if len(infos) > int(limits.max_zip_entries):
        raise SB3ValidationError("invalid_sb3_archive")
    try:
        total_uncompressed = sum(int(i.file_size or 0) for i in infos)
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")
    if total_uncompressed > int(limits.max_total_uncompressed_bytes):
        raise SB3ValidationError("invalid_sb3_archive")

    try:
        info = zf.getinfo("project.json")
    except KeyError:
        raise SB3ValidationError("missing_project_json")
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")

    data = _bounded_read(zf, info, max_bytes=int(limits.max_project_json_bytes))
    if not data:
        raise SB3ValidationError("invalid_sb3_archive")
    return data


def load_project_json(sb3_bytes: bytes, *, limits: SB3Limits | None = None) -> dict[str, Any]:
    """Parse and return the SB3 `project.json` object (dict).

    Raises:
        SB3ValidationError with one of:
            - invalid_sb3_archive
            - missing_project_json
    """
    raw = extract_project_json_bytes(sb3_bytes, limits=limits)
    try:
        text = raw.decode("utf-8")
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")
    try:
        parsed = json.loads(text)
    except Exception:
        raise SB3ValidationError("invalid_sb3_archive")
    if not isinstance(parsed, dict):
        raise SB3ValidationError("invalid_sb3_archive")
    targets = parsed.get("targets")
    if not isinstance(targets, list):
        raise SB3ValidationError("invalid_sb3_archive")
    return parsed  # type: ignore[return-value]

