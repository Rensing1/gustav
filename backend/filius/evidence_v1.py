"""
Filius Evidence v1 renderer.

Why:
    The feedback pipeline needs a stable text representation of Filius uploads.
    This renderer starts from the validated `.fls` bytes and emits bounded
    Markdown; it never forwards raw XML to the LLM.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from backend.storage.filius_validation import extract_configuration_xml_bytes


EVIDENCE_SCHEMA_V1 = "filius.evidence.v1"
_SECTION_HEADINGS = (
    "Project",
    "Parser Notes",
    "Nodes",
    "Links",
    "Routing",
    "Firewall",
    "DNS",
    "Web",
    "Email",
    "Documentation",
    "Custom Applications",
)
_CLASS_RE = re.compile(rb'class\s*=\s*"([^"]+)"|class\s*=\s*\'([^\']+)\'')


def _safe_text(value: object, *, max_chars: int = 2000) -> str:
    text = str(value or "")
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    if len(text) > max_chars:
        text = text[:max_chars] + f" [truncated: original_chars={len(text)} shown_chars={max_chars}]"
    return text


def _extract_version(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return "unknown"
    first_string = root.find("string")
    if first_string is not None and first_string.text:
        return first_string.text.strip() or "unknown"
    return "unknown"


def _extract_classes(xml_bytes: bytes) -> list[str]:
    classes: set[str] = set()
    for match in _CLASS_RE.finditer(xml_bytes):
        raw = match.group(1) or match.group(2) or b""
        try:
            text = raw.decode("utf-8")
        except Exception:
            continue
        if text.startswith("filius."):
            classes.add(text)
    return sorted(classes, key=str.casefold)


def build_evidence_markdown_v1(fls_bytes: bytes) -> str:
    """Build deterministic Markdown evidence from validated Filius `.fls` bytes."""
    xml_bytes = extract_configuration_xml_bytes(fls_bytes)
    version = _safe_text(_extract_version(xml_bytes))
    classes = _extract_classes(xml_bytes)

    lines: list[str] = [f"# {EVIDENCE_SCHEMA_V1}", ""]
    for heading in _SECTION_HEADINGS:
        lines.append(f"## {heading}")
        if heading == "Project":
            lines.append(f'- schema: "{EVIDENCE_SCHEMA_V1}"')
            lines.append(f'- filius_version: "{version}"')
        elif heading == "Parser Notes":
            lines.append(f"- extracted_classes: {len(classes)}")
        elif heading == "Nodes" and classes:
            for index, class_name in enumerate(classes, start=1):
                lines.append(f'### n{index}')
                lines.append(f'- class: "{_safe_text(class_name)}"')
        else:
            lines.append("none")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
