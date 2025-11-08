"""
Internal upload proxy — prod-parity error handling.

Goal:
    The proxy must return 502 on upstream failures in all environments
    (no soft-200 in dev/test). These tests simulate both an exception during
    the upstream PUT and a non-2xx upstream status code.
"""
from __future__ import annotations

import importlib
import types

import httpx
import pytest
from httpx import ASGITransport


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
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-err", name="S", roles=["student"])  # type: ignore

    # Monkeypatch the requests.put used by the proxy to raise
    def fake_put(url: str, data: bytes, headers: dict[str, str]):  # noqa: ARG001
        raise RuntimeError("upstream down")

    monkeypatch.setattr(learning, "requests", types.SimpleNamespace(put=fake_put))

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": "http://supabase.local:54321/storage/v1/object/test"},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 502
    j = r.json()
    assert j.get("error") == "bad_gateway"


@pytest.mark.anyio
async def test_upload_proxy_raises_502_on_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "true")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")

    if "routes.learning" in importlib.sys.modules:
        importlib.reload(importlib.import_module("routes.learning"))

    import main  # noqa
    import routes.learning as learning  # noqa
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub="s-proxy-500", name="S", roles=["student"])  # type: ignore

    class _Resp:
        status_code = 500

    def fake_put(url: str, data: bytes, headers: dict[str, str]):  # noqa: ARG001
        return _Resp()

    monkeypatch.setattr(learning, "requests", types.SimpleNamespace(put=fake_put))

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(
            "/api/learning/internal/upload-proxy",
            params={"url": "http://supabase.local:54321/storage/v1/object/test"},
            content=b"abc",
            headers={"Origin": "http://test", "Content-Type": "application/octet-stream"},
        )
    assert r.status_code == 502
    j = r.json()
    assert j.get("error") == "bad_gateway"

