"""
Learning internal upload-proxy — host/path/MIME validation.

Asserts the proxy rejects wrong hosts, invalid paths, and disallowed MIME types
before attempting to forward.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import httpx
import pytest
from httpx import ASGITransport
from starlette.requests import Request as StarletteRequest

from backend.tests.runtime_auth_helpers import install_session_store


pytestmark = pytest.mark.anyio("asyncio")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEARNING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "learning.py"
UPLOAD_PROXY_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "learning_upload_proxy.py"


async def _client():
    main = importlib.import_module("backend.web.main")
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


def _main():
    return importlib.import_module("backend.web.main")


def _reload_learning_route():
    module_name = "backend.web.routes.learning"
    if module_name in importlib.sys.modules:
        return importlib.reload(importlib.import_module(module_name))
    return importlib.import_module(module_name)


def _student_session(monkeypatch: pytest.MonkeyPatch, main_module, sub: str):
    store = install_session_store(monkeypatch, main_module)
    return store.create(sub=sub, name="S", roles=["student"])


def test_upload_proxy_helpers_live_outside_learning_hotspot() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    upload_proxy = importlib.import_module("backend.web.routes.learning_upload_proxy")
    learning_source = LEARNING_SOURCE.read_text(encoding="utf-8")
    upload_proxy_source = UPLOAD_PROXY_SOURCE.read_text(encoding="utf-8")

    assert "def _encode_proxy_headers(" not in learning_source
    assert "def _decode_proxy_headers(" not in learning_source
    assert "def _filter_upload_proxy_headers(" not in learning_source
    assert "def _normalized_parts(" not in learning_source
    assert "def encode_proxy_headers(" in upload_proxy_source
    assert "def decode_proxy_headers(" in upload_proxy_source
    assert "def filter_upload_proxy_headers(" in upload_proxy_source
    assert "def normalized_parts(" in upload_proxy_source
    assert learning._encode_proxy_headers is upload_proxy.encode_proxy_headers
    assert learning._decode_proxy_headers is upload_proxy.decode_proxy_headers
    assert learning._filter_upload_proxy_headers is upload_proxy.filter_upload_proxy_headers
    assert learning._normalized_parts is upload_proxy.normalized_parts


@pytest.mark.anyio
async def test_proxy_rejects_wrong_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    # Reload to pick env
    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-host")

    # Ensure forwarding would fail if called (should not be called)
    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when host invalid")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    bad = "https://evil.example.com/storage/v1/object/upload/x"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": bad},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_url_host"


@pytest.mark.anyio
async def test_proxy_rejects_invalid_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-path")

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when path invalid")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    # Path does not begin with expected storage upload prefix
    bad = "https://supabase.local:54321/storage/v1/other"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": bad},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_url"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "bad_path",
    [
        "/storage/v1/object/../auth/v1/token",
        "/storage/v1/object/%2e%2e/auth/v1/token",
        "/storage/v1/object/%2E%2E/auth/v1/token",
    ],
)
async def test_proxy_rejects_path_traversal(monkeypatch: pytest.MonkeyPatch, bad_path: str) -> None:
    """Reject dot-segments and encoded traversal to keep SSRF surface narrow."""

    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-traversal")

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when path contains traversal")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    bad = f"https://supabase.local:54321{bad_path}"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": bad},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_url"


@pytest.mark.anyio
async def test_proxy_rejects_disallowed_mime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-mime")

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when MIME invalid")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    good = "https://supabase.local:54321/storage/v1/object/upload/submissions/file"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": good},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "text/plain"},
        )
    assert r.status_code == 400
    assert r.json().get("detail") == "mime_not_allowed"


@pytest.mark.anyio
async def test_proxy_filters_forward_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forward only an allowlist of safe presign headers (no auth/cookie/host)."""

    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-headers")

    captured: dict[str, object] = {}

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    token = learning._encode_proxy_headers(  # type: ignore[attr-defined]
        {
            "Authorization": "Bearer secret",
            "Cookie": "x=y",
            "Host": "evil.example.com",
            "x-upsert": "true",
            "Content-Type": "application/octet-stream",
        },
    )

    good = "https://supabase.local:54321/storage/v1/object/upload/submissions/file"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": good, "headers": token},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 200

    forwarded = dict(captured.get("headers") or {})
    assert forwarded.get("x-upsert") == "true"
    assert forwarded.get("Content-Type") == "application/octet-stream"
    assert "Authorization" not in forwarded
    assert "Cookie" not in forwarded
    assert "Host" not in forwarded


@pytest.mark.anyio
async def test_proxy_rejects_port_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-port")

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when port mismatched")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    bad = "https://supabase.local:65432/storage/v1/object/upload/submissions/file"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": bad},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 400
    assert r.json().get("detail") == "invalid_url_host"


@pytest.mark.anyio
async def test_proxy_allows_supabase_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """SUPABASE_PUBLIC_URL host should be whitelisted for rewritten upload URLs."""

    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.internal:54321")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-public")

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    good = "https://app.localhost/storage/v1/object/upload/submissions/file"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": good},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_proxy_allows_host_docker_internal_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local http with host.docker.internal should be treated as local dev host."""
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://host.docker.internal:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-docker")

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    good = "http://host.docker.internal:54321/storage/v1/object/upload/submissions/file"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": good},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/pdf"},
        )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_proxy_allows_double_slash_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proxy should accept presigned URLs that contain accidental double slashes.

    Some presigners can emit /storage/v1//object/...; we normalize before checks.
    """
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://host.docker.internal:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-doubleslash")

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    # Note the double slash after /storage/v1/
    good = "http://host.docker.internal:54321/storage/v1//object/upload/submissions/file"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": good},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/pdf"},
        )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_proxy_streams_request_body_without_calling_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the proxy reads the incoming body via stream, not Request.body()."""

    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://host.docker.internal:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-stream")

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)

    async def _fail_body(self):  # type: ignore[no-untyped-def]
        raise AssertionError("Request.body() usage is forbidden for streaming proxy")

    monkeypatch.setattr(StarletteRequest, "body", _fail_body, raising=False)

    good = "http://host.docker.internal:54321/storage/v1/object/upload/submissions/file"
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": good},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_proxy_emits_telemetry_for_successful_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Upload proxy should emit structured telemetry without exposing payload contents."""

    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    main = _main()
    learning = _reload_learning_route()

    student = _student_session(monkeypatch, main, "s-proxy-telemetry")

    class _Resp:
        status_code = 200

    async def fake_forward(**_kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    telemetry_events: list[dict] = []

    def fake_emit(**kwargs):  # type: ignore[no-untyped-def]
        telemetry_events.append(dict(kwargs))

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    monkeypatch.setattr(learning, "_emit_upload_proxy_telemetry", fake_emit, raising=False)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": "https://supabase.local:54321/storage/v1/object/upload/submissions/file"},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 200
    assert telemetry_events, "expected upload proxy telemetry event"
    assert telemetry_events[-1].get("outcome") == "success"
