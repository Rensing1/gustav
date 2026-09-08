"""Construct the standard storage adapter without mutating web routes."""

import os

from backend.teaching.storage import StorageAdapterProtocol


def build_storage_adapter() -> StorageAdapterProtocol:
    """Build the existing server-side adapter from the standard production ENV.

    Storage3 accepts the service key directly, as in the course lifecycle worker.
    No route globals or alternate local hosts are involved. Failed construction
    raises so the lazy factory can retry instead of caching an unavailable client.
    """
    base_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    service_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base_url or not service_key:
        raise RuntimeError("storage_not_configured")
    from storage3._sync.client import SyncStorageClient

    from backend.teaching.storage_supabase import SupabaseStorageAdapter

    client = SyncStorageClient(
        f"{base_url}/storage/v1", {"Authorization": f"Bearer {service_key}", "apikey": service_key}
    )
    return SupabaseStorageAdapter(client)
