"""
Unit test: CSRF diagnostic log must not include Referer path/query (privacy).

Why:
    The optional `CSRF_DIAG_LOG` mechanism should help debug CSRF issues, but it
    must not leak sensitive URLs (paths/queries) to disk logs. Only origins
    (scheme://host[:port]) are allowed.
"""

from __future__ import annotations

import importlib

_redact_origin_for_diag_log = importlib.import_module(
    "backend.web.routes.learning"
)._redact_origin_for_diag_log


def test_redact_origin_for_diag_log_strips_path_and_query() -> None:
    assert (
        _redact_origin_for_diag_log("https://app.localhost/courses/123?token=SECRET")
        == "https://app.localhost"
    )


def test_redact_origin_for_diag_log_keeps_origin_header() -> None:
    assert _redact_origin_for_diag_log("https://app.localhost") == "https://app.localhost"


def test_redact_origin_for_diag_log_handles_invalid_values() -> None:
    assert _redact_origin_for_diag_log("") == "?"
    assert _redact_origin_for_diag_log("not a url") == "?"
