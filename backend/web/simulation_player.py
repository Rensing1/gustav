"""Shared hardened HTTP response for executable simulation HTML."""

from __future__ import annotations

from fastapi.responses import Response


SIMULATION_CONTENT_SECURITY_POLICY = "; ".join(
    (
        "sandbox allow-scripts",
        "default-src 'none'",
        "script-src 'unsafe-inline'",
        "style-src 'unsafe-inline'",
        "img-src data: blob:",
        "media-src data: blob:",
        "font-src data:",
        "connect-src 'none'",
        "frame-src 'none'",
        "child-src 'none'",
        "worker-src 'none'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'self'",
    )
)

SIMULATION_PERMISSIONS_POLICY = ", ".join(
    (
        "accelerometer=()",
        "autoplay=()",
        "camera=()",
        "display-capture=()",
        "fullscreen=()",
        "geolocation=()",
        "gyroscope=()",
        "microphone=()",
        "midi=()",
        "payment=()",
        "usb=()",
    )
)


def build_simulation_response(payload: bytes) -> Response:
    """Return validated HTML with a sandbox that survives direct opening."""

    return Response(
        content=payload,
        media_type="text/html",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
            "Content-Security-Policy": SIMULATION_CONTENT_SECURITY_POLICY,
            "Permissions-Policy": SIMULATION_PERMISSIONS_POLICY,
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


__all__ = [
    "SIMULATION_CONTENT_SECURITY_POLICY",
    "SIMULATION_PERMISSIONS_POLICY",
    "build_simulation_response",
]
