import builtins
from types import SimpleNamespace
from unittest import mock

import pytest


@pytest.fixture()
def fake_pdfium(monkeypatch):
    # Build a fake pypdfium2 API surface we use
    class FakeBitmap:
        def __init__(self, w=1000, h=1400, mode="RGB"):
            self._w = w
            self._h = h
            self._mode = mode

        def to_pil(self):
            # Fake PIL Image via a simple object with needed props and save()
            class _Img:
                def __init__(self, w, h, mode):
                    self.width = w
                    self.height = h
                    self.mode = mode

                def convert(self, mode):
                    self.mode = mode
                    return self

                def save(self, fp, format="PNG"):
                    fp.write(b"PNGDATA")

            return _Img(self._w, self._h, self._mode)

    class FakePage:
        def __init__(self, idx):
            self.idx = idx

        def render(self, **kwargs):
            # New renderer passes scale/draw_annots instead of dpi.
            scale = kwargs.get("scale")
            assert scale is None or isinstance(scale, (int, float))
            return FakeBitmap()

    class FakeDoc:
        def __init__(self, n):
            self._n = n

        def __len__(self):
            return self._n

        def __getitem__(self, i):
            if i >= self._n:
                raise IndexError
            return FakePage(i)

    fake = SimpleNamespace(
        PdfDocument=lambda b: FakeDoc(5),
        BitmapConvFlags=SimpleNamespace(ANNOT=1),
    )
    monkeypatch.setitem(builtins.__dict__, "pypdfium2", fake)
    monkeypatch.setitem(mock.sys.modules, "pypdfium2", fake)
    return fake


def test_render_pdf_defaults_sequential(fake_pdfium):
    from backend.vision.pdf_renderer import render_pdf_to_images

    pages, meta = render_pdf_to_images(b"%PDF fake")
    assert len(pages) == 5
    assert meta.page_count == 5
    assert meta.dpi == 300 and meta.grayscale and meta.used_annotations
    # First page characteristics
    p0 = pages[0]
    assert p0.index == 0
    assert p0.width > 0 and p0.height > 0
    assert p0.mode == "L"  # grayscale enforced
    assert isinstance(p0.data, (bytes, bytearray)) and len(p0.data) > 0


def test_page_limit_enforced(monkeypatch):
    # 5-page doc but limit to 2
    class FakeDoc:
        def __len__(self):
            return 5

        def __getitem__(self, i):
            class P:
                def render(self, **_kwargs):
                    class B:
                        def to_pil(self):
                            class I:
                                width = 800
                                height = 1200
                                mode = "L"

                                def convert(self, mode):
                                    self.mode = mode
                                    return self

                                def save(self, fp, format="PNG"):
                                    fp.write(b"PNGDATA")

                            return I()

                    return B()

            return P()

    fake = SimpleNamespace(PdfDocument=lambda b: FakeDoc(), BitmapConvFlags=SimpleNamespace(ANNOT=1))
    monkeypatch.setitem(mock.sys.modules, "pypdfium2", fake)

    from backend.vision.pdf_renderer import render_pdf_to_images

    pages, meta = render_pdf_to_images(b"%PDF", page_limit=2)
    assert len(pages) == 2
    assert meta.page_count == 5


def test_open_failure_raises(monkeypatch):
    class Boom(Exception):
        pass

    def raise_open(_):
        raise Boom()

    fake = SimpleNamespace(PdfDocument=raise_open, BitmapConvFlags=SimpleNamespace(ANNOT=1))
    monkeypatch.setitem(mock.sys.modules, "pypdfium2", fake)

    from backend.vision.pdf_renderer import render_pdf_to_images, PdfRenderError

    with pytest.raises(PdfRenderError):
        render_pdf_to_images(b"broken")


def test_render_failure_raises(monkeypatch):
    class FakeDoc:
        def __len__(self):
            return 1

        def __getitem__(self, i):
            class P:
                def render(self, dpi=300, flags=0):
                    raise RuntimeError("boom")

            return P()

    fake = SimpleNamespace(PdfDocument=lambda b: FakeDoc(), BitmapConvFlags=SimpleNamespace(ANNOT=1))
    monkeypatch.setitem(mock.sys.modules, "pypdfium2", fake)

    from backend.vision.pdf_renderer import render_pdf_to_images, PdfRenderError

    with pytest.raises(PdfRenderError):
        render_pdf_to_images(b"%PDF")


def test_render_allows_preprocess_hook(fake_pdfium):
    from backend.vision.pdf_renderer import render_pdf_to_images

    called = {"ok": False}

    def _pp(pil):
        called["ok"] = True
        return pil

    pages, meta = render_pdf_to_images(b"%PDF", preprocess=_pp)
    assert called["ok"] is True
