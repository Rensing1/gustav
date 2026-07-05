"""Download helpers for Learning storage files.

Why:
    Learning routes need to fetch presigned storage URLs for validation and file
    delivery. The SSRF guard, public-to-internal Supabase rewrite, and byte
    limit are security-sensitive helper logic, so they live outside the route
    hotspot and can be tested directly.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

import httpx


def _is_private_host(host: str) -> bool:
    """Return True when a host resolves only to loopback/private IPs."""

    h = (host or "").strip().lower()
    if not h:
        return False
    if h.endswith(".internal"):
        return True
    if h in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}:
        return True
    try:
        ip = ipaddress.ip_address(h)
        return bool(ip.is_loopback or ip.is_private)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(h, None)
    except OSError:
        return False
    if not infos:
        return False
    for _family, _socktype, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0] if isinstance(sockaddr, (tuple, list)) and sockaddr else ""
        try:
            ip = ipaddress.ip_address(str(ip_str))
        except ValueError:
            return False
        if not (ip.is_loopback or ip.is_private):
            return False
    return True


def _origin(raw: str) -> tuple[str, str, int] | None:
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        return None
    port = parsed.port or (443 if scheme == "https" else 80)
    return (scheme, host, int(port))


async def download_bytes_with_limit(
    *,
    url: str,
    max_bytes: int,
    headers: dict[str, str] | None = None,
    environment: str,
) -> bytes | None:
    """Download bytes from a presigned storage URL with SSRF guards and a hard cap."""

    if not url:
        return None
    try:
        env = (environment or "").strip().lower()
        allow_insecure_env = env in {"dev", "development", "test", "testing", "local"}
        supabase_base = (os.getenv("SUPABASE_URL") or "").strip()
        public_base = (os.getenv("SUPABASE_PUBLIC_URL") or "").strip()

        sup_origin = _origin(supabase_base)
        pub_origin = _origin(public_base)
        pub_host = pub_origin[1] if pub_origin else ""
        target = urlparse(url)
        if (target.scheme or "").lower() not in {"http", "https"}:
            return None
        tgt_scheme = (target.scheme or "").lower()
        if (not allow_insecure_env) and tgt_scheme != "https":
            return None
        tgt_host = (target.hostname or "").lower()
        tgt_port = target.port or (443 if tgt_scheme == "https" else 80)
        allowed_origins = {o for o in (sup_origin, pub_origin) if o is not None}
        if not allowed_origins or ((tgt_scheme, tgt_host, int(tgt_port)) not in allowed_origins):
            return None
        path = target.path or "/"
        while "//" in path:
            path = path.replace("//", "/")
        if ".." in path or re.search(r"%2e", path, flags=re.IGNORECASE):
            return None
        if not path.startswith("/storage/v1/object/"):
            return None
        # Prefer the internal gateway for server-side downloads to avoid TLS
        # trust issues against the browser-facing host, while preserving the
        # signed path and query.
        if pub_origin and sup_origin and tgt_host == pub_host and supabase_base:
            try:
                internal = urlparse(supabase_base)
                if internal.scheme and internal.netloc:
                    internal_scheme = (internal.scheme or "").lower()
                    internal_host = (internal.hostname or "").lower()
                    allow_http_internal = (internal_scheme == "http") and _is_private_host(internal_host)
                    if internal_scheme == "https" or allow_insecure_env or allow_http_internal:
                        url = target._replace(scheme=internal.scheme, netloc=internal.netloc).geturl()
            except Exception:
                pass
        effective = urlparse(url)
        eff_scheme = (effective.scheme or "").lower()
        if (not allow_insecure_env) and eff_scheme != "https":
            eff_host = (effective.hostname or "").lower()
            eff_port = effective.port or (443 if eff_scheme == "https" else 80)
            if not (
                sup_origin
                and (eff_scheme, eff_host, int(eff_port)) == sup_origin
                and _is_private_host(eff_host)
            ):
                return None
    except Exception:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                code = int(getattr(resp, "status_code", 500))
                if 300 <= code < 400:
                    return None
                if code >= 400:
                    return None
                out = bytearray()
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    out.extend(chunk)
                    if len(out) > int(max_bytes):
                        return None
                return bytes(out)
    except Exception:
        return None
