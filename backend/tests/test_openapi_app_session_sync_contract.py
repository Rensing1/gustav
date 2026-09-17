"""The former synchronization endpoint must not survive the single-session cutover."""
from pathlib import Path

import yaml


def test_session_sync_is_retired():
    spec = yaml.safe_load(Path("api/openapi.yml").read_text())
    assert "/api/app/session-sync" not in spec["paths"]
    assert "AppSessionSyncRequest" not in spec["components"]["schemas"]
