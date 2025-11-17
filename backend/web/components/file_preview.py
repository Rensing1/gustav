"""
FilePreview Component

Small, reusable component to render inline previews for file-based materials.

Why:
    Teachers (and later students) should be able to see uploaded files
    (PDFs, images) directly on the page instead of only via a "Download"
    link and a new browser tab.

Behavior:
    - For image/* MIME types: renders an <img> wrapped in a container.
    - For application/pdf: renders an <iframe> based PDF preview.
    - For all other types: falls back to a simple download link.

Security:
    - Uses short-lived, owner-scoped download URLs provided by the API.
    - Escapes all attributes via the base Component helpers.
"""

from __future__ import annotations

from typing import Optional

from .base import Component


class FilePreview(Component):
    """Inline file preview for teaching materials and similar resources.

    Parameters:
        url: Short-lived download URL (inline disposition).
        mime: MIME type string (e.g. "application/pdf", "image/png").
        title: Optional human-friendly title used in captions/titles.
        alt: Optional alt text for images; falls back to title when omitted.
        max_height: CSS height for embedded viewers (e.g. "600px").

    Expected usage:
        - Teachers' "Material bearbeiten" page shows file previews using
          FilePreview instead of a bare "Download anzeigen" link.
        - Other pages can reuse the component whenever they have a URL
          and MIME type for a file material.
    """

    def __init__(
        self,
        url: str,
        mime: str,
        *,
        title: str = "",
        alt: Optional[str] = None,
        max_height: str = "600px",
    ) -> None:
        self.url = url or ""
        self.mime = (mime or "").lower()
        self.title = title or ""
        self.alt = (alt or "").strip()
        self.max_height = max_height

    def render(self) -> str:
        """Render an inline preview or a safe download fallback."""
        if not self.url:
            return ""

        mime = self.mime

        # Common wrapper attributes used for all preview types.
        # They expose hooks for JS-based zoom and basic keyboard accessibility.
        def wrapper_attrs(extra_class: str) -> str:
            cls = self.classes("file-preview", extra_class)
            return self.attributes(
                class_=cls,
                **{
                    "data-file-preview": "true",
                    "role": "button",
                    "tabindex": "0",
                },
            )
        # Images: inline <img> preview
        if mime.startswith("image/"):
            alt_text = self.alt or self.title or "Datei-Material"
            wrapper = wrapper_attrs("file-preview--image")
            img_attrs = self.attributes(
                src=self.url,
                alt=alt_text,
                class_="file-preview__image",
                loading="lazy",
            )
            return f'<figure {wrapper}><img {img_attrs}></figure>'

        # PDFs: embed via <iframe> with bounded height
        if mime == "application/pdf":
            viewer_title = self.title or "PDF-Vorschau"
            wrapper = wrapper_attrs("file-preview--pdf")
            frame_style = f"width: 100%; height: {self.max_height}; border: none;"
            iframe_attrs = self.attributes(
                src=self.url,
                title=viewer_title,
                class_="file-preview__frame",
                style=frame_style,
            )
            return f'<div {wrapper}><iframe {iframe_attrs}></iframe></div>'

        # Fallback: simple download link for unsupported types
        wrapper = wrapper_attrs("file-preview--download")
        link_label = self.title or "Download"
        link_attrs = self.attributes(
            href=self.url,
            target="_blank",
            rel="noopener",
            class_="btn",
        )
        return f'<div {wrapper}><a {link_attrs}>{self.escape(link_label)}</a></div>'
