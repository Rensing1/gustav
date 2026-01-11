"""
SSR helper — presign injection for learner submission previews.

Why:
    The SSR layer may enrich submission records with short-lived download URLs
    for rendering previews (image/PDF). To keep this helper testable and reduce
    tight coupling to route modules, the presign adapter should be injectable.
"""

from __future__ import annotations

import main  # type: ignore  # noqa: E402


def test_ssr_enrich_submission_records_supports_adapter_injection() -> None:
    class _FakeAdapter:
        def presign_download(self, **kwargs):  # type: ignore[no-untyped-def]
            return {"url": "https://example.invalid/presigned"}

    records = [
        {"kind": "image", "storage_key": "submissions/x.png", "mime_type": "image/png"}
    ]

    main._enrich_submission_records_with_file_urls(records, storage_adapter=_FakeAdapter())

    assert records[0].get("file_url") == "https://example.invalid/presigned"

