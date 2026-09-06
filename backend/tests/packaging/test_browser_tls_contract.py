"""Browser fixtures must exercise the same TLS boundary as real users."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_browser_support_never_disables_certificate_verification():
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "frontend/e2e").rglob("*.ts")
        if re.search(r"ignoreHTTPSErrors\s*:\s*true", path.read_text())
    ]
    assert offenders == []


def test_shared_browser_context_enforces_tls_after_options():
    support = (ROOT / "frontend/e2e/support/browser-context.ts").read_text()
    assert support.index("...options") < support.index("ignoreHTTPSErrors: false")
