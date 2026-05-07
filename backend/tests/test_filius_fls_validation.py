"""
Filius `.fls` validation helpers.

Intent:
    Filius files are ZIP archives containing `projekt/konfiguration.xml`.
    Validation must be deterministic, bounded, and must never deserialize Java
    XMLDecoder content.
"""

from __future__ import annotations

import io
import zipfile

import pytest


VALID_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<java version="17" class="java.beans.XMLDecoder">
  <string>2.5</string>
</java>
"""


def _fls_with_config(config: bytes = VALID_XML, *, name: str = "projekt/konfiguration.xml") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, config)
    return buf.getvalue()


def test_extract_configuration_xml_returns_project_configuration() -> None:
    from backend.storage.filius_validation import extract_configuration_xml_bytes

    xml = extract_configuration_xml_bytes(_fls_with_config())

    assert xml == VALID_XML


@pytest.mark.parametrize(
    "fls_bytes,expected",
    [
        (b"not a zip", "invalid_filius_archive"),
        (_fls_with_config(name="other.xml"), "missing_filius_configuration"),
        (_fls_with_config(b"<!DOCTYPE java><java></java>"), "invalid_filius_configuration"),
        (_fls_with_config(b"<java><object class='java.lang.ProcessBuilder'/></java>"), "invalid_filius_configuration"),
    ],
)
def test_invalid_filius_archives_raise_stable_codes(fls_bytes: bytes, expected: str) -> None:
    from backend.storage.filius_validation import FiliusValidationError, extract_configuration_xml_bytes

    with pytest.raises(FiliusValidationError) as exc:
        extract_configuration_xml_bytes(fls_bytes)

    assert exc.value.code == expected


def test_configuration_size_limit_raises_stable_code() -> None:
    from backend.storage.filius_validation import FiliusLimits, FiliusValidationError, extract_configuration_xml_bytes

    with pytest.raises(FiliusValidationError) as exc:
        extract_configuration_xml_bytes(
            _fls_with_config(VALID_XML + b"x" * 10),
            limits=FiliusLimits(max_configuration_xml_bytes=len(VALID_XML)),
        )

    assert exc.value.code == "filius_configuration_too_large"
