"""
MakeCode HEX validation — deterministic extraction for Calliope tasks.

Intent:
    `.hex` uploads coming from MakeCode (makecode.calliope.cc) should be
    validated deterministically and converted into a small, bounded project
    snapshot that can be rendered for LLM-based feedback.

Security:
    - Validate Intel HEX structure and checksums.
    - Require MakeCode source embedding (magic + header).
    - Enforce strict size limits on decompression and file maps.
"""

from __future__ import annotations

import json
import lzma
import struct

import pytest


def _hex_record(*, addr: int, record_type: int, data: bytes) -> str:
    """Build one Intel HEX line with a valid checksum."""
    if addr < 0 or addr > 0xFFFF:
        raise ValueError("addr_out_of_range")
    if record_type < 0 or record_type > 0xFF:
        raise ValueError("record_type_out_of_range")
    if len(data) > 0xFF:
        raise ValueError("data_too_long")
    ll = len(data)
    total = ll + ((addr >> 8) & 0xFF) + (addr & 0xFF) + (record_type & 0xFF) + sum(data)
    checksum = (-total) & 0xFF
    return f":{ll:02X}{addr:04X}{record_type:02X}{data.hex().upper()}{checksum:02X}"


def _make_hex_with_embedded_source(*, eurl: str, record_type: int = 0x0D, place_after_eof: bool = False) -> bytes:
    # Keep the project minimal, but realistic.
    files = {
        "main.ts": 'basic.showString("Hi")\n',
        "pxt.json": json.dumps({"name": "test-project", "dependencies": {}}, separators=(",", ":")),
    }
    extra_header = {"name": "test-project"}
    extra_header_json = json.dumps(extra_header, separators=(",", ":"))
    files_json = json.dumps(files, separators=(",", ":"))
    text = (extra_header_json + files_json).encode("utf-8")
    compressed = lzma.compress(text, format=lzma.FORMAT_ALONE)

    header = {
        "eURL": eurl,
        "compression": "LZMA",
        "headerSize": len(extra_header_json),
        "textSize": len(text.decode("utf-8")),
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    magic = b"\x41\x14\x0E\x2F\xB8\x2F\xA2\xBB"
    blob = magic + struct.pack("<H", len(header_bytes)) + struct.pack("<I", len(compressed)) + b"\x00\x00"
    blob += header_bytes + compressed

    lines: list[str] = []
    chunk = 16
    if place_after_eof:
        # Real MakeCode downloads may append the embedded source *after* the
        # Intel-HEX EOF line (many flashing tools stop at EOF and ignore the rest).
        lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
        lines.append("")  # keep one blank line (common in real exports)
    for i in range(0, len(blob), chunk):
        # MakeCode source embedding may live in "custom" Intel HEX record types
        # (e.g. 0x0D/0x0E). Our extractor must treat those records as scan data.
        lines.append(_hex_record(addr=i, record_type=record_type, data=blob[i : i + chunk]))
    if not place_after_eof:
        lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
    return ("\n".join(lines) + "\n").encode("ascii")


def _make_hex_without_magic() -> bytes:
    blob = b"\x00" * 64
    lines: list[str] = []
    for i in range(0, len(blob), 16):
        lines.append(_hex_record(addr=i, record_type=0x00, data=blob[i : i + 16]))
    lines.append(_hex_record(addr=0, record_type=0x01, data=b""))
    return ("\n".join(lines) + "\n").encode("ascii")


def test_extract_makecode_project_from_hex_returns_files() -> None:
    from backend.storage.makecode_hex_validation import extract_makecode_project_from_hex

    hex_bytes = _make_hex_with_embedded_source(eurl="https://makecode.calliope.cc/#editor")
    project = extract_makecode_project_from_hex(hex_bytes)
    assert isinstance(project.files, dict)
    assert "main.ts" in project.files
    assert "basic.showString" in project.files["main.ts"]


def test_extract_makecode_project_from_hex_accepts_record_type_0e_embedding() -> None:
    from backend.storage.makecode_hex_validation import extract_makecode_project_from_hex

    # Real MakeCode Calliope downloads embed the source in record type 0x0E.
    hex_bytes = _make_hex_with_embedded_source(eurl="https://makecode.calliope.cc/#editor", record_type=0x0E)
    project = extract_makecode_project_from_hex(hex_bytes)
    assert "main.ts" in project.files


def test_extract_makecode_project_from_hex_accepts_embedding_after_eof() -> None:
    from backend.storage.makecode_hex_validation import extract_makecode_project_from_hex

    # Real MakeCode Calliope downloads may put the source embedding after EOF.
    hex_bytes = _make_hex_with_embedded_source(
        eurl="https://makecode.calliope.cc/#editor",
        record_type=0x0E,
        place_after_eof=True,
    )
    project = extract_makecode_project_from_hex(hex_bytes)
    assert "main.ts" in project.files


def test_does_not_reject_hex_when_eurl_host_is_unexpected() -> None:
    from backend.storage.makecode_hex_validation import extract_makecode_project_from_hex

    hex_bytes = _make_hex_with_embedded_source(eurl="https://makecode.microbit.org/#editor")
    project = extract_makecode_project_from_hex(hex_bytes)
    assert "main.ts" in project.files


def test_missing_makecode_source_raises() -> None:
    from backend.storage.makecode_hex_validation import MakeCodeHexValidationError, extract_makecode_project_from_hex

    hex_bytes = _make_hex_without_magic()
    with pytest.raises(MakeCodeHexValidationError) as exc:
        _ = extract_makecode_project_from_hex(hex_bytes)
    assert exc.value.code == "missing_makecode_source"


def test_invalid_checksum_is_rejected() -> None:
    from backend.storage.makecode_hex_validation import MakeCodeHexValidationError, extract_makecode_project_from_hex

    # Corrupt checksum (last byte) on a minimal EOF-only file.
    bad = b":00000001FE\n"
    with pytest.raises(MakeCodeHexValidationError) as exc:
        _ = extract_makecode_project_from_hex(bad)
    assert exc.value.code == "invalid_hex_file"
