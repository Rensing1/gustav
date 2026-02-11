"""
Public repository safety contract.

This repository is intended to be publishable as open source.
Therefore we enforce a small set of "fail fast" hygiene rules that prevent
accidental commits of:
  - PII in tickets (email addresses, prod UUIDs, internal/private IPs)
  - Production domain leakage in docs/config exports
  - Private key PEM blocks in the repository
  - Ops/provider-specific deployment snippets in the public dev config
  - References to docs/scripts that are intentionally not shipped publicly

The goal is not perfect DLP. The goal is a clear, deterministic guardrail that
blocks obvious leaks and keeps the public surface OSS-friendly.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PUBLIC_TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".yml",
    ".yaml",
    ".json",
    ".ftl",
    ".properties",
    ".txt",
}


def _iter_ticket_files() -> list[Path]:
    tickets_dir = REPO_ROOT / "docs" / "tickets"
    if not tickets_dir.is_dir():
        return []
    return sorted(p for p in tickets_dir.glob("*.md") if p.is_file())


def _find_private_ipv4(text: str) -> list[str]:
    hits: list[str] = []
    for raw in _IPV4_RE.findall(text):
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if isinstance(ip, ipaddress.IPv4Address) and ip.is_private:
            hits.append(raw)
    return hits


def _iter_public_text_files() -> list[Path]:
    """Iterate over the repo's public text surface (avoid scanning .venv/large artifacts)."""
    roots = [
        REPO_ROOT / "docs",
        REPO_ROOT / "keycloak",
        REPO_ROOT / "backend",
        REPO_ROOT / "docker-compose.yml",
        REPO_ROOT / "reverse-proxy" / "Caddyfile",
        REPO_ROOT / "Makefile",
        REPO_ROOT / ".env.example",
    ]
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            paths.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in _PUBLIC_TEXT_SUFFIXES:
                continue
            paths.append(path)
    # stable order makes failures deterministic
    return sorted(set(paths))


def test_tickets_contain_no_emails_uuids_or_private_ips() -> None:
    """Tickets must not contain PII or prod identifiers."""
    offenders: list[str] = []
    for path in _iter_ticket_files():
        text = path.read_text(encoding="utf-8")
        emails = sorted(set(_EMAIL_RE.findall(text)))
        uuids = sorted(set(_UUID_RE.findall(text)))
        private_ips = sorted(set(_find_private_ipv4(text)))
        if emails or uuids or private_ips:
            offenders.append(
                f"{path.relative_to(REPO_ROOT)}: emails={emails[:3]} uuids={uuids[:3]} private_ips={private_ips[:3]}"
            )
    assert not offenders, "Tickets must be PII-free.\n" + "\n".join(offenders)


def test_public_dev_config_contains_no_provider_ddns_or_lets_encrypt_snippets() -> None:
    """Public dev config must not embed prod/provider-specific deployment helpers."""
    paths = [
        REPO_ROOT / "docker-compose.yml",
        REPO_ROOT / "reverse-proxy" / "Caddyfile",
    ]
    forbidden_substrings = [
        "IONOS",
        "ipinfo.io",
        "ddns",
        "LETSENCRYPT_EMAIL",
        "DOMAIN_NAME",
    ]
    offenders: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_substrings:
            if needle in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} contains {needle!r}")
    assert not offenders, "Public dev config must not contain ops/provider snippets.\n" + "\n".join(offenders)


def test_public_docs_do_not_reference_removed_runbooks_or_scripts() -> None:
    """Top-level docs should not link to files that are intentionally not shipped publicly."""
    paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "ARCHITECTURE.md",
        REPO_ROOT / "Makefile",
    ]
    forbidden_substrings = [
        "docs/runbooks/",
        "scripts/",
    ]
    offenders: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_substrings:
            if needle in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} references {needle!r}")
    assert not offenders, "Public docs must not reference non-public runbooks/scripts.\n" + "\n".join(offenders)


def test_public_repo_contains_no_production_domain() -> None:
    """Public repo must not hardcode a real production domain.

    We allow example domains (e.g. *.example) and local hosts (*.localhost).
    """
    forbidden_substrings = [
        "gustav-lernplattform.de",
    ]
    offenders: list[str] = []
    for path in _iter_public_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_substrings:
            if needle in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} contains {needle!r}")
    assert not offenders, "Public repo must not contain production domains.\n" + "\n".join(offenders)


def test_public_repo_contains_no_private_key_pem_blocks() -> None:
    """Public repo must not contain private key PEM blocks.

    Even test keys trigger secret scanners and are too easy to confuse with real credentials.
    """
    forbidden_substrings = [
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "BEGIN OPENSSH PRIVATE KEY",
    ]
    offenders: list[str] = []
    for path in _iter_public_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_substrings:
            if needle in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} contains {needle!r}")
    assert not offenders, "Public repo must not contain private key PEM blocks.\n" + "\n".join(offenders)
