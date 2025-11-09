"""
Internal upload proxy — prod-parity error handling.

Goal:
    The proxy must return 502 on upstream failures in all environments
    (no soft-200 in dev/test). These tests simulate both an exception during
    the upstream PUT and a non-2xx upstream status code.
"""
from __future__ import annotations

import importlib

import httpx
import pytest
from httpx import ASGITransport
import asyncio


pytestmark = pytest.mark.anyio("asyncio")


async def _client():
    import main  # noqa
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_upload_proxy_raises_502_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    # Enable proxy and set SUPABASE_URL host validation
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")

    # Reload modules to pick up env
    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:  # type: ignore[attr-defined]
        import backend.web.routes.learning as learning_backend  # type: ignore
    except ImportError:  # pragma: no cover - alias may not exist outside app package
        learning_backend = None  # type: ignore
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-err", name="S", roles=["student"])  # type: ignore

    # Monkeypatch async forwarder to raise
    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("upstream down")

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)



@pytest.mark.anyio
async def test_upload_proxy_raises_502_on_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:  # type: ignore[attr-defined]
        import backend.web.routes.learning as learning_backend  # type: ignore
    except ImportError:  # pragma: no cover
        learning_backend = None  # type: ignore
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-500", name="S", roles=["student"])  # type: ignore

    class _Resp:
        status_code = 500

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)


@pytest.mark.anyio
async def test_upload_proxy_awaits_async_forwarder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:  # type: ignore[attr-defined]
        import backend.web.routes.learning as learning_backend  # type: ignore
    except ImportError:  # pragma: no cover
        learning_backend = None  # type: ignore
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-await", name="S", roles=["student"])  # type: ignore

    invoked = asyncio.Event()

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0)
        invoked.set()
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": "http://supabase.local:54321/storage/v1/object/test"},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 200
    assert invoked.is_set()


@pytest.mark.anyio
async def test_upload_proxy_handles_parallel_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    try:  # type: ignore[attr-defined]
        import backend.web.routes.learning as learning_backend  # type: ignore
    except ImportError:  # pragma: no cover
        learning_backend = None  # type: ignore
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-parallel", name="S", roles=["student"])  # type: ignore

    in_flight = 0
    peak = 0

    class _Resp:
        status_code = 200

    async def fake_forward(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return _Resp()

    monkeypatch.setattr(learning, "_async_forward_upload", fake_forward)
    if learning_backend is not None:
        monkeypatch.setattr(learning_backend, "_async_forward_upload", fake_forward)

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)

        async def _upload(payload: bytes):
            return await c.put(
                "/api/learning/internal/upload-proxy",
                params={"url": "http://supabase.local:54321/storage/v1/object/test"},
                content=payload,
                headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
            )

        r1, r2 = await asyncio.gather(_upload(b"a" * 3), _upload(b"b" * 4))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert peak >= 2, "Expected overlapping async forwards"
