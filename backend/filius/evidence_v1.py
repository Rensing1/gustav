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
from backend.filius.topology import (
    FiliusApplication,
    FiliusFilesystemFile,
    FiliusInterface,
    FiliusManualRoute,
    FiliusTopology,
    extract_topology,
)


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
    topology = extract_topology(xml_bytes)

    lines: list[str] = [f"# {EVIDENCE_SCHEMA_V1}", ""]
    for heading in _SECTION_HEADINGS:
        lines.append(f"## {heading}")
        if heading == "Project":
            lines.append(f'- schema: "{EVIDENCE_SCHEMA_V1}"')
            lines.append(f'- filius_version: "{version}"')
        elif heading == "Parser Notes":
            lines.append(f"- extracted_classes: {len(classes)}")
            if classes:
                lines.append(f'- extracted_class_names: "{_safe_text(", ".join(classes), max_chars=4000)}"')
            lines.append(f"- nodes: {len(topology.nodes)}")
            lines.append(f"- interfaces: {sum(len(node.interfaces) for node in topology.nodes)}")
            lines.append(f"- links: {len(topology.links)}")
            lines.append(f"- derived_networks: {len(topology.derived_networks)}")
            lines.append(f"- manual_routes: {len(topology.manual_routes)}")
            lines.append(f"- applications: {len(topology.applications)}")
            lines.append(f"- filesystem_files: {len(topology.filesystem_files)}")
            truncated_files = sum(1 for file in topology.filesystem_files if file.truncated)
            lines.append(f"- truncated_files: {truncated_files}")
            lines.append(f"- unresolved_links: {topology.unresolved_links}")
            lines.append(f"- invalid_interfaces: {topology.invalid_interfaces}")
        elif heading == "Nodes":
            _render_nodes(lines, topology)
        elif heading == "Links":
            _render_links(lines, topology)
        elif heading == "Routing":
            _render_routing(lines, topology)
        elif heading == "DNS":
            _render_dns(lines, topology)
        elif heading == "Web":
            _render_web(lines, topology)
        else:
            lines.append("none")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_nodes(lines: list[str], topology: FiliusTopology) -> None:
    if not topology.nodes:
        lines.append("none")
        return
    for node in topology.nodes:
        lines.append(f"### {node.id}")
        lines.append(f'- source_id: "{_safe_text(node.source_id)}"')
        lines.append(f'- class: "{_safe_text(node.class_name)}"')
        lines.append(f'- type: "{_safe_text(node.device_type)}"')
        lines.append(f'- name: "{_safe_text(node.name)}"')
        lines.append(f'- label_type: "{_safe_text(node.label_type)}"')
        if not node.interfaces:
            lines.append("- interfaces: none")
            lines.append("")
            continue
        lines.append("- interfaces:")
        for interface in node.interfaces:
            lines.append(f"  - {_format_interface(interface)}")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()


def _format_interface(interface: FiliusInterface) -> str:
    fields = (
        ("id", interface.id),
        ("ip", interface.ip),
        ("netmask", interface.netmask),
        ("network", interface.network),
        ("gateway", interface.gateway),
        ("dns", interface.dns),
        ("mac", interface.mac),
        ("wireless", interface.wireless),
    )
    return "; ".join(f'{key}: "{_safe_text(value)}"' for key, value in fields)


def _render_links(lines: list[str], topology: FiliusTopology) -> None:
    if not topology.links:
        lines.append("none")
        return
    for link in topology.links:
        lines.append(f"### {link.id}")
        lines.append(f'- endpoints: "{_safe_text(link.endpoint_a)}" <-> "{_safe_text(link.endpoint_b)}"')
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()


def _render_routing(lines: list[str], topology: FiliusTopology) -> None:
    if not topology.derived_networks and not topology.manual_routes:
        lines.append("none")
        return
    if topology.derived_networks:
        lines.append("- derived_networks:")
        for network in topology.derived_networks:
            interface_list = ", ".join(network.interface_ids)
            lines.append(
                f'  - cidr: "{_safe_text(network.cidr)}"; netmask: "{_safe_text(network.netmask)}"; '
                f'interfaces: "{_safe_text(interface_list, max_chars=4000)}"'
            )
    if topology.manual_routes:
        lines.append("- manual_routes:")
        for route in topology.manual_routes:
            lines.append(f"  - {_format_manual_route(route)}")


def _format_manual_route(route: FiliusManualRoute) -> str:
    fields = (
        ("id", route.id),
        ("node", route.node_id),
        ("destination", route.destination),
        ("netmask", route.netmask),
        ("next_hop_ip", route.next_hop_ip),
        ("next_hop_node", route.next_hop_node),
        ("next_hop_interface", route.next_hop_interface),
        ("via_ip", route.via_ip),
        ("via_interface", route.via_interface),
    )
    return "; ".join(f'{key}: "{_safe_text(value)}"' for key, value in fields)


def _render_dns(lines: list[str], topology: FiliusTopology) -> None:
    dns_apps = [app for app in topology.applications if app.kind == "dns_server"]
    dns_files = [file for file in topology.filesystem_files if file.path == "/dns/hosts"]
    if not dns_apps and not dns_files:
        lines.append("none")
        return
    _render_applications(lines, dns_apps)
    _render_files(lines, dns_files)


def _render_web(lines: list[str], topology: FiliusTopology) -> None:
    web_apps = [app for app in topology.applications if app.kind == "web_server"]
    web_files = [
        file
        for file in topology.filesystem_files
        if file.path.startswith("/webserver/") or file.path == "/www.conf/vhosts"
    ]
    if not web_apps and not web_files:
        lines.append("none")
        return
    _render_applications(lines, web_apps)
    _render_files(lines, web_files)


def _render_applications(lines: list[str], applications: list[FiliusApplication]) -> None:
    if not applications:
        return
    lines.append("- applications:")
    for app in applications:
        fields = (
            ("id", app.id),
            ("node", app.node_id),
            ("class", app.class_name),
            ("name", app.name),
            ("active", app.active),
        )
        rendered_fields = "; ".join(f'{key}: "{_safe_text(value)}"' for key, value in fields)
        lines.append(f"  - {rendered_fields}")


def _render_files(lines: list[str], files: list[FiliusFilesystemFile]) -> None:
    if not files:
        return
    lines.append("- files:")
    for file in files:
        fields = (
            ("id", file.id),
            ("node", file.node_id),
            ("path", file.path),
            ("type", file.file_type),
            ("content_kind", file.content_kind),
            ("size_bytes", str(file.size_bytes)),
            ("sha256", file.sha256),
        )
        parts = [f'{key}: "{_safe_text(value)}"' for key, value in fields]
        if file.content_kind == "text":
            content = file.content
            if file.truncated:
                content = f"{content} [truncated: shown_chars={len(file.content)}]"
            parts.append(f'content: "{_safe_text(content, max_chars=5000)}"')
        lines.append("  - " + "; ".join(parts))
