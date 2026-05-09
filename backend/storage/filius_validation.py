"""
Filius `.fls` validation helpers.

Why:
    Filius projects are ZIP archives containing `projekt/konfiguration.xml`.
    That XML is a Java XMLDecoder document, but untrusted student uploads must
    never enter a Java deserialization path. This module only reads bounded
    bytes and rejects executable or entity-enabled XML structures.

Security:
    - Never extract archives to disk.
    - Enforce entry, total-size, and configuration-size limits.
    - Reject DTD/DOCTYPE/entities and dangerous XMLDecoder classes.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import re
import zipfile

from backend.storage.config import get_learning_max_upload_bytes
from backend.storage.mime_types import FILIUS_FLS_MIME


FILIUS_CONFIGURATION_PATH = "projekt/konfiguration.xml"


class FiliusValidationError(ValueError):
    """Raised when a Filius archive fails validation.

    The exception message is a stable, API-facing detail code.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class FiliusLimits:
    """Hard limits used during Filius archive validation."""

    max_input_bytes: int = get_learning_max_upload_bytes()
    max_zip_entries: int = 256
    max_total_uncompressed_bytes: int = 50_000_000
    max_configuration_xml_bytes: int = 8_000_000


_DANGEROUS_XML_RE = re.compile(
    rb"<!DOCTYPE|<!ENTITY|SYSTEM\s+['\"]|PUBLIC\s+['\"]|java\.lang\.ProcessBuilder|java\.lang\.Runtime",
    re.IGNORECASE,
)


def _bounded_read(zf: zipfile.ZipFile, info: zipfile.ZipInfo, *, max_bytes: int) -> bytes:
    try:
        size = int(info.file_size)
    except Exception as exc:
        raise FiliusValidationError("invalid_filius_archive") from exc
    if size < 0:
        raise FiliusValidationError("invalid_filius_archive")
    if size > int(max_bytes):
        raise FiliusValidationError("filius_configuration_too_large")
    try:
        with zf.open(info, "r") as fh:
            data = fh.read(size + 1)
    except FiliusValidationError:
        raise
    except Exception as exc:
        raise FiliusValidationError("invalid_filius_archive") from exc
    if len(data) != size:
        raise FiliusValidationError("invalid_filius_archive")
    return data


def _reject_unsafe_xml(xml_bytes: bytes) -> None:
    if not xml_bytes:
        raise FiliusValidationError("invalid_filius_configuration")
    if _DANGEROUS_XML_RE.search(xml_bytes):
        raise FiliusValidationError("invalid_filius_configuration")
    try:
        text = xml_bytes[:512].decode("utf-8", errors="ignore").lower()
    except Exception as exc:
        raise FiliusValidationError("invalid_filius_configuration") from exc
    if "<java" not in text:
        raise FiliusValidationError("invalid_filius_configuration")


def extract_configuration_xml_bytes(fls_bytes: bytes, *, limits: FiliusLimits | None = None) -> bytes:
    """Return Filius `projekt/konfiguration.xml` bytes or raise FiliusValidationError."""
    limits = limits or FiliusLimits()
    if not isinstance(fls_bytes, (bytes, bytearray)) or not fls_bytes:
        raise FiliusValidationError("invalid_filius_archive")
    if len(fls_bytes) > int(limits.max_input_bytes):
        raise FiliusValidationError("filius_configuration_too_large")

    try:
        with zipfile.ZipFile(io.BytesIO(bytes(fls_bytes))) as zf:
            try:
                infos = zf.infolist()
            except Exception as exc:
                raise FiliusValidationError("invalid_filius_archive") from exc
            if len(infos) > int(limits.max_zip_entries):
                raise FiliusValidationError("filius_configuration_too_large")
            try:
                total_uncompressed = sum(int(i.file_size or 0) for i in infos)
            except Exception as exc:
                raise FiliusValidationError("invalid_filius_archive") from exc
            if total_uncompressed > int(limits.max_total_uncompressed_bytes):
                raise FiliusValidationError("filius_configuration_too_large")

            try:
                info = zf.getinfo(FILIUS_CONFIGURATION_PATH)
            except KeyError as exc:
                raise FiliusValidationError("missing_filius_configuration") from exc
            except Exception as exc:
                raise FiliusValidationError("invalid_filius_archive") from exc

            xml_bytes = _bounded_read(zf, info, max_bytes=int(limits.max_configuration_xml_bytes))
            _reject_unsafe_xml(xml_bytes)
            return xml_bytes
    except FiliusValidationError:
        raise
    except zipfile.BadZipFile as exc:
        raise FiliusValidationError("invalid_filius_archive") from exc
    except Exception as exc:
        raise FiliusValidationError("invalid_filius_archive") from exc
