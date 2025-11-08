"""
App wiring — Supabase storage adapter injection

Why:
    In production, uploads rely on a concrete storage adapter. This test
    verifies that, when Supabase env vars are present and a `supabase`
    client is importable, the FastAPI app wires a non-null storage adapter
    into the Learning router at import/startup time.

Notes:
    - We inject a minimal fake `supabase` module into `sys.modules` so the
      app can import and instantiate `SupabaseStorageAdapter` without the
      real dependency.
    - We assert adapter type only (not performing an actual presign call),
      keeping the test fast and deterministic.
"""
from __future__ import annotations

import os
import sys
import types
import importlib

import pytest


def _install_fake_supabase_module() -> None:
    """Provide a minimal fake `supabase` module with `create_client`.

    The returned client exposes `.storage.from_(bucket)` with methods used by
    our adapter. This keeps the wiring path testable without the real lib.
    """

    class _FakeBucket:
        def create_signed_upload_url(self, key: str):
            return {"url": f"https://fake.storage.local/{key}?signature=xyz"}

        def create_signed_url(self, key: str, expires_in: int, options=None):
            return {"url": f"https://fake.storage.local/{key}?download=1"}

        def stat(self, key: str):
            return {"size": 0, "mimetype": "application/octet-stream"}

        def remove(self, paths: list[str]):
            return None

    class _FakeStorage:
        def from_(self, bucket: str):
            return _FakeBucket()

    class _FakeClient:
        def __init__(self) -> None:
            self.storage = _FakeStorage()

    def create_client(url: str, key: str):  # noqa: D401 - simple factory
        return _FakeClient()

    mod = types.SimpleNamespace(create_client=create_client)
    sys.modules["supabase"] = mod  # type: ignore[assignment]


@pytest.mark.anyio
async def test_learning_storage_adapter_wired_on_startup(monkeypatch):
    # Ensure fresh imports for wiring logic
    for name in list(sys.modules.keys()):
        if name in {"main", "routes.learning", "backend.web.routes.learning"}:
            del sys.modules[name]

    # Provide env vars that enable Supabase wiring in the app
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

    # Inject fake supabase module
    _install_fake_supabase_module()

    # Import the app module (triggers startup wiring code)
    import main  # noqa: F401  # type: ignore

    # After import, learning router must have a non-null storage adapter
    import routes.learning as learning  # type: ignore
    from teaching.storage import NullStorageAdapter  # type: ignore

    assert not isinstance(learning.STORAGE_ADAPTER, NullStorageAdapter)

