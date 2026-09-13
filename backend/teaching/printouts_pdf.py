"""PDF adapter for transient printable learning-unit student copies.

Why:
    The Teaching use case supplies a student-safe document model. This adapter
    turns it into deterministic A4 pages without network or filesystem access
    and imports source PDFs into fresh pages so annotations and document-level
    payloads are not copied into the result.
"""

from __future__ import annotations

import html
import re
from io import BytesIO
from typing import Any

from backend.teaching.printouts import PrintExportError, PrintPolicy
from backend.web.components.markdown import render_markdown_safe

_A4_PORTRAIT = (595.276, 841.89)
_A4_LANDSCAPE = (_A4_PORTRAIT[1], _A4_PORTRAIT[0])
_MAX_IMAGE_PIXELS = 40_000_000


def _value(item: object, name: str, default: object = None) -> object:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _markdown_for_print(source: object) -> str:
    """Render safe Markdown and expose every link destination on paper."""

    rendered = render_markdown_safe(str(source or ""))

    def replace_link(match: re.Match[str]) -> str:
        label, url = match.group(2), html.escape(match.group(1), quote=False)
        return f"{label} ({url})"

    return re.sub(r'<a href="([^"]+)"(?: title="[^"]*")?>(.*?)</a>', replace_link, rendered, flags=re.DOTALL)


def _weasyprint_document(markup: str, *, assets: dict[str, tuple[bytes, str]] | None = None) -> Any:
    """Lay out trusted template HTML while denying all external resource URLs."""

    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - deployment dependency guard
        raise PrintExportError("pdf_renderer_unavailable", 503) from exc

    available_assets = assets or {}

    def fetch_asset(url: str) -> dict[str, object]:
        if url not in available_assets:
            raise ValueError("external_resource_denied")
        content, mime_type = available_assets[url]
        return {"string": content, "mime_type": mime_type}

    try:
        return HTML(string=markup, url_fetcher=fetch_asset).render()
    except PrintExportError:
        raise
    except Exception as exc:
        raise PrintExportError("pdf_render_failed", 503) from exc


def _write_pdf(rendered: Any) -> bytes:
    """Keep layout and serialization failures behind the same safe error boundary."""
    try:
        return rendered.write_pdf()
    except Exception as exc:
        raise PrintExportError("pdf_render_failed", 503) from exc


def _weasyprint_pdf(markup: str, *, assets: dict[str, tuple[bytes, str]] | None = None) -> bytes:
    return _write_pdf(_weasyprint_document(markup, assets=assets))


def _base_styles(*, landscape: bool = False) -> str:
    """Keep section spacing inside the heading so adjacent margins cannot collapse it."""
    orientation = "landscape" if landscape else "portrait"
    return f"""
      @page {{ size: A4 {orientation}; margin: 16mm 15mm 18mm; }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: 'DejaVu Sans', sans-serif; font-size: 11pt; line-height: 1.45; color: #111; }}
      h1 {{ font-size: 18pt; line-height: 1.25; margin: 0 0 4mm; overflow-wrap: anywhere; }}
      .section-heading {{ font-size: 14pt; line-height: 1.3; border-bottom: .5pt solid #222; margin: 0 0 3mm; padding: 8mm 0 2mm; }}
      h3 {{ font-size: 12pt; line-height: 1.35; margin: 0 0 2mm; }}
      h1, h2, h3, h4, h5, h6 {{ break-after: avoid; }}
      .item-body h1, .item-body h2, .item-body h3,
      .item-body h4, .item-body h5, .item-body h6 {{ font-size: 11pt; line-height: 1.45; margin: 3mm 0 1.5mm; }}
      .item-body h3, .item-body h4, .item-body h5, .item-body h6 {{ font-weight: normal; font-style: italic; }}
      .item-body > :first-child {{ margin-top: 0; }}
      p, ul, ol, pre, blockquote, table {{ margin: 0 0 3mm; orphans: 3; widows: 3; }}
      ul, ol {{ padding-left: 6mm; }}
      li {{ margin-bottom: 1mm; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: .5pt solid #555; padding: 2mm; vertical-align: top; }}
      tr {{ break-inside: avoid; }}
      pre {{ white-space: pre-wrap; overflow-wrap: anywhere; border-left: .5pt solid #555; padding: 1mm 3mm; font-size: 10pt; }}
      code {{ font-family: 'DejaVu Sans Mono', monospace; }}
      img {{ display: block; max-width: 100%; max-height: 190mm; object-fit: contain; margin: 3mm auto; }}
      .print-header {{ break-inside: avoid; break-after: avoid; }}
      .student-fields {{ display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 5mm; font-size: 9pt; }}
      .student-field {{ border-bottom: .5pt solid #222; height: 8mm; }}
      .item {{ margin-bottom: 5mm; }}
      .image-item {{ break-inside: avoid; }}
      .hint {{ border-left: .5pt solid #555; padding: 1mm 3mm; font-size: 9pt; }}
    """


def _header(title: str) -> str:
    return f"""
      <header class="print-header">
        <h1>{html.escape(title)}</h1>
        <div class="student-fields">
          <div class="student-field">Name:</div>
          <div class="student-field">Kurs:</div>
          <div class="student-field">Datum:</div>
        </div>
      </header>
    """


def _validate_image(content: bytes, *, title: str) -> None:
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > _MAX_IMAGE_PIXELS:
                raise ValueError("image_dimensions_exceeded")
            image.verify()
    except Exception as exc:
        raise PrintExportError("material_unprintable", 422, material_title=title) from exc


def _html_item(item: object, *, asset_number: int, assets: dict[str, tuple[bytes, str]]) -> str:
    title = str(_value(item, "title", "") or "")
    item_type = str(_value(item, "type", "") or "")
    body = _markdown_for_print(_value(item, "body_md", ""))
    hint = str(_value(item, "digital_hint", "") or "")
    item_class = "item image-item" if item_type == "image" else "item"
    parts = [f'<article class="{item_class}"><h3>{html.escape(title)}</h3>', f'<div class="item-body">{body}</div>']
    if item_type == "image":
        content = _value(item, "content", b"")
        mime_type = str(_value(item, "mime_type", "") or "")
        if not isinstance(content, bytes):
            raise PrintExportError("material_unprintable", 422, material_title=title)
        _validate_image(content, title=title)
        asset_url = f"print-asset:{asset_number}"
        assets[asset_url] = (content, mime_type)
        alt_text = str(_value(item, "alt_text", "") or "")
        parts.append(f'<img src="{asset_url}" alt="{html.escape(alt_text)}">')
    if hint:
        parts.append(f'<p class="hint">{html.escape(hint)}</p>')
    parts.append("</article>")
    return "".join(parts)


def _content_pdf(document: object, items: list[tuple[str, object]], *, show_header: bool) -> bytes:
    title = str(_value(document, "title", "Lerneinheit") or "Lerneinheit")
    assets: dict[str, tuple[bytes, str]] = {}
    body = [_header(title)] if show_header else []
    current_node = None
    for index, (node_title, item) in enumerate(items):
        if node_title != current_node:
            body.append(f'<h2 class="section-heading">{html.escape(node_title)}</h2>')
            current_node = node_title
        body.append(_html_item(item, asset_number=index, assets=assets))
    markup = "<!doctype html><html lang=" + '"de"><head><meta charset="utf-8"><style>' + _base_styles() + "</style></head><body>" + "".join(body) + "</body></html>"
    return _weasyprint_pdf(markup, assets=assets)


def _overlay_pdf(
    *,
    title: str,
    page_number: int,
    total_pages: int,
    landscape: bool,
    divider: str = "",
    show_student_header: bool = False,
) -> tuple[bytes, float]:
    """Return the overlay and its actual top reservation in PDF points.

    The source label flows below the same wrapping header used by text pages.
    Measuring its laid-out bottom prevents long titles from covering an imported
    worksheet. This uses the existing render pass, not a second layout engine.
    """
    divider_html = f'<div class="divider">{html.escape(divider)}</div>' if divider else ""
    student_header = _header(title) if show_student_header else ""
    markup = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><style>
      {_base_styles(landscape=landscape)}
      .source-label {{ display: flow-root; }}
      .divider {{ padding: 0 0 2mm; border-bottom: .5pt solid #222; font-size: 9pt; overflow-wrap: anywhere; }}
      .print-header + .divider {{ margin-top: 5mm; }}
      .footer {{ position: fixed; bottom: -10mm; font-size: 8pt; white-space: nowrap; }}
      .footer-title {{ left: 0; max-width: 75%; overflow: hidden; text-overflow: ellipsis; }}
      .footer-page {{ right: 0; }}
    </style></head><body><div class="source-label">{student_header}{divider_html}</div>
      <div class="footer footer-title">{html.escape(title)}</div>
      <div class="footer footer-page">Seite {page_number} / {total_pages}</div>
    </body></html>"""
    rendered = _weasyprint_document(markup)
    # Layout boxes use CSS pixels; PDF placement uses points (72 / 96).
    label = next(box for box in rendered.pages[0]._page_box.descendants()
                 if box.element is not None and box.element.get("class") == "source-label")
    reserved_top = (label.border_box_y() + label.border_height()) * 72 / 96 + 4 * 72 / 25.4
    return _write_pdf(rendered), reserved_top


class LearningUnitPdfRenderer:
    """Render a prepared learning-unit document as sanitised A4 PDF pages.

    The caller must pass only author-authorised, student-visible content. Source
    PDFs and images are nevertheless parsed defensively and never fetched by URL.
    """

    def render(self, document: object, *, policy: PrintPolicy) -> bytes:
        try:
            from pypdf import PdfReader, PdfWriter, Transformation
        except Exception as exc:  # pragma: no cover - deployment dependency guard
            raise PrintExportError("pdf_renderer_unavailable", 503) from exc

        page_specs: list[tuple[object, bool, str, bool]] = []
        pending: list[tuple[str, object]] = []
        show_header = True

        def flush_pending() -> None:
            nonlocal show_header
            if not pending:
                return
            generated = PdfReader(BytesIO(_content_pdf(document, pending, show_header=show_header)), strict=True)
            for generated_page in generated.pages:
                page_specs.append((generated_page, False, "", False))
            pending.clear()
            show_header = False

        for node in list(_value(document, "nodes", []) or []):
            node_title = str(_value(node, "title", "") or "")
            for item in list(_value(node, "items", []) or []):
                if str(_value(item, "type", "") or "") != "pdf":
                    pending.append((node_title, item))
                    continue
                flush_pending()
                item_title = str(_value(item, "title", "Material") or "Material")
                content = _value(item, "content", b"")
                if not isinstance(content, bytes):
                    raise PrintExportError("material_unprintable", 422, material_title=item_title)
                try:
                    source = PdfReader(BytesIO(content), strict=True)
                    if source.is_encrypted:
                        raise ValueError("encrypted_pdf")
                    if not source.pages:
                        raise ValueError("empty_pdf")
                    filename = str(_value(item, "filename", "Datei") or "Datei")
                    for index, source_page in enumerate(source.pages):
                        width = float(source_page.mediabox.width)
                        height = float(source_page.mediabox.height)
                        if width <= 0 or height <= 0:
                            raise ValueError("invalid_page_size")
                        page_specs.append(
                            (source_page, width > height, f"{item_title} · {filename}" if index == 0 else "", True)
                        )
                    show_header = False
                except PrintExportError:
                    raise
                except Exception as exc:
                    raise PrintExportError("material_unprintable", 422, material_title=item_title) from exc
        flush_pending()

        if not page_specs:
            raise PrintExportError("invalid_print_selection", 400)
        if len(page_specs) > policy.max_pages:
            raise PrintExportError("page_limit_exceeded", 413)

        writer = PdfWriter()
        title = str(_value(document, "title", "Lerneinheit") or "Lerneinheit")
        total_pages = len(page_specs)
        for page_number, (source_page, landscape, divider, imported) in enumerate(page_specs, start=1):
            page_width, page_height = _A4_LANDSCAPE if landscape else _A4_PORTRAIT
            target = writer.add_blank_page(width=page_width, height=page_height)
            source_width = float(source_page.mediabox.width)
            source_height = float(source_page.mediabox.height)
            overlay, reserved_top = _overlay_pdf(
                title=title, page_number=page_number, total_pages=total_pages,
                landscape=landscape, divider=divider,
                show_student_header=bool(imported and page_number == 1),
            )
            if imported:
                # Reserve footer space on every source page, not only its first.
                left = right = 15 * 72 / 25.4
                bottom = 18 * 72 / 25.4
                top = reserved_top if divider else 16 * 72 / 25.4
            else:
                left = right = bottom = top = 0.0
            available_width = page_width - left - right
            available_height = page_height - bottom - top
            scale = min(available_width / source_width, available_height / source_height)
            x = left + (available_width - source_width * scale) / 2
            y = bottom + (available_height - source_height * scale) / 2
            target.merge_transformed_page(source_page, Transformation().scale(scale).translate(x, y))

            overlay_reader = PdfReader(BytesIO(overlay), strict=True)
            target.merge_page(overlay_reader.pages[0])
            if "/Annots" in target:
                del target["/Annots"]

        writer.add_metadata({"/Title": title, "/Producer": "GUSTAV"})
        output = BytesIO()
        writer.write(output)
        content = output.getvalue()
        if len(content) > policy.max_output_bytes:
            raise PrintExportError("output_bytes_exceeded", 413)
        return content


def _render_in_worker(connection: Any, document: object, policy: PrintPolicy, memory_limit_bytes: int) -> None:
    """Child-process entry point with OS-enforced resource ceilings."""

    try:
        import resource

        # Address-space and CPU ceilings limit malformed or unexpectedly complex
        # teacher content even if a rendering library regresses.
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (policy.max_output_bytes, policy.max_output_bytes))
        content = LearningUnitPdfRenderer().render(document, policy=policy)
        connection.send(("ok", content, None, None))
    except PrintExportError as exc:
        connection.send(("error", exc.code, exc.status_code, exc.material_title))
    except BaseException:
        # Never send exception text: parser errors may contain private filenames
        # or snippets from teacher-authored content.
        try:
            connection.send(("error", "pdf_render_failed", 503, None))
        except Exception:
            pass
    finally:
        connection.close()


class IsolatedLearningUnitPdfRenderer:
    """Run the PDF adapter in a disposable, resource-limited worker process."""

    def __init__(self, *, timeout_seconds: int = 35, memory_limit_bytes: int = 1536 * 1024 * 1024) -> None:
        self.timeout_seconds = timeout_seconds
        self.memory_limit_bytes = memory_limit_bytes

    def render(self, document: object, *, policy: PrintPolicy) -> bytes:
        import multiprocessing

        # ``spawn`` starts from a clean interpreter. A forked web worker would
        # inherit its whole virtual address space and make RLIMIT_AS misleading.
        context = multiprocessing.get_context("spawn")
        parent_connection, child_connection = context.Pipe(duplex=False)
        process = context.Process(
            target=_render_in_worker,
            args=(child_connection, document, policy, self.memory_limit_bytes),
            daemon=True,
        )
        process.start()
        child_connection.close()
        try:
            if not parent_connection.poll(self.timeout_seconds):
                process.terminate()
                process.join(timeout=2)
                raise PrintExportError("pdf_render_timeout", 503)
            status, payload, status_code, material_title = parent_connection.recv()
        except EOFError as exc:
            raise PrintExportError("pdf_render_failed", 503) from exc
        finally:
            parent_connection.close()
            if process.is_alive():
                process.join(timeout=2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        if status != "ok":
            raise PrintExportError(str(payload), int(status_code or 503), material_title=material_title)
        if not isinstance(payload, bytes):
            raise PrintExportError("pdf_render_failed", 503)
        return payload


__all__ = ["IsolatedLearningUnitPdfRenderer", "LearningUnitPdfRenderer"]
