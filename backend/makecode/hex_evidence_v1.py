"""
Deterministic MakeCode HEX evidence extraction (v1).

Intent:
    Convert a MakeCode project snapshot (files map) into a stable, bounded
    Markdown report that is safe to feed into an LLM for criteria-based
    feedback.

Why:
    Raw `.hex` files are not LLM-friendly. Evidence should:
    - expose the relevant source files (main.ts/main.py, pxt.json)
    - stay deterministic (no LLM calls)
    - be bounded (avoid giant prompts and injection via huge payloads)
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Iterable

from backend.storage.makecode_hex_validation import MakeCodeProject


EVIDENCE_SCHEMA_V1 = "makecode.evidence.v1"


@dataclass(frozen=True, slots=True)
class EvidenceV1Limits:
    """Hard limits used while rendering evidence."""

    max_markdown_chars: int = 200_000
    max_files: int = 20
    max_filename_chars: int = 200
    max_file_chars: int = 15_000


def limits_from_env(defaults: EvidenceV1Limits | None = None) -> EvidenceV1Limits:
    """Build limits with optional ENV overrides (prod-compatible)."""
    base = defaults or EvidenceV1Limits()

    def _int(name: str, default: int) -> int:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return int(default)
        try:
            value = int(raw)
        except Exception:
            return int(default)
        return max(1, value)

    return EvidenceV1Limits(
        max_markdown_chars=_int("MAKECODE_EVIDENCE_MAX_MARKDOWN_CHARS", base.max_markdown_chars),
        max_files=_int("MAKECODE_EVIDENCE_MAX_FILES", base.max_files),
        max_filename_chars=_int("MAKECODE_EVIDENCE_MAX_FILENAME_CHARS", base.max_filename_chars),
        max_file_chars=_int("MAKECODE_EVIDENCE_MAX_FILE_CHARS", base.max_file_chars),
    )


def _json_str(value: object, *, limits: EvidenceV1Limits) -> str:
    """Render untrusted text as a single-line JSON string.

    We use this for file names to prevent Markdown structure injection via
    newlines (e.g. "name\\n# heading").
    """
    raw = str(value or "")
    if len(raw) > int(limits.max_filename_chars):
        raw = raw[: int(limits.max_filename_chars)] + "…"
    return json.dumps(raw, ensure_ascii=True)


def _language_hint(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".ts"):
        return "typescript"
    if name.endswith(".py"):
        return "python"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".md"):
        return "markdown"
    return "text"


def _code_fence(text: str) -> str:
    # Use a fence longer than any backtick run in the text to prevent escaping.
    max_run = 0
    run = 0
    for ch in text or "":
        if ch == "`":
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return "`" * max(3, max_run + 1)


def _preferred_file_order(names: Iterable[str]) -> list[str]:
    priority = ["main.ts", "main.py", "pxt.json", "README.md", "readme.md"]
    remaining = sorted({str(n) for n in names}, key=lambda x: x.casefold())
    out: list[str] = []
    for p in priority:
        if p in remaining:
            out.append(p)
            remaining.remove(p)
    out.extend(remaining)
    return out


def build_evidence_markdown_v1(*, project: MakeCodeProject, limits: EvidenceV1Limits | None = None) -> str:
    """Build `makecode.evidence.v1` Markdown from extracted MakeCode project files."""
    limits = limits or limits_from_env()
    max_total = int(limits.max_markdown_chars)

    parts: list[str] = []

    def _add(text: str) -> None:
        if not text:
            return
        if sum(len(p) for p in parts) >= max_total:
            return
        remaining = max_total - sum(len(p) for p in parts)
        parts.append(text[:remaining])

    _add(f"# {EVIDENCE_SCHEMA_V1}\n\n")
    _add("## Summary\n")
    _add(f"- files_count: {len(project.files)}\n")
    _add("\n")

    _add("## Files\n\n")
    names = _preferred_file_order(project.files.keys())
    shown = 0
    for name in names:
        if shown >= int(limits.max_files):
            break
        body = project.files.get(name)
        if not isinstance(body, str):
            continue
        shown += 1
        lang = _language_hint(name)
        safe_name = _json_str(name, limits=limits)
        trimmed = body
        if len(trimmed) > int(limits.max_file_chars):
            trimmed = trimmed[: int(limits.max_file_chars)] + "\n/* … truncated … */\n"
        fence = _code_fence(trimmed)
        _add(f"### file: {safe_name}\n")
        _add(f"{fence}{lang}\n")
        _add(trimmed.rstrip() + "\n")
        _add(f"{fence}\n\n")

    if shown == 0:
        _add("_No readable files extracted._\n")

    out = "".join(parts)
    return out if out.strip() else f"# {EVIDENCE_SCHEMA_V1}\n\n_No evidence._\n"


__all__ = ["EVIDENCE_SCHEMA_V1", "EvidenceV1Limits", "build_evidence_markdown_v1", "limits_from_env"]
