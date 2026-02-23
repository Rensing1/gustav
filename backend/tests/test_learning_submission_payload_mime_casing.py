"""
Learning submission payload validation — MIME casing.

Intent:
    Clients sometimes send MIME types with non-canonical casing. The API should
    accept those values (case-insensitive comparison) and normalize them to the
    canonical lowercase string for consistent downstream policy checks.
"""

from __future__ import annotations

import routes.learning as learning  # type: ignore


def test_validate_submission_payload_accepts_mixed_case_makecode_hex_mime() -> None:
    kind, clean = learning._validate_submission_payload(
        {
            "kind": "file",
            "storage_key": "submissions/x/y/z/projekt.hex",
            "mime_type": "Application/X.MakeCode.Hex",
            "size_bytes": 1024,
            "sha256": "0" * 64,
        }
    )

    assert kind == "file"
    assert clean.get("mime_type") == "application/x.makecode.hex"

