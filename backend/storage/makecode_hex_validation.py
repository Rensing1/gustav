"""
MakeCode `.hex` validation helpers (Calliope tasks).

Why:
    Calliope MakeCode projects are submitted as `.hex` files (Intel HEX).
    For security and predictable evaluation we validate the container and
    require MakeCode "source embedding" so we can deterministically extract
    the student's project files (e.g. main.ts, pxt.json).

Security:
    - Validate Intel HEX structure and checksums (reject malformed input).
    - Enforce strict bounds on parsed bytes and decompression output.
    - Do not write to disk; operate on bytes only.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import lzma
import os
import struct
from typing import Any


MAKECODE_HEX_MIME = "application/x.makecode.hex"

# MakeCode source embedding magic bytes. See: https://makecode.com/source-embedding
_PXT_MAGIC = b"\x41\x14\x0E\x2F\xB8\x2F\xA2\xBB"


class MakeCodeHexValidationError(ValueError):
    """Raised when a MakeCode HEX payload fails validation.

    The exception message is a stable, API-facing detail code.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class MakeCodeProject:
    """Minimal project snapshot extracted from a MakeCode HEX payload."""

    files: dict[str, str]
    meta: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MakeCodeHexLimits:
    """Hard limits used during HEX parsing and source extraction."""

    max_input_bytes: int = 10 * 1024 * 1024  # contract: 10 MiB
    max_lines: int = 250_000
    max_total_data_bytes: int = 6_000_000
    max_header_json_bytes: int = 200_000
    max_compressed_text_bytes: int = 6_000_000
    max_decompressed_text_bytes: int = 2_000_000
    max_files: int = 80
    max_file_chars: int = 200_000


def limits_from_env(defaults: MakeCodeHexLimits | None = None) -> MakeCodeHexLimits:
    """Build limits with optional ENV overrides (prod-compatible)."""
    base = defaults or MakeCodeHexLimits()

    def _int(name: str, default: int) -> int:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return int(default)
        try:
            value = int(raw)
        except Exception:
            return int(default)
        return max(1, value)

    return MakeCodeHexLimits(
        max_input_bytes=_int("MAKECODE_HEX_MAX_INPUT_BYTES", base.max_input_bytes),
        max_lines=_int("MAKECODE_HEX_MAX_LINES", base.max_lines),
        max_total_data_bytes=_int("MAKECODE_HEX_MAX_TOTAL_DATA_BYTES", base.max_total_data_bytes),
        max_header_json_bytes=_int("MAKECODE_HEX_MAX_HEADER_JSON_BYTES", base.max_header_json_bytes),
        max_compressed_text_bytes=_int("MAKECODE_HEX_MAX_COMPRESSED_TEXT_BYTES", base.max_compressed_text_bytes),
        max_decompressed_text_bytes=_int("MAKECODE_HEX_MAX_DECOMPRESSED_TEXT_BYTES", base.max_decompressed_text_bytes),
        max_files=_int("MAKECODE_HEX_MAX_FILES", base.max_files),
        max_file_chars=_int("MAKECODE_HEX_MAX_FILE_CHARS", base.max_file_chars),
    )


def _decode_hex_bytes(text: str) -> bytes:
    try:
        return bytes.fromhex(text)
    except Exception as exc:
        raise MakeCodeHexValidationError("invalid_hex_file") from exc


def _parse_hex_byte(text: str) -> int:
    try:
        return int(text, 16)
    except Exception as exc:
        raise MakeCodeHexValidationError("invalid_hex_file") from exc


def _parse_hex_u16(text: str) -> int:
    try:
        return int(text, 16)
    except Exception as exc:
        raise MakeCodeHexValidationError("invalid_hex_file") from exc


def _validate_checksum(*, ll: int, addr: int, record_type: int, data: bytes, checksum: int) -> None:
    total = ll + ((addr >> 8) & 0xFF) + (addr & 0xFF) + (record_type & 0xFF) + sum(data) + (checksum & 0xFF)
    if (total & 0xFF) != 0:
        raise MakeCodeHexValidationError("invalid_hex_file")


def _decompress_lzma_with_limit(data: bytes, *, max_bytes: int) -> bytes:
    """Decompress LZMA data while enforcing an output cap."""
    try:
        decomp = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO)
        out = decomp.decompress(data, max_length=int(max_bytes) + 1)
    except lzma.LZMAError as exc:
        raise MakeCodeHexValidationError("invalid_hex_file") from exc
    except Exception as exc:
        raise MakeCodeHexValidationError("invalid_hex_file") from exc
    if len(out) > int(max_bytes) or (not decomp.eof):
        raise MakeCodeHexValidationError("makecode_source_too_large")
    return bytes(out)


def _bounded_files_map(raw: dict[str, Any], *, limits: MakeCodeHexLimits) -> dict[str, str]:
    """Normalize and bound a MakeCode files map (dict[str,str])."""
    out: dict[str, str] = {}
    for name in sorted(raw.keys(), key=lambda x: str(x).casefold()):
        if len(out) >= int(limits.max_files):
            break
        if not isinstance(name, str):
            continue
        content = raw.get(name)
        if not isinstance(content, str):
            continue
        text = content
        if len(text) > int(limits.max_file_chars):
            text = text[: int(limits.max_file_chars)] + "\n/* … truncated … */\n"
        out[name] = text
    return out


def extract_makecode_project_from_hex(hex_bytes: bytes, *, limits: MakeCodeHexLimits | None = None) -> MakeCodeProject:
    """Extract a bounded MakeCode project snapshot from an Intel HEX payload.

    Raises:
        MakeCodeHexValidationError with one of:
            - invalid_hex_file
            - missing_makecode_source
            - makecode_source_too_large
    """
    limits = limits or limits_from_env()
    if not isinstance(hex_bytes, (bytes, bytearray)) or not hex_bytes:
        raise MakeCodeHexValidationError("invalid_hex_file")
    if len(hex_bytes) > int(limits.max_input_bytes):
        raise MakeCodeHexValidationError("invalid_hex_file")

    try:
        text = bytes(hex_bytes).decode("ascii")
    except Exception as exc:
        raise MakeCodeHexValidationError("invalid_hex_file") from exc

    # Parse Intel HEX records into contiguous memory segments (address -> bytes).
    segments: list[tuple[int, bytes]] = []
    addr_base = 0
    total_data = 0
    lines_seen = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lines_seen += 1
        if lines_seen > int(limits.max_lines):
            raise MakeCodeHexValidationError("invalid_hex_file")
        if not line.startswith(":"):
            raise MakeCodeHexValidationError("invalid_hex_file")
        # Minimal record has 1 + 2(ll) + 4(addr) + 2(type) + 2(checksum) = 11 chars.
        if len(line) < 11:
            raise MakeCodeHexValidationError("invalid_hex_file")
        ll = _parse_hex_byte(line[1:3])
        addr = _parse_hex_u16(line[3:7])
        record_type = _parse_hex_byte(line[7:9])
        expected_len = 11 + (ll * 2)
        if len(line) != expected_len:
            raise MakeCodeHexValidationError("invalid_hex_file")
        data_hex = line[9 : 9 + (ll * 2)]
        checksum = _parse_hex_byte(line[9 + (ll * 2) : 11 + (ll * 2)])
        data = _decode_hex_bytes(data_hex) if ll else b""
        if len(data) != ll:
            raise MakeCodeHexValidationError("invalid_hex_file")
        _validate_checksum(ll=ll, addr=addr, record_type=record_type, data=data, checksum=checksum)

        if record_type == 0x01:
            # Intel HEX EOF traditionally terminates the file. However, MakeCode
            # exports (incl. Calliope) may append the source embedding *after*
            # the EOF line because flashing tools typically stop at EOF and
            # ignore any trailing records. We therefore continue parsing.
            continue
        if record_type == 0x04:
            if ll != 2:
                raise MakeCodeHexValidationError("invalid_hex_file")
            upper = int.from_bytes(data, "big")
            addr_base = int(upper) << 16
            continue
        if record_type == 0x02:
            if ll != 2:
                raise MakeCodeHexValidationError("invalid_hex_file")
            seg = int.from_bytes(data, "big")
            addr_base = int(seg) << 4
            continue

        # Treat both normal data (00) and "custom data" records (e.g. 0x0D/0x0E)
        # as bytes to scan. MakeCode embeds source into the flashed image.
        if record_type in (0x00, 0x0D, 0x0E) and data:
            total_data += len(data)
            if total_data > int(limits.max_total_data_bytes):
                raise MakeCodeHexValidationError("invalid_hex_file")
            abs_addr = int(addr_base) + int(addr)
            segments.append((abs_addr, data))

    if not segments:
        raise MakeCodeHexValidationError("missing_makecode_source")

    # Merge strictly-contiguous segments (avoid mixing across overlaps).
    merged: list[tuple[int, bytes]] = []
    for addr, data in sorted(segments, key=lambda x: x[0]):
        if not merged:
            merged.append((addr, data))
            continue
        prev_addr, prev_data = merged[-1]
        prev_end = prev_addr + len(prev_data)
        if addr == prev_end:
            merged[-1] = (prev_addr, prev_data + data)
        else:
            merged.append((addr, data))

    # Find the first valid embedded project. HEX payloads may contain multiple
    # embedded-source markers; we scan fail-soft so a corrupted marker does not
    # hide a later valid one.
    saw_marker = False
    for seg_addr, seg_bytes in merged:
        start = 0
        while True:
            idx = seg_bytes.find(_PXT_MAGIC, start)
            if idx < 0:
                break
            abs_addr = seg_addr + idx
            start = idx + 1
            # MakeCode aligns the header to 16 bytes.
            if abs_addr % 16 != 0:
                continue
            if idx + 16 > len(seg_bytes):
                continue
            saw_marker = True
            json_len = int.from_bytes(seg_bytes[idx + 8 : idx + 10], "little")
            text_len = int.from_bytes(seg_bytes[idx + 10 : idx + 14], "little")
            if json_len <= 0 or json_len > int(limits.max_header_json_bytes):
                continue
            if text_len <= 0 or text_len > int(limits.max_compressed_text_bytes):
                continue
            total_len = 16 + json_len + text_len
            if idx + total_len > len(seg_bytes):
                continue
            header_bytes = seg_bytes[idx + 16 : idx + 16 + json_len]
            text_bytes = seg_bytes[idx + 16 + json_len : idx + total_len]

            try:
                header_text = header_bytes.decode("utf-8")
                header = json.loads(header_text)
            except Exception:
                continue
            if not isinstance(header, dict):
                continue

            compression = str(header.get("compression") or "").strip().upper()
            if compression and compression != "LZMA":
                continue
            try:
                if compression == "LZMA":
                    decompressed = _decompress_lzma_with_limit(
                        text_bytes, max_bytes=int(limits.max_decompressed_text_bytes)
                    )
                else:
                    decompressed = bytes(text_bytes)
                    if len(decompressed) > int(limits.max_decompressed_text_bytes):
                        raise MakeCodeHexValidationError("makecode_source_too_large")
            except MakeCodeHexValidationError as exc:
                if str(exc.code) == "makecode_source_too_large":
                    raise
                continue

            try:
                text_str = decompressed.decode("utf-8")
            except Exception:
                continue

            header_size = header.get("headerSize") or 0
            if header_size is None:
                header_size = 0
            if not isinstance(header_size, int):
                continue
            if header_size < 0 or header_size > len(text_str):
                continue

            extra_header: dict[str, Any] = {}
            if header_size:
                try:
                    extra_header = json.loads(text_str[:header_size])
                except Exception:
                    continue
                if not isinstance(extra_header, dict):
                    continue

            try:
                files_raw = json.loads(text_str[header_size:])
            except Exception:
                continue
            if not isinstance(files_raw, dict):
                continue

            files = _bounded_files_map(files_raw, limits=limits)
            if not files:
                continue
            meta = {"header": header, "extra_header": extra_header}
            return MakeCodeProject(files=files, meta=meta)

    # Distinguish "no marker present" from "marker present but corrupted" so
    # clients can guide students appropriately (re-export vs enable source embedding).
    if saw_marker:
        raise MakeCodeHexValidationError("invalid_hex_file")
    raise MakeCodeHexValidationError("missing_makecode_source")


__all__ = [
    "MAKECODE_HEX_MIME",
    "MakeCodeHexValidationError",
    "MakeCodeHexLimits",
    "MakeCodeProject",
    "extract_makecode_project_from_hex",
    "limits_from_env",
]
