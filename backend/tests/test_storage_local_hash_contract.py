"""Contract tests for local storage hash helpers.

These helpers belong to the storage boundary. The web entrypoint may trigger
upload flows, but it must not own filesystem verification details.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.storage import verification

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_local_hash_helper_hashes_file_within_configured_root(tmp_path: Path) -> None:
    """Local hash verification should be reusable outside the web entrypoint."""

    payload = b"student-submission-bytes"
    storage_key = "course/task/submission.png"
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)

    actual = verification.compute_local_sha256(
        storage_key=storage_key,
        expected_size=len(payload) + 1,
        local_verify_root=str(tmp_path),
    )

    assert actual == hashlib.sha256(payload).hexdigest()


def test_local_hash_helper_rejects_path_escape(tmp_path: Path) -> None:
    """A storage key must never escape the configured verification root."""

    outside = tmp_path.parent / "outside-submission.bin"
    outside.write_bytes(b"outside")

    actual = verification.compute_local_sha256(
        storage_key=f"../{outside.name}",
        expected_size=outside.stat().st_size,
        local_verify_root=str(tmp_path),
    )

    assert actual is None


def test_web_entrypoint_does_not_define_storage_filesystem_helpers() -> None:
    """Storage filesystem helpers should not live in backend.web.main."""

    source = (REPO_ROOT / "backend/web/main.py").read_text(encoding="utf-8")

    assert "def _resolve_storage_root" not in source
    assert "def _compute_local_sha256" not in source
