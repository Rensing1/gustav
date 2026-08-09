"""Security headers for executable simulation HTML."""

from backend.web.simulation_player import build_simulation_response


def test_simulation_response_is_inline_private_and_doubly_sandboxed() -> None:
    response = build_simulation_response(b"<html><body>ok</body></html>")

    assert response.status_code == 200
    assert response.media_type == "text/html"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    csp = response.headers["content-security-policy"]
    assert "sandbox allow-scripts" in csp
    assert "connect-src 'none'" in csp
    assert "frame-src 'none'" in csp
    assert "worker-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    permissions = response.headers["permissions-policy"]
    assert "camera=()" in permissions
    assert "microphone=()" in permissions
