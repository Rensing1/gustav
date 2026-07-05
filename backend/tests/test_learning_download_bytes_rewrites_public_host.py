"""
Learning download helper — rewrite public host to internal host.

Why:
    In local dev, `SUPABASE_PUBLIC_URL` typically points at the browser-facing
    reverse proxy (e.g., https://app.localhost) which may use a local CA that
    Python inside containers does not trust. Server-side validation downloads
    must therefore prefer the internal `SUPABASE_URL` gateway when the signed
    URL uses the public host.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

learning = importlib.import_module("backend.web.routes.learning")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEARNING_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "learning.py"
DOWNLOADS_SOURCE = PROJECT_ROOT / "backend" / "web" / "routes" / "learning_downloads.py"


pytestmark = pytest.mark.anyio("asyncio")


def test_download_security_logic_lives_outside_learning_hotspot() -> None:
    downloads = importlib.import_module("backend.web.routes.learning_downloads")
    learning_source = LEARNING_SOURCE.read_text(encoding="utf-8")
    downloads_source = DOWNLOADS_SOURCE.read_text(encoding="utf-8")

    assert "def _is_private_host(" not in learning_source
    assert "def _origin(" not in learning_source
    assert "async def download_bytes_with_limit(" in downloads_source
    assert callable(downloads.download_bytes_with_limit)


@pytest.mark.anyio
async def test_download_bytes_rewrites_public_host_to_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.internal:8000")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")

    created: list[object] = []

    class _FakeResp:
        status_code = 200

        async def aiter_bytes(self):  # noqa: ANN001 - httpx-like interface
            yield b"ok"

    class _FakeStream:
        def __init__(self, client, url: str) -> None:  # noqa: ANN001 - minimal fake
            self._client = client
            self._url = url

        async def __aenter__(self):  # noqa: ANN001 - context manager protocol
            self._client.last_url = self._url
            return _FakeResp()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001 - context manager protocol
            return False

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003 - httpx compat
            created.append(self)
            self.last_url = ""

        async def __aenter__(self):  # noqa: ANN001 - context manager protocol
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001 - context manager protocol
            return False

        def stream(self, method: str, url: str, headers=None):  # noqa: ANN001 - httpx compat
            return _FakeStream(self, url)

    monkeypatch.setattr(learning.httpx, "AsyncClient", _FakeAsyncClient)

    public_url = "https://app.localhost/storage/v1/object/sign/submissions/x/y/z/file.sb3?token=abc"
    out = await learning._download_bytes_with_limit(url=public_url, max_bytes=1024, headers=None)

    assert out == b"ok"
    assert created, "expected the helper to create an httpx.AsyncClient"
    assert created[0].last_url.startswith("http://supabase.internal:8000/storage/v1/object/sign/")
    assert "token=abc" in created[0].last_url


@pytest.mark.anyio
async def test_download_bytes_rejects_non_storage_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.internal:8000")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")

    created: list[object] = []

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003 - httpx compat
            created.append(self)

    monkeypatch.setattr(learning.httpx, "AsyncClient", _FakeAsyncClient)

    invalid_url = "https://app.localhost/anything/else?token=abc"
    out = await learning._download_bytes_with_limit(url=invalid_url, max_bytes=1024, headers=None)

    assert out is None
    assert not created, "helper must fail before creating an HTTP client for non-storage paths"


@pytest.mark.anyio
async def test_download_bytes_rejects_invalid_public_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.internal:8000")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")

    created: list[object] = []

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003 - httpx compat
            created.append(self)

    monkeypatch.setattr(learning.httpx, "AsyncClient", _FakeAsyncClient)

    invalid_port_url = "https://app.localhost:8443/storage/v1/object/sign/submissions/x/y/z/file.sb3?token=abc"
    out = await learning._download_bytes_with_limit(url=invalid_port_url, max_bytes=1024, headers=None)

    assert out is None
    assert not created, "helper must fail before creating an HTTP client for invalid public host:port"


@pytest.mark.anyio
async def test_download_bytes_rejects_http_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    active_learning = importlib.import_module("backend.web.routes.learning")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.internal:8000")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "http://app.localhost")
    monkeypatch.setattr(active_learning, "_current_environment", lambda: "production")

    created: list[object] = []

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003 - httpx compat
            created.append(self)

    monkeypatch.setattr(active_learning.httpx, "AsyncClient", _FakeAsyncClient)

    http_url = "http://app.localhost/storage/v1/object/sign/submissions/x/y/z/file.sb3?token=abc"
    out = await active_learning._download_bytes_with_limit(url=http_url, max_bytes=1024, headers=None)

    assert out is None
    assert not created, "helper must fail closed for non-HTTPS validation downloads in production-like environments"


@pytest.mark.anyio
async def test_download_bytes_allows_internal_http_rewrite_in_production_for_private_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Local stacks run with `GUSTAV_ENV=prod` (local=prod) while Supabase Kong is
    typically reachable only over HTTP on a private network. Server-side
    validation downloads must still succeed when rewriting to that private HTTP
    origin.
    """
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "https://app.localhost")
    monkeypatch.setattr(learning, "_current_environment", lambda: "production")

    created: list[object] = []

    class _FakeResp:
        status_code = 200

        async def aiter_bytes(self):  # noqa: ANN001 - httpx-like interface
            yield b"ok"

    class _FakeStream:
        def __init__(self, client, url: str) -> None:  # noqa: ANN001 - minimal fake
            self._client = client
            self._url = url

        async def __aenter__(self):  # noqa: ANN001 - context manager protocol
            self._client.last_url = self._url
            return _FakeResp()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001 - context manager protocol
            return False

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003 - httpx compat
            created.append(self)
            self.last_url = ""

        async def __aenter__(self):  # noqa: ANN001 - context manager protocol
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001 - context manager protocol
            return False

        def stream(self, method: str, url: str, headers=None):  # noqa: ANN001 - httpx compat
            return _FakeStream(self, url)

    monkeypatch.setattr(learning.httpx, "AsyncClient", _FakeAsyncClient)

    public_url = "https://app.localhost/storage/v1/object/sign/submissions/x/y/z/file.hex?token=abc"
    out = await learning._download_bytes_with_limit(url=public_url, max_bytes=1024, headers=None)

    assert out == b"ok"
    assert created, "expected the helper to create an httpx.AsyncClient"
    assert created[0].last_url.startswith("http://127.0.0.1:8000/storage/v1/object/sign/")
