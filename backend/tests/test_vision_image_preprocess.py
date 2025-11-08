from PIL import Image, ImageChops
import numpy as np


def _unique_vals(img):
    arr = np.array(img)
    return np.unique(arr)


def test_preprocess_binarize_reduces_to_two_levels():
    # Create a synthetic grayscale gradient with a sharp rectangle
    w, h = 200, 100
    grad = Image.linear_gradient("L").resize((w, h))
    # Add a dark rectangle to ensure bimodal
    rect = Image.new("L", (w, h), 255)
    for y in range(20, 80):
        for x in range(60, 140):
            rect.putpixel((x, y), 30)
    img = ImageChops.darker(grad, rect)

    from backend.vision.image_preprocess import preprocess

    out = preprocess(img, denoise=False, equalize=False, binarize=True)
    assert out.mode == "L"
    uniq = _unique_vals(out)
    assert len(uniq) <= 2


def test_preprocess_denoise_and_equalize_changes_image():
    # Start from a noisy uniform image
    w, h = 128, 128
    rng = np.random.default_rng(42)
    base = np.full((h, w), 180, dtype=np.uint8)
    noise = rng.integers(0, 50, size=(h, w), dtype=np.uint8)
    arr = np.clip(base + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")

    from backend.vision.image_preprocess import preprocess

    out = preprocess(img, denoise=True, equalize=True, binarize=False)
    assert out.mode == "L"
    # The result should not be identical to input and should remain same size
    assert out.size == img.size
    diff = ImageChops.difference(out, img)
    # Some pixels should change due to denoise/equalize
    bbox = diff.getbbox()
    assert bbox is not None

