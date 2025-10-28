"""
Shared web security helpers (FastAPI-agnostic utilities for routes).

Contains CSRF same-origin check logic used by both Teaching and Learning
adapters. Keeping a single implementation avoids security drift.
"""
from __future__ import annotations

from fastapi import Request


def _is_same_origin(request: Request) -> bool:
    """Verify same-origin using Origin or Referer headers.

    Behavior:
    - If Origin is present, require exact scheme/host/port match with server.
    - Else if Referer is present, validate its origin similarly.
    - Else (no headers): allow to not break non-browser clients.
    Proxy awareness: Only trust X-Forwarded-* when GUSTAV_TRUST_PROXY=true.
    """
    origin_val = request.headers.get("origin")
    try:
        from urllib.parse import urlparse
        import os

        def parse_origin(url: str) -> tuple[str, str, int]:
            p = urlparse(url)
            if not p.scheme or not p.hostname:
                raise ValueError("invalid_origin")
            scheme = p.scheme.lower()
            host = p.hostname.lower()
            port = p.port if p.port is not None else (443 if scheme == "https" else 80)
            return scheme, host, int(port)

        def parse_server(req: Request) -> tuple[str, str, int]:
            trust_proxy = (os.getenv("GUSTAV_TRUST_PROXY", "false") or "").lower() == "true"
            if trust_proxy:
                xf_proto_raw = req.headers.get("x-forwarded-proto") or req.url.scheme or ""
                xf_host_raw = req.headers.get("x-forwarded-host") or req.headers.get("host") or ""
                xf_proto = xf_proto_raw.split(",")[0].strip()
                xf_host = xf_host_raw.split(",")[0].strip()
                scheme = (xf_proto or req.url.scheme or "http").lower()
                if ":" in xf_host:
                    host_only, port_str = xf_host.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except Exception:
                        port = 443 if scheme == "https" else 80
                    host = host_only.lower()
                else:
                    host = (xf_host or (req.url.hostname or "")).lower()
                    port = int(req.url.port) if req.url.port else (443 if scheme == "https" else 80)
                xf_port_raw = req.headers.get("x-forwarded-port") or ""
                if xf_port_raw:
                    try:
                        port = int(xf_port_raw.split(",")[0].strip())
                    except Exception:
                        port = 443 if scheme == "https" else 80
                return scheme, host, port

            scheme = (request.url.scheme or "http").lower()
            host = (request.url.hostname or "").lower()
            port = int(request.url.port) if request.url.port else (443 if scheme == "https" else 80)
            return scheme, host, port

        s_scheme, s_host, s_port = parse_server(request)

        if origin_val:
            o_scheme, o_host, o_port = parse_origin(origin_val)
            return (o_scheme == s_scheme) and (o_host == s_host) and (o_port == s_port)

        referer_val = request.headers.get("referer")
        if referer_val:
            r_scheme, r_host, r_port = parse_origin(referer_val)
            return (r_scheme == s_scheme) and (r_host == s_host) and (r_port == s_port)

        return True
    except Exception:
        return False

