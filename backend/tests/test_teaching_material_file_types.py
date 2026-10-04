"""Closed material-file policy shared by API, CLI and synchronization."""

from __future__ import annotations

import pytest

from backend.teaching.material_file_types import (
    canonical_material_mime,
    is_inline_preview_mime,
    material_download_disposition,
    validate_material_file_type,
)

SUPPORTED = [
    ("projekt.sb3", "application/x.scratch.sb3"),
    ("programm.hex", "application/x.makecode.hex"),
    ("netz.fls", "application/x.filius.fls"),
    ("sortieren.py", "text/x-python"),
    ("daten.json", "application/json"),
    ("hinweise.txt", "text/plain"),
    ("arbeitsblatt.odt", "application/vnd.oasis.opendocument.text"),
    ("messwerte.ods", "application/vnd.oasis.opendocument.spreadsheet"),
    ("vortrag.odp", "application/vnd.oasis.opendocument.presentation"),
]


@pytest.mark.parametrize(("filename", "mime_type"), SUPPORTED)
def test_program_and_opendocument_extensions_have_canonical_mime_types(
    filename: str, mime_type: str
) -> None:
    assert canonical_material_mime(filename) == mime_type
    assert validate_material_file_type(filename, mime_type) == mime_type
    assert is_inline_preview_mime(mime_type) is False
    assert material_download_disposition(mime_type, "inline") == "attachment"


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("bild.png", "image/png"),
        ("foto.jpg", "image/jpeg"),
        ("foto.jpeg", "image/jpeg"),
        ("blatt.pdf", "application/pdf"),
    ],
)
def test_existing_preview_types_keep_inline_support(filename: str, mime_type: str) -> None:
    assert validate_material_file_type(filename, mime_type) == mime_type
    assert is_inline_preview_mime(mime_type) is True
    assert material_download_disposition(mime_type, "inline") == "inline"


def test_material_file_policy_rejects_unknown_extensions_and_mime_mismatches() -> None:
    with pytest.raises(ValueError, match="invalid_filename"):
        canonical_material_mime("programm.exe")
    with pytest.raises(ValueError, match="mime_not_allowed"):
        validate_material_file_type("programm.py", "text/plain")
    with pytest.raises(ValueError, match="mime_not_allowed"):
        validate_material_file_type("programm.py", "application/octet-stream")


def test_material_file_policy_is_case_insensitive_but_returns_canonical_values() -> None:
    assert validate_material_file_type("PROJEKT.SB3", " APPLICATION/X.SCRATCH.SB3 ") == (
        "application/x.scratch.sb3"
    )
