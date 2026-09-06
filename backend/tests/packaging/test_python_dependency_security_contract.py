"""Keep reviewed non-AI security fixes while the DSPy baseline is frozen."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("pin", [
    "fastapi==0.136.3",
    "python-multipart==0.0.32",
    "python-jose[cryptography]==3.5.0",
    "Pillow==12.3.0",
    "bleach==6.4.0",
    "pip==26.2.1",
    "setuptools==84.0.0",
    "wheel==0.48.0",
])
def test_runtime_keeps_reviewed_security_versions(pin):
    assert pin in (ROOT / "backend/web/requirements.txt").read_text()
