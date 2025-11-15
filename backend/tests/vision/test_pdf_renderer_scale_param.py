"""
pdf_renderer should call pypdfium2's page.render with a `scale` argument,
not `dpi`. This test fakes the pdfium module and asserts the call shape.
"""

from __future__ import annotations

from types import SimpleNamespace
import sys


def test_render_uses_scale(monkeypatch):
    calls = []

    class _Bitmap:
        def to_pil(self):
            # minimal fake PIL-like object
            class _Img:
                mode = "L"
                width = 10
                height = 10
                def convert(self, *_args, **_kwargs):
                    return self
                def save(self, *_args, **_kwargs):  # pragma: no cover - not invoked here
                    return None
            return _Img()

    class _Page:
        def render(self, **kwargs):
            calls.append(kwargs)
            return _Bitmap()

    class _Doc:
        def __init__(self, _bytes):
            self._pages = [_Page()]
        def __len__(self):
            return 1
        def __getitem__(self, idx):
            return self._pages[idx]

    fake_pdfium = SimpleNamespace(PdfDocument=lambda b: _Doc(b), BitmapConvFlags=SimpleNamespace(ANNOT=1))
    monkeypatch.setitem(sys.modules, "pypdfium2", fake_pdfium)

    from backend.vision.pdf_renderer import render_pdf_to_images

    pages, _meta = render_pdf_to_images(b"%PDF-test", dpi=300)
    assert len(pages) == 1
    assert calls, "render() should have been called"
    # ensure dpi wasn't passed; scale + draw_annots should be used
    assert "dpi" not in calls[0]
    assert "scale" in calls[0]
    assert calls[0].get("draw_annots") is True
