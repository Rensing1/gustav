"""
Filius topology extraction.

Why:
    Filius stores projects as Java XMLDecoder documents. The feedback pipeline
    needs network facts from that XML, but must never deserialize Java objects.
    This module reads only passive XML fields and returns a small structured
    model for the Markdown renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import html
import ipaddress
import re
import xml.etree.ElementTree as ET


@dataclass(frozen=True, slots=True)
class FiliusInterface:
    """A network interface extracted from a Filius node."""

    id: str
    ip: str
    netmask: str
    network: str
    gateway: str
    dns: str
    mac: str
    wireless: str = "unknown"


@dataclass(frozen=True, slots=True)
class FiliusNode:
    """A Filius GUI node with its hardware type and interfaces."""

    id: str
    source_id: str
    class_name: str
    device_type: str
    name: str
    label_type: str
    interfaces: tuple[FiliusInterface, ...]


@dataclass(frozen=True, slots=True)
class FiliusLink:
    """A cable between two resolved Filius nodes."""

    id: str
    source_id: str
    endpoint_a: str
    endpoint_b: str


@dataclass(frozen=True, slots=True)
class FiliusDerivedNetwork:
    """A network derived from interface IP and subnet mask."""

    cidr: str
    netmask: str
    interface_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FiliusTopology:
    """Structured topology facts used by the evidence renderer."""

    nodes: tuple[FiliusNode, ...]
    links: tuple[FiliusLink, ...]
    derived_networks: tuple[FiliusDerivedNetwork, ...]
    unresolved_links: int = 0
    invalid_interfaces: int = 0


@dataclass(slots=True)
class _TooltipInterface:
    ip: str = "unknown"
    netmask: str = "unknown"
    gateway: str = "unknown"
    dns: str = "unknown"
    mac: str = "unknown"


_TOOLTIP_INTERFACE_RE = re.compile(
    r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s*/\s*"
    r"(?P<netmask>\d{1,3}(?:\.\d{1,3}){3})\s*"
    r"\((?P<mac>[0-9A-Fa-f:]{17})\)"
)
_GATEWAY_RE = re.compile(r"Gateway:[^\S\n]*(?P<value>[^\n<]*)")
_DNS_RE = re.compile(r"DNS-Server:[^\S\n]*(?P<value>[^\n<]*)")


def extract_topology(xml_bytes: bytes) -> FiliusTopology:
    """Extract network topology facts from validated Filius XML bytes."""
    root = ET.fromstring(xml_bytes)
    node_objects = [obj for obj in root.iter("object") if obj.attrib.get("class") == "filius.gui.netzwerksicht.GUIKnotenItem"]

    nodes: list[FiliusNode] = []
    source_to_node_id: dict[str, str] = {}
    invalid_interfaces = 0
    networks: dict[tuple[str, str], list[str]] = {}

    for node_index, node_object in enumerate(node_objects, start=1):
        node_id = f"n{node_index}"
        source_id = node_object.attrib.get("id") or f"unknown-node-{node_index}"
        source_to_node_id[source_id] = node_id

        label = _find_direct_property_object(node_object, "imageLabel")
        name = _property_text(label, "text") or "unknown"
        label_type = _property_text(label, "typ") or "unknown"
        tooltip = _property_text(label, "toolTipText") or ""

        hardware = _find_direct_property_object(node_object, "knoten")
        class_name = hardware.attrib.get("class") if hardware is not None else "unknown"
        device_type = _device_type(class_name or label_type)
        tooltip_interfaces = _parse_tooltip_interfaces(tooltip)

        interfaces: list[FiliusInterface] = []
        if hardware is not None:
            for interface_index, interface_object in enumerate(_interface_objects(hardware), start=1):
                tooltip_info = _match_tooltip_interface(interface_object, tooltip_interfaces)
                iface, valid_network = _build_interface(
                    node_id=node_id,
                    interface_index=interface_index,
                    interface_object=interface_object,
                    fallback=tooltip_info,
                )
                interfaces.append(iface)
                if valid_network:
                    networks.setdefault((iface.network, iface.netmask), []).append(iface.id)
                elif iface.ip != "unknown" or iface.netmask != "unknown":
                    invalid_interfaces += 1

        nodes.append(
            FiliusNode(
                id=node_id,
                source_id=source_id,
                class_name=class_name or "unknown",
                device_type=device_type,
                name=name,
                label_type=label_type,
                interfaces=tuple(interfaces),
            )
        )

    links: list[FiliusLink] = []
    unresolved_links = 0
    link_objects = [obj for obj in root.iter("object") if obj.attrib.get("class") == "filius.gui.netzwerksicht.GUIKabelItem"]
    for link_index, link_object in enumerate(link_objects, start=1):
        endpoint_refs = _link_endpoint_refs(link_object)
        if len(endpoint_refs) < 2:
            unresolved_links += 1
            continue
        endpoint_a = source_to_node_id.get(endpoint_refs[0])
        endpoint_b = source_to_node_id.get(endpoint_refs[1])
        if not endpoint_a or not endpoint_b:
            unresolved_links += 1
            continue
        links.append(
            FiliusLink(
                id=f"e{len(links) + 1}",
                source_id=link_object.attrib.get("id") or f"unknown-link-{link_index}",
                endpoint_a=endpoint_a,
                endpoint_b=endpoint_b,
            )
        )

    derived_networks = tuple(
        FiliusDerivedNetwork(cidr=cidr, netmask=netmask, interface_ids=tuple(interface_ids))
        for (cidr, netmask), interface_ids in sorted(networks.items(), key=lambda item: item[0][0])
    )

    return FiliusTopology(
        nodes=tuple(nodes),
        links=tuple(links),
        derived_networks=derived_networks,
        unresolved_links=unresolved_links,
        invalid_interfaces=invalid_interfaces,
    )


def _find_direct_property_object(element: ET.Element | None, property_name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in element.findall("./void"):
        if child.attrib.get("property") != property_name:
            continue
        obj = child.find("./object")
        if obj is not None:
            return obj
    return None


def _property_text(element: ET.Element | None, property_name: str) -> str | None:
    if element is None:
        return None
    for child in element.findall("./void"):
        if child.attrib.get("property") != property_name:
            continue
        value = next(iter(child), None)
        if value is not None and value.tag in {"string", "int", "boolean"}:
            return (value.text or "").strip()
    return None


def _interface_objects(hardware: ET.Element) -> list[ET.Element]:
    for child in hardware.findall("./void"):
        if child.attrib.get("property") == "netzwerkInterfaces":
            return child.findall("./void")
    return []


def _parse_tooltip_interfaces(tooltip: str) -> list[_TooltipInterface]:
    text = html.unescape(tooltip or "")
    gateway = _normalize_optional(_first_match(_GATEWAY_RE, text))
    dns = _normalize_optional(_first_match(_DNS_RE, text))
    return [
        _TooltipInterface(
            ip=match.group("ip"),
            netmask=match.group("netmask"),
            gateway=gateway,
            dns=dns,
            mac=match.group("mac").upper(),
        )
        for match in _TOOLTIP_INTERFACE_RE.finditer(text)
    ]


def _match_tooltip_interface(interface_object: ET.Element, fallbacks: list[_TooltipInterface]) -> _TooltipInterface:
    if not fallbacks:
        return _TooltipInterface()
    mac = (_property_text(interface_object, "mac") or "").upper()
    if mac:
        for fallback in fallbacks:
            if fallback.mac.upper() == mac:
                return fallback
    return fallbacks[0]


def _build_interface(
    *,
    node_id: str,
    interface_index: int,
    interface_object: ET.Element,
    fallback: _TooltipInterface,
) -> tuple[FiliusInterface, bool]:
    ip = _normalize_optional(_property_text(interface_object, "ip")) if _property_text(interface_object, "ip") else fallback.ip
    netmask = fallback.netmask
    gateway = fallback.gateway
    dns = fallback.dns
    mac = _normalize_optional(_property_text(interface_object, "mac")) if _property_text(interface_object, "mac") else fallback.mac
    cidr, valid_network = _derive_network(ip, netmask)
    return (
        FiliusInterface(
            id=f"{node_id}-if{interface_index}",
            ip=ip,
            netmask=netmask,
            network=cidr,
            gateway=gateway,
            dns=dns,
            mac=mac.upper() if mac != "unknown" else mac,
        ),
        valid_network,
    )


def _derive_network(ip: str, netmask: str) -> tuple[str, bool]:
    if ip == "unknown" or netmask == "unknown":
        return "unknown", False
    try:
        network = ipaddress.IPv4Network((ip, netmask), strict=False)
    except Exception:
        return "unknown", False
    return str(network), True


def _link_endpoint_refs(link_object: ET.Element) -> list[str]:
    refs: list[str] = []
    for child in link_object.iter("void"):
        if child.attrib.get("property") not in {"ziel1", "ziel2"}:
            continue
        obj = child.find("./object")
        ref = obj.attrib.get("idref") if obj is not None else None
        if ref:
            refs.append(ref)
    return refs


def _device_type(class_or_label: str) -> str:
    text = (class_or_label or "").casefold()
    if "notebook" in text:
        return "notebook"
    if "switch" in text:
        return "switch"
    if "vermittlungsrechner" in text or "router" in text:
        return "router"
    if "rechner" in text:
        return "computer"
    if "modem" in text:
        return "modem"
    return "unknown"


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group("value") if match else ""


def _normalize_optional(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else "unknown"
