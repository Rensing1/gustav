"""
Shared helper for wiring Supabase-backed storage adapters.

Why:
    App startup may occur before Supabase is reachable locally, leaving the
    storage adapter unset and breaking upload-intents. This module provides an
    idempotent helper that can be used both at startup and lazily on-demand
    from API routes to (re)attempt wiring when configuration is present.

Security:
    Requires SUPABASE_SERVICE_ROLE_KEY and SUPABASE_URL environment variables.
    The helper only wires server-side adapters; no secrets are exposed to clients.
"""
from __future__ import annotations

import logging
import os


_STARTUP_ATTEMPTED = False


def wire_supabase_adapter_if_configured() -> bool:
    """Attempt to wire Supabase storage adapters for Teaching and Learning.

    Behavior:
        - Returns True when wiring succeeds (adapters injected).
        - Returns False when not configured or any error occurs (keeps Null).
        - Safe and idempotent to call multiple times.

    Logging:
        - On success, logs an info message.
        - On failure, logs a warning including exception class and message.
    """
    logger = logging.getLogger("gustav.web")
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        return False

    global _STARTUP_ATTEMPTED
    try:
        # Lazy imports keep optional dependency out of non-storage paths.
        from teaching.storage_supabase import SupabaseStorageAdapter  # type: ignore
        from routes import teaching as _teaching  # type: ignore
        from routes import learning as _learning  # type: ignore

        adapter = None
        # Preferred: use official client when key is a JWT (remote/prod)
        try:
            from supabase import create_client  # type: ignore
            try:
                client = create_client(url, key)
                adapter = SupabaseStorageAdapter(client)
            except Exception as exc:
                # On first (startup) attempt, prefer lazy rewire – except when
                # explicitly running local E2E against a reachable dev instance.
                if not _STARTUP_ATTEMPTED:
                    try:
                        from urllib.parse import urlparse as _urlparse
                        host = (_urlparse(url).hostname or "").lower()
                    except Exception:
                        host = ""
                    is_local = host in {"127.0.0.1", "localhost"}
                    e2e = (os.getenv("RUN_SUPABASE_E2E", "0") == "1")
                    if not (is_local and e2e):
                        logger.warning("Supabase client unavailable at startup: %s: %s", exc.__class__.__name__, str(exc))
                        _STARTUP_ATTEMPTED = True
                        return False
                # Subsequent calls (lazy path): fall back to storage3 when the supabase client rejects non‑JWT dev keys
                logger.warning("Supabase client unavailable: %s: %s — falling back to storage3", exc.__class__.__name__, str(exc))
        except Exception:
            # No supabase package; rely on storage3 fallback below
            pass

        if adapter is None:
            # Fallback: wire a storage3 client directly using the service key.
            # This path is compatible with local `supabase start` where keys are not JWTs.
            try:
                from storage3._sync.client import SyncStorageClient  # type: ignore
            except Exception as exc:  # pragma: no cover - defensive path
                logger.warning("storage3 client import failed: %s: %s", exc.__class__.__name__, str(exc))
                return False
            # Only use the fallback for obviously local hosts unless explicitly allowed.
            try:
                from urllib.parse import urlparse as _urlparse
                host = (_urlparse(url).hostname or "").lower()
            except Exception:
                host = ""
            force = (os.getenv("SUPABASE_FALLBACK_STORAGE3", "false").lower() == "true")
            is_local = host in {"127.0.0.1", "localhost"}
            if not force and not is_local:
                return False
            storage_url = f"{url.rstrip('/')}/storage/v1"
            headers = {"Authorization": f"Bearer {key}", "apikey": key}
            storage_client = SyncStorageClient(storage_url, headers)  # type: ignore[arg-type]
            adapter = SupabaseStorageAdapter(storage_client)

        _teaching.set_storage_adapter(adapter)
        _learning.set_storage_adapter(adapter)
        logger.info("Storage adapter wired: Supabase")
        _STARTUP_ATTEMPTED = True
        
        # Dev convenience: ensure buckets requested by env exist when helper is called.
        try:
            from backend.storage.bootstrap import ensure_buckets_from_env  # type: ignore
            ensure_buckets_from_env()
        except Exception:
            # Do not block wiring on bootstrap issues in dev.
            pass
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Storage wiring skipped due to error: %s: %s", exc.__class__.__name__, str(exc)
        )
        return False


__all__ = ["wire_supabase_adapter_if_configured"]
