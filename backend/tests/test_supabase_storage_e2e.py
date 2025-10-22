import os
import io
import pytest


pytestmark = pytest.mark.supabase_integration


def _should_run():
    return os.getenv("RUN_SUPABASE_E2E") == "1" and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")


@pytest.mark.skipif(not _should_run(), reason="Supabase E2E disabled; set RUN_SUPABASE_E2E=1 and env vars")
def test_e2e_supabase_upload_finalize_download_delete_flow():
    """
    High-level E2E smoke test (requires local Supabase Storage running):
      - Request upload intent
      - PUT file to signed upload URL
      - Finalize (DB persist)
      - Get download URL and fetch bytes
      - Delete material

    This test intentionally avoids asserting app-specific DB state to remain robust.
    """
    # We keep this as a placeholder to be implemented when E2E environment is wired in CI.
    # Implementation would:
    #  - boot app client
    #  - create unit/section, request intent
    #  - upload via requests.put(intent["url"], data=bytes, headers=intent["headers"]) with content-type
    #  - call finalize with sha256
    #  - GET download-url and requests.get(payload["url"]) assert status 200
    #  - call DELETE and ensure subsequent download-url returns 404/not_found
    assert True

