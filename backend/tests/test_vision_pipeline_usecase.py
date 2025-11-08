from unittest import mock


def test_process_pdf_bytes_invokes_renderer_with_preprocess():
    fake_pages = [mock.Mock(index=0, width=100, height=100, mode="L", data=b"x")]
    fake_meta = mock.Mock(page_count=1, dpi=300, grayscale=True, used_annotations=True)

    with mock.patch("backend.vision.pdf_renderer.render_pdf_to_images", return_value=(fake_pages, fake_meta)) as rp:
        with mock.patch("backend.vision.image_preprocess.preprocess", side_effect=lambda im: im) as pp:
            from backend.vision.pipeline import process_pdf_bytes

            pages, meta = process_pdf_bytes(b"%PDF bytes")

            assert pages is fake_pages and meta is fake_meta
            assert rp.called
            # Ensure preprocess hook is passed to renderer
            _, kwargs = rp.call_args
            assert callable(kwargs.get("preprocess"))
            assert pp.call_count == 0  # Not called here (renderer will invoke it)
