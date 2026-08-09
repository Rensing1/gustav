"""Validate the deliberately small offline contract for HTML simulations.

Why:
    Simulations contain executable teacher-authored code. The browser sandbox
    is the security boundary; this validator additionally catches accidental
    online dependencies and common navigation/network APIs before publishing.

Permissions:
    Pure validation. Callers must perform authorisation and storage cleanup.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_FORBIDDEN_TAGS = {"base", "embed", "frame", "iframe", "object"}
_URL_ATTRIBUTES = {"action", "data", "formaction", "href", "poster", "src"}
_SCRIPT_NETWORK_PATTERN = re.compile(
    r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|WebTransport|importScripts)\s*\(|"
    r"\b(?:navigator\s*\.\s*)?sendBeacon\s*\(|"
    r"\b(?:window\s*\.\s*)?open\s*\(|"
    r"\bimport\s*\(|"
    r"\b(?:(?:window|self|top|parent|document)\s*\.\s*)*location\s*"
    r"(?:=|\.\s*(?:href\s*=|assign\s*\(|replace\s*\())",
    re.IGNORECASE,
)
_SCRIPT_STATIC_IMPORT_PATTERN = re.compile(
    r"\b(?:import\s+(?:[^;]*?\s+from\s+)?|export\s+[^;]*?\s+from\s+)['\"]",
    re.IGNORECASE,
)
_CSS_IMPORT_PATTERN = re.compile(r"@import\b", re.IGNORECASE)
_CSS_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)


def _is_embedded_or_internal_url(raw: str) -> bool:
    value = (raw or "").strip()
    if not value or value.startswith("#"):
        return True
    lowered = value.lower()
    if lowered.startswith(("data:", "blob:")):
        return True
    return False


def _validate_css(css: str) -> None:
    if _CSS_IMPORT_PATTERN.search(css or ""):
        raise ValueError("simulation_not_self_contained")
    for match in _CSS_URL_PATTERN.finditer(css or ""):
        if not _is_embedded_or_internal_url(match.group(2)):
            raise ValueError("simulation_not_self_contained")


class _SimulationHTMLParser(HTMLParser):
    """Collect structural facts and reject resource-bearing markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_html_doctype = False
        self.has_html = False
        self.has_html_end = False
        self.has_body = False
        self.has_body_end = False
        self._html_open = False
        self._body_open = False
        self._script_depth = 0
        self._style_depth = 0

    def handle_decl(self, decl: str) -> None:
        if " ".join((decl or "").lower().split()) == "doctype html":
            self.has_html_doctype = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_tag(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"html", "body"}:
            raise ValueError("invalid_simulation_html")
        self._handle_tag(tag, attrs)
        self.handle_endtag(tag)

    def _handle_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "html":
            if self.has_html or self.has_html_end:
                raise ValueError("invalid_simulation_html")
            self.has_html = True
            self._html_open = True
        elif normalized_tag == "body":
            if not self._html_open or self.has_body or self.has_body_end:
                raise ValueError("invalid_simulation_html")
            self.has_body = True
            self._body_open = True
        if normalized_tag in _FORBIDDEN_TAGS:
            raise ValueError("simulation_not_self_contained")

        normalized_attrs = {name.lower(): value or "" for name, value in attrs}
        if normalized_tag == "meta" and normalized_attrs.get("http-equiv", "").lower() == "refresh":
            raise ValueError("simulation_not_self_contained")
        if normalized_tag == "meta" and "charset" in normalized_attrs:
            charset = normalized_attrs["charset"].strip().lower().replace("_", "-")
            if charset not in {"utf-8", "utf8"}:
                raise ValueError("invalid_simulation_html")
        if (
            normalized_tag == "meta"
            and normalized_attrs.get("http-equiv", "").strip().lower() == "content-type"
        ):
            charset_match = re.search(
                r"charset\s*=\s*([^;\s]+)", normalized_attrs.get("content", ""), re.IGNORECASE
            )
            if charset_match and charset_match.group(1).strip("'\"").lower() not in {
                "utf-8",
                "utf8",
            }:
                raise ValueError("invalid_simulation_html")
        if normalized_tag == "link":
            raise ValueError("simulation_not_self_contained")
        if normalized_tag == "script" and normalized_attrs.get("src"):
            raise ValueError("simulation_not_self_contained")

        for name, value in normalized_attrs.items():
            if name in _URL_ATTRIBUTES and not _is_embedded_or_internal_url(value):
                raise ValueError("simulation_not_self_contained")
            if name == "srcset":
                for candidate in value.split(","):
                    url = candidate.strip().split(maxsplit=1)[0] if candidate.strip() else ""
                    if not _is_embedded_or_internal_url(url):
                        raise ValueError("simulation_not_self_contained")
            if name == "style":
                _validate_css(value)

        if normalized_tag == "script":
            self._script_depth += 1
        elif normalized_tag == "style":
            self._style_depth += 1

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "html":
            if not self._html_open or self._body_open:
                raise ValueError("invalid_simulation_html")
            self._html_open = False
            self.has_html_end = True
        elif normalized_tag == "body":
            if not self._body_open:
                raise ValueError("invalid_simulation_html")
            self._body_open = False
            self.has_body_end = True
        elif normalized_tag == "script" and self._script_depth:
            self._script_depth -= 1
        elif normalized_tag == "style" and self._style_depth:
            self._style_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._script_depth:
            script = data or ""
            if _SCRIPT_NETWORK_PATTERN.search(script) or _SCRIPT_STATIC_IMPORT_PATTERN.search(
                script
            ):
                raise ValueError("simulation_not_self_contained")
        if self._style_depth:
            _validate_css(data)


def validate_simulation_html(payload: bytes) -> str:
    """Return decoded HTML when it satisfies the offline simulation contract.

    Args:
        payload: Complete uploaded object bytes, already bounded by the caller.

    Raises:
        ValueError: ``invalid_simulation_html`` for encoding/structure errors or
            ``simulation_not_self_contained`` for online/embedded dependencies.
    """

    if not isinstance(payload, bytes) or not payload:
        raise ValueError("invalid_simulation_html")
    try:
        document = payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_simulation_html") from exc
    if not document.strip():
        raise ValueError("invalid_simulation_html")

    parser = _SimulationHTMLParser()
    try:
        parser.feed(document)
        parser.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid_simulation_html") from exc
    if not (
        parser.has_html_doctype
        and parser.has_html
        and parser.has_html_end
        and parser.has_body
        and parser.has_body_end
        and not parser._html_open
        and not parser._body_open
    ):
        raise ValueError("invalid_simulation_html")
    return document


__all__ = ["validate_simulation_html"]
