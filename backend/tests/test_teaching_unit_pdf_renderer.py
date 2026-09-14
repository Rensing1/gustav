"""Rendering tests for printable learning-unit PDFs."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

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


def _image_material(*, width: int = 480, height: int = 240) -> dict[str, object]:
    from PIL import Image, ImageDraw, ImageFont

    stream = BytesIO()
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("DejaVuSans.ttf", max(16, width // 28))
    for left, text in [(0.05, "Eingabe"), (0.55, "Ausgabe")]:
        draw.rectangle((width * left, height * .15, width * (left + .4), height * .85), outline="black", width=max(1, width // 350))
        draw.text((width * (left + .2), height * .5), text, font=font, fill="black", anchor="mm")
    image.save(stream, format="PNG")
    return {"type": "image", "title": "Netzwerkdiagramm", "body_md": "Beachte die Datei `beispiel.fls`.",
            "filename": "original-upload-123.png", "mime_type": "image/png", "content": stream.getvalue()}


def test_image_filename_is_not_printed_but_authored_text_and_image_remain() -> None:
    from pypdf import PdfReader

    page = PdfReader(BytesIO(LearningUnitPdfRenderer().render(_document(_image_material()), policy=PrintPolicy()))).pages[0]
    text = page.extract_text()
    assert "original-upload-123.png" not in text
    assert "Datei:" not in text
    assert "Netzwerkdiagramm" in text and "beispiel.fls" in text
    assert len(page.images) == 1


def test_print_typography_and_compact_wrapping_header_use_actual_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    from weasyprint import HTML

    from backend.teaching import printouts_pdf

    markup: list[str] = []
    monkeypatch.setattr(printouts_pdf, "_weasyprint_pdf", lambda source, **kwargs: markup.append(source) or b"%PDF")
    title = "Digitale Systeme verstehen und verantwortungsvoll gestalten: Eingabe, Verarbeitung und Ausgabe"
    printouts_pdf._content_pdf({"title": title}, [("Untersuchen", {
        "type": "markdown", "title": "Materialüberschrift", "body_md": "# Inhaltsebene eins\n\n## Inhaltsebene zwei\n\n### Inhaltsebene drei\n\nFließtext mit Umlauten: ä, ö, ü und ß."
    })], show_header=True)
    pages = HTML(string=markup[0]).render().pages
    assert len(pages) == 1
    boxes = list(pages[0]._page_box.descendants())
    blocks = [box for box in boxes if box.__class__.__name__ == "BlockBox"]
    heading = next(box for box in blocks if box.element_tag == "h1")
    section = next(box for box in blocks if box.element.get("class") == "section-heading")
    item_title = next(box for box in blocks if box.element_tag == "h3" and box.element.text == "Materialüberschrift")
    paragraph = next(box for box in blocks if box.element_tag == "p")
    assert heading.style["font_size"] == pytest.approx(18 * 96 / 72)
    assert section.style["font_size"] == pytest.approx(14 * 96 / 72)
    assert item_title.style["font_size"] == pytest.approx(12 * 96 / 72)
    assert paragraph.style["font_size"] == pytest.approx(11 * 96 / 72)
    assert paragraph.style["line_height"] == ("NUMBER", 1.45)
    assert paragraph.style["orphans"] == paragraph.style["widows"] == 3
    authored_headings = [box for box in blocks if box.element_tag in {"h1", "h2", "h3"} and (box.element.text or "").startswith("Inhaltsebene")]
    assert len(authored_headings) == 3
    assert all(box.style["font_size"] < item_title.style["font_size"] for box in authored_headings)
    fields = [box for box in blocks if box.element.get("class") == "student-field"]
    assert len(fields) == 3
    assert len(heading.children) >= 2  # Long titles wrap, rather than disappear behind ellipses.
    assert heading.border_box_y() + heading.border_height() <= fields[0].border_box_y()
    assert fields[0].border_box_y() + fields[0].border_height() < section.border_box_y() + section.padding_top
    assert fields[0].border_box_y() - heading.border_box_y() - heading.border_height() <= 4 * 96 / 25.4 + .5


@pytest.mark.parametrize("item_type", ["pdf", "markdown"])
def test_long_title_is_complete_and_above_source_content(tmp_path: Path, item_type: str) -> None:
    from pypdf import PdfReader

    from backend.teaching.printouts_pdf import _weasyprint_pdf

    title = "Digitale Systeme verstehen und verantwortungsvoll gestalten: Eingabe, Verarbeitung und Ausgabe im Alltag"
    source = _weasyprint_pdf('<style>@page { size:A4; margin:0; } body { margin:0; }</style><p>QUELLENANFANG</p>')
    document = _document({"type": item_type, "title": "Quellenblatt", "filename": "blatt.pdf", "content": source, "body_md": "QUELLENANFANG"})
    document["title"] = title
    pdf = LearningUnitPdfRenderer().render(document, policy=PrintPolicy())
    (tmp_path / f"long-title-{item_type}.pdf").write_bytes(pdf)
    page = PdfReader(BytesIO(pdf)).pages[0]
    assert " ".join(title.split()) in " ".join(page.extract_text().split())
    assert "QUELLENANFANG" in page.extract_text()
    runs: list[tuple[str, float, float]] = []
    page.extract_text(visitor_text=lambda text, cm, tm, font, size: runs.append((text, cm[5] + tm[5] * cm[3], abs(size * cm[3]))))
    title_lines = [(text, y) for text, y, size in runs if text.strip() and size == pytest.approx(18)]
    assert len(title_lines) >= 2
    name_y = next(y for text, y, size in runs if "Name:" in text)
    source_y = next(y for text, y, size in runs if "QUELLENANFANG" in text)
    assert min(y for text, y in title_lines) > name_y > source_y


@pytest.mark.parametrize("width,height", [(240, 120), (1400, 1000)])
def test_image_and_material_heading_stay_together_without_distortion(width: int, height: int, tmp_path: Path) -> None:
    from pypdf import PdfReader

    document = _document(
        {"type": "markdown", "title": "Vorbereitung", "body_md": "\n\n".join(["Lies und begründe Deine Beobachtung. " * 5] * 9)},
        _image_material(width=width, height=height),
    )
    pdf = LearningUnitPdfRenderer().render(document, policy=PrintPolicy())
    (tmp_path / f"image-{width}.pdf").write_bytes(pdf)
    pages = PdfReader(BytesIO(pdf)).pages
    # A shared PDF resource may list an image on pages that do not paint it.
    image_page = next(page for page in pages if any(op == b"Do" for args, op in page.get_contents().operations))
    assert "Netzwerkdiagramm" in image_page.extract_text()
    assert image_page.images[0].image.size == (width, height)
    placements: list[list[float]] = []
    image_page.extract_text(visitor_operand_before=lambda op, args, cm, tm: placements.append(cm) if op == b"Do" else None)
    matrix = placements[0]
    assert abs(matrix[0] / matrix[3]) == pytest.approx(width / height, rel=.001)
    assert abs(matrix[0]) <= 180 * 72 / 25.4 + .5
    assert abs(matrix[3]) <= 190 * 72 / 25.4 + .5


def test_all_imported_pages_reserve_footer_space_and_header_is_not_repeated(tmp_path: Path) -> None:
    from pypdf import PdfReader

    from backend.teaching.printouts_pdf import _weasyprint_pdf

    source = _weasyprint_pdf('''<style>
      @page { size:A4; margin:0; } body { margin:0; }
      .edge { position:fixed; bottom:0; margin:0; }
      </style><p>QUELLENSEITE EINS</p><p style="break-before:page">QUELLENSEITE ZWEI</p>
      <p class="edge">QUELLENUNTERKANTE</p>''')
    pdf = LearningUnitPdfRenderer().render(_document(
        {"type": "pdf", "title": "Quellenblatt", "filename": "blatt.pdf", "content": source},
        {"type": "task", "title": "Abschluss", "body_md": "Begründe Deine Beobachtung."},
    ), policy=PrintPolicy())
    (tmp_path / "source-footer-clearance.pdf").write_bytes(pdf)
    pages = PdfReader(BytesIO(pdf)).pages
    assert len(pages) == 3
    assert sum(page.extract_text().count("Name:") for page in pages) == 1
    for page in pages[:2]:
        runs: list[tuple[str, float]] = []
        page.extract_text(visitor_text=lambda text, cm, tm, font, size: runs.append((text, cm[5] + tm[5] * cm[3])))
        source_y = next(y for text, y in runs if "QUELLENUNTERKANTE" in text)
        footer_y = next(y for text, y in runs if "Seite " in text)
        assert source_y >= 18 * 72 / 25.4
        assert source_y - footer_y >= 15


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


@pytest.mark.parametrize("paragraphs", [10, 14, 18, 22])
def test_section_heading_stays_with_following_content_across_page_breaks(paragraphs: int) -> None:
    from pypdf import PdfReader

    content = LearningUnitPdfRenderer().render({
        "title": "Abschnittswechsel",
        "nodes": [
            {"title": "Vorbereitung", "items": [{"type": "markdown", "title": "Lesetext", "body_md": "\n\n".join(["Ein nachvollziehbarer Beleg unterstützt die Aussage. " * 4] * paragraphs)}]},
            {"title": "Programme entwickeln", "items": [{"type": "task", "title": "Erste Programmieraufgabe", "body_md": "ENTWICKLUNGSSTART: Beschreibe die Eingabe, Verarbeitung und Ausgabe.\n\n" + "\n\n".join(["Prüfe das Ergebnis und begründe Deine Entscheidung. " * 4] * 12)}]},
        ],
    }, policy=PrintPolicy())
    pages = [page.extract_text() for page in PdfReader(BytesIO(content)).pages]
    assert len(pages) >= 2
    heading_page = next(text for text in pages if "Programme entwickeln" in text)
    assert "Erste Programmieraufgabe" in heading_page
    assert "ENTWICKLUNGSSTART" in heading_page


def test_print_section_spacing_cannot_collapse_into_the_previous_item(monkeypatch: pytest.MonkeyPatch) -> None:
    from weasyprint import HTML

    from backend.teaching import printouts_pdf

    markup: list[str] = []
    monkeypatch.setattr(printouts_pdf, "_weasyprint_pdf", lambda source, **kwargs: markup.append(source) or b"%PDF")
    printouts_pdf._content_pdf({"title": "Abstände"}, [
        ("Erster Abschnitt", {"type": "markdown", "title": "Erstes Material", "body_md": "Letzter Satz."}),
        ("Zweiter Abschnitt", {"type": "task", "title": "Zweite Aufgabe", "body_md": "Nächster Inhalt."}),
    ], show_header=True)
    # Inspect actual layout boxes, not the mere presence of a CSS declaration.
    boxes = list(HTML(string=markup[0]).render().pages[0]._page_box.descendants())
    headings = [box for box in boxes if box.element_tag == "h2" and box.__class__.__name__ == "BlockBox"]
    articles = [box for box in boxes if box.element_tag == "article" and box.__class__.__name__ == "BlockBox"]
    previous_bottom = articles[0].border_box_y() + articles[0].border_height()
    actual_gap = headings[1].border_box_y() - previous_bottom
    # Internal spacing remains intact even when a page boundary discards an
    # adjoining vertical margin; the renderer must not rely on UA defaults.
    assert headings[1].margin_top == 0
    assert headings[1].padding_top == pytest.approx(8 * 96 / 25.4)
    assert actual_gap + headings[1].padding_top >= 8 * 96 / 25.4 - 0.5
    assert headings[1].style["break_after"] == "avoid"
    assert headings[1].element.get("class") == "section-heading"


def test_long_material_starts_in_the_available_space_instead_of_leaving_a_blank_page() -> None:
    from pypdf import PdfReader

    content = LearningUnitPdfRenderer().render(_document(
        {"type": "markdown", "title": "Kurze Einführung", "body_md": "## Leitfragen\n\nEin kurzer Einstieg."},
        {"type": "markdown", "title": "Langer Lesetext", "body_md": "TEXTANFANG: Ein zusammenhängender Text.\n\n" + "\n\n".join(["Lerne, prüfe und begründe Deine Entscheidung. " * 5] * 28)},
    ), policy=PrintPolicy())
    pages = PdfReader(BytesIO(content)).pages
    assert len(pages) > 1
    assert "TEXTANFANG" in pages[0].extract_text()


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


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_import_preserves_stored_page_rotation(rotation: int, tmp_path: Path) -> None:
    from math import hypot

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    source = PdfWriter()
    page = source.add_blank_page(width=595, height=842)
    drawing = DecodedStreamObject()
    # An asymmetric marker makes both orientation and position visible in QA.
    drawing.set_data(b"0 0 0 rg 20 30 40 10 re f 20 30 10 60 re f")
    page[NameObject("/Contents")] = source._add_object(drawing)
    page.rotate(rotation)
    stream = BytesIO()
    source.write(stream)
    (tmp_path / f"source-{rotation}.pdf").write_bytes(stream.getvalue())
    content = LearningUnitPdfRenderer().render(_document({
        "type": "pdf", "title": "Gedrehtes Arbeitsblatt", "filename": "blatt.pdf",
        "content": stream.getvalue(),
    }), policy=PrintPolicy())
    (tmp_path / f"result-{rotation}.pdf").write_bytes(content)
    result = PdfReader(BytesIO(content)).pages[0]
    assert (float(result.mediabox.width) > float(result.mediabox.height)) == (rotation != 180)
    matrices: list[list[float]] = []
    result.extract_text(visitor_operand_before=lambda op, args, cm, tm:
                        matrices.append(cm) if op == b"re" and list(args) == [20, 30, 40, 10] else None)
    assert len(matrices) == 1
    a, b, c, d = matrices[0][:4]
    scale = hypot(a, b)
    expected = {90: (0, -1, 1, 0), 180: (-1, 0, 0, -1), 270: (0, 1, -1, 0)}
    assert (a / scale, b / scale, c / scale, d / scale) == pytest.approx(expected[rotation], abs=1e-6)


@pytest.mark.parametrize("url", [
    "https://school.example/suche?a=1&b=2",
    "https://school.example/suche?a=1&amp;b=2",
])
def test_printed_link_preserves_query_parameters(url: str) -> None:
    from pypdf import PdfReader

    # Escape a literal ampersand for Markdown so even literal entity text survives.
    markdown_url = url.replace("&", "&amp;")
    content = LearningUnitPdfRenderer().render(_document({
        "type": "markdown", "title": "Recherche", "body_md": f"[Arbeitsblatt]({markdown_url})",
    }), policy=PrintPolicy())
    text = PdfReader(BytesIO(content)).pages[0].extract_text()
    assert f"Arbeitsblatt ({url})" in text


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
