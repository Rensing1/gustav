"""Rendering tests for printable learning-unit PDFs."""

from __future__ import annotations

from io import BytesIO

import pytest

from backend.teaching.printouts import PrintExportError, PrintPolicy
from backend.teaching.printouts_pdf import IsolatedLearningUnitPdfRenderer, LearningUnitPdfRenderer


def _blank_pdf(width: float, height: float) -> bytes:
    from pypdf import PdfWriter

    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    writer.write(stream)
    return stream.getvalue()


def _document(*items: dict[str, object]) -> dict[str, object]:
    return {"title": "Netzwerke verstehen", "nodes": [{"title": "Einstieg", "items": list(items)}]}


def test_renderer_creates_a4_student_copy_with_header_footer_and_visible_link_url() -> None:
    from pypdf import PdfReader

    content = LearningUnitPdfRenderer().render(
        _document(
            {
                "type": "markdown",
                "title": "Merkblatt",
                "body_md": "Lies die [Erklärung](https://example.org/netze).",
            },
            {
                "type": "task",
                "title": "Aufgabe",
                "body_md": "Beschreibe das Netzwerk.",
                "digital_hint": "Für die interaktive Bearbeitung wird ein digitales Gerät benötigt.",
            },
        ),
        policy=PrintPolicy(),
    )

    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) == pytest.approx(595.28, abs=1)
    assert float(reader.pages[0].mediabox.height) == pytest.approx(841.89, abs=1)
    text = reader.pages[0].extract_text()
    assert "Netzwerke verstehen" in text
    assert "Name:" in text and "Kurs:" in text and "Datum:" in text
    assert "Erklärung (https://example.org/netze)" in text
    assert "Für die interaktive Bearbeitung" in text
    assert "Seite 1 / 1" in text


def test_renderer_inserts_source_pdf_as_fitted_a4_page_and_removes_annotations() -> None:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, NameObject

    source_stream = BytesIO()
    source = PdfWriter()
    page = source.add_blank_page(width=842, height=595)
    page[NameObject("/Annots")] = ArrayObject()
    source.write(source_stream)

    content = LearningUnitPdfRenderer().render(
        _document(
            {"type": "markdown", "title": "Vorbereitung", "body_md": "Vor dem Arbeitsblatt."},
            {
                "type": "pdf",
                "title": "Arbeitsblatt",
                "body_md": "",
                "filename": "blatt.pdf",
                "mime_type": "application/pdf",
                "alt_text": "",
                "content": source_stream.getvalue(),
            },
        ),
        policy=PrintPolicy(),
    )

    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) == 2
    assert float(reader.pages[1].mediabox.width) > float(reader.pages[1].mediabox.height)
    assert "/Annots" not in reader.pages[1]
    assert "Arbeitsblatt · blatt.pdf" in reader.pages[1].extract_text()
    assert "Netzwerke verstehen" in reader.pages[1].extract_text()
    assert "Seite 2 / 2" in reader.pages[1].extract_text()


def test_renderer_rejects_corrupt_and_encrypted_source_pdfs() -> None:
    from pypdf import PdfWriter

    encrypted_stream = BytesIO()
    encrypted = PdfWriter()
    encrypted.add_blank_page(width=595, height=842)
    encrypted.encrypt("secret")
    encrypted.write(encrypted_stream)

    renderer = LearningUnitPdfRenderer()
    for payload in (b"not-a-pdf", encrypted_stream.getvalue()):
        with pytest.raises(PrintExportError) as error:
            renderer.render(
                _document(
                    {
                        "type": "pdf",
                        "title": "Defektes Blatt",
                        "body_md": "",
                        "filename": "defekt.pdf",
                        "mime_type": "application/pdf",
                        "alt_text": "",
                        "content": payload,
                    }
                ),
                policy=PrintPolicy(),
            )

        assert error.value.code == "material_unprintable"
        assert error.value.status_code == 422
        assert error.value.material_title == "Defektes Blatt"


def test_renderer_enforces_page_limit_before_returning_output() -> None:
    renderer = LearningUnitPdfRenderer()
    source = _blank_pdf(595, 842)

    with pytest.raises(PrintExportError) as error:
        renderer.render(
            _document(
                *[
                    {
                        "type": "pdf",
                        "title": f"Blatt {number}",
                        "body_md": "",
                        "filename": f"blatt-{number}.pdf",
                        "mime_type": "application/pdf",
                        "alt_text": "",
                        "content": source,
                    }
                    for number in range(3)
                ]
            ),
            policy=PrintPolicy(max_pages=2),
        )

    assert error.value.code == "page_limit_exceeded"
    assert error.value.status_code == 413


def test_pdf_only_selection_keeps_student_name_course_and_date_fields_on_first_page() -> None:
    from pypdf import PdfReader

    content = LearningUnitPdfRenderer().render(
        _document(
            {
                "type": "pdf",
                "title": "Arbeitsblatt",
                "body_md": "",
                "filename": "blatt.pdf",
                "mime_type": "application/pdf",
                "alt_text": "",
                "content": _blank_pdf(595, 842),
            }
        ),
        policy=PrintPolicy(),
    )

    first_page_text = PdfReader(BytesIO(content)).pages[0].extract_text()
    assert "Netzwerke verstehen" in first_page_text
    assert "Name:" in first_page_text
    assert "Kurs:" in first_page_text
    assert "Datum:" in first_page_text


def test_isolated_renderer_returns_pdf_from_a_short_lived_worker() -> None:
    content = IsolatedLearningUnitPdfRenderer(timeout_seconds=10).render(
        _document({"type": "markdown", "title": "Merkblatt", "body_md": "Kurzer Inhalt."}),
        policy=PrintPolicy(),
    )

    assert content.startswith(b"%PDF")
