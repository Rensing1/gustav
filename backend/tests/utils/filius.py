"""Shared Filius fixture packaging for parser and worker tests."""

import io
import zipfile


def fls_with_config(config: bytes) -> bytes:
    """Package an XML fixture exactly as expected by the Filius upload pipeline."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("projekt/konfiguration.xml", config)
    return buf.getvalue()
