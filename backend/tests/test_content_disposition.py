"""Contracts for safe HTTP download filenames."""

from urllib.parse import quote

import pytest

from backend.web.content_disposition import content_disposition_value


@pytest.mark.parametrize("disposition", ["inline", "attachment"])
def test_content_disposition_preserves_unicode_via_rfc_5987(disposition: str) -> None:
    filename = "программа🧪.py"

    value = content_disposition_value(disposition, filename, fallback="material.bin")

    assert value == (
        f"{disposition}; filename=\"material.py\"; filename*=UTF-8''{quote(filename, safe='')}"
    )
    value.encode("latin-1")


def test_content_disposition_neutralizes_header_and_path_delimiters() -> None:
    value = content_disposition_value(
        "attachment",
        'ordner\\seite"\r\n.txt',
        fallback="material.bin",
    )

    assert value == (
        "attachment; filename=\"ordner_seite.txt\"; filename*=UTF-8''ordner_seite___.txt"
    )
    assert "\r" not in value
    assert "\n" not in value
    assert "\\" not in value


def test_content_disposition_rejects_unvalidated_disposition() -> None:
    with pytest.raises(ValueError, match="invalid_content_disposition"):
        content_disposition_value("form-data", "material.pdf")
