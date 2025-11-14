"""
Learning internal upload-proxy — host/path/MIME validation.

Asserts the proxy rejects wrong hosts, invalid paths, and disallowed MIME types
before attempting to forward.
"""
from __future__ import annotations

import importlib
import httpx
import pytest
from httpx import ASGITransport
from starlette.requests import Request as StarletteRequest


pytestmark = pytest.mark.anyio("asyncio")


async def _client():
    import main  # noqa
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_proxy_rejects_wrong_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    # Reload to pick env
    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-host", name="S", roles=["student"])  # type: ignore

    # Ensure forwarding would fail if called (should not be called)
    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when host invalid")

    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-path", name="S", roles=["student"])  # type: ignore

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when path invalid")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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
async def test_proxy_rejects_disallowed_mime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-mime", name="S", roles=["student"])  # type: ignore

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when MIME invalid")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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
async def test_proxy_rejects_port_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.local:54321")

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-port", name="S", roles=["student"])  # type: ignore

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("forward must not be called when port mismatched")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-public", name="S", roles=["student"])  # type: ignore

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-docker", name="S", roles=["student"])  # type: ignore

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-doubleslash", name="S", roles=["student"])  # type: ignore

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:
        import backend.web.routes.learning as learning_backend  # type: ignore
    except Exception:
        learning_backend = None
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-stream", name="S", roles=["student"])  # type: ignore

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

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
