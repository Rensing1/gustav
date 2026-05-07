"""
Learning upload policy -- Filius FLS support.

Intent:
    The central learning upload policy must include Filius FLS as an accepted
    file MIME type so routers, repo guards, and storage verification share the
    same bounded upload surface.
"""

from __future__ import annotations


def test_learning_upload_policy_accepts_filius_fls_as_file_mime() -> None:
    from backend.storage.learning_policy import ALLOWED_FILE_MIME, DEFAULT_POLICY

    assert "application/x.filius.fls" in ALLOWED_FILE_MIME
    assert "application/x.filius.fls" in DEFAULT_POLICY.accepted_for_kind("file")
    assert "application/x.filius.fls" in DEFAULT_POLICY.allowed_mime_types
