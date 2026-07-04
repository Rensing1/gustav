"""Storage composition for the package-oriented FastAPI entry point."""

from __future__ import annotations

from backend.web.storage_wiring import wire_supabase_adapter_if_configured


def initialize_main_storage() -> None:
    """Attempt startup storage adapter wiring for the main web app.

    The underlying helper is intentionally idempotent and lazy-safe. If
    Supabase is not reachable at import/startup time, route-level lazy rewiring
    can still retry later when a request needs storage.
    """

    wire_supabase_adapter_if_configured()
