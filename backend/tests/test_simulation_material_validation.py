"""Unit tests for the offline boundary of interactive simulations."""

import pytest

from backend.teaching.services.simulation_validation import validate_simulation_html

VALID_HTML = b"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><style>
body { font-family: sans-serif } .dot { background: url(data:image/png;base64,AA==) }
</style></head><body><button id="plus">Plus</button><output id="value">0</output>
<script>let n=0; plus.onclick=()=>{value.textContent=String(++n)}</script></body></html>"""


def test_accepts_complete_self_contained_html() -> None:
    assert validate_simulation_html(VALID_HTML) == VALID_HTML.decode("utf-8")


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        (b"", "invalid_simulation_html"),
        (b"\xff\xfe", "invalid_simulation_html"),
        (b"<p>fragment</p>", "invalid_simulation_html"),
        (b"<html><head></head><body></body></html>", "invalid_simulation_html"),
        (b"<!doctype html><html><head></head><body>", "invalid_simulation_html"),
        (
            b"<!doctype html><html><head><meta charset='iso-8859-1'></head><body></body></html>",
            "invalid_simulation_html",
        ),
        (
            b"<html><body><iframe srcdoc='<p>x</p>'></iframe></body></html>",
            "simulation_not_self_contained",
        ),
        (
            b"<html><head><script src='https://example.test/a.js'></script></head><body></body></html>",
            "simulation_not_self_contained",
        ),
        (
            b"<html><body><img src='//example.test/a.png'></body></html>",
            "simulation_not_self_contained",
        ),
        (b"<html><body><img src='assets/a.png'></body></html>", "simulation_not_self_contained"),
        (
            b"<html><head><style>@import 'https://example.test/a.css';</style></head><body></body></html>",
            "simulation_not_self_contained",
        ),
        (
            b"<html><body><script>fetch('/api/session')</script></body></html>",
            "simulation_not_self_contained",
        ),
        (
            b"<html><body><script>window.open('https://example.test')</script></body></html>",
            "simulation_not_self_contained",
        ),
        (
            b"<!doctype html><html><body><script>"
            b"import helper from './helper.js'"
            b"</script></body></html>",
            "simulation_not_self_contained",
        ),
        (
            b"<!doctype html><html><body><script>location.href = 'https://example.test'</script></body></html>",
            "simulation_not_self_contained",
        ),
        (
            b"<html><head><meta http-equiv='refresh' content='0;url=https://example.test'></head><body></body></html>",
            "simulation_not_self_contained",
        ),
    ],
)
def test_rejects_invalid_or_non_offline_html(payload: bytes, detail: str) -> None:
    with pytest.raises(ValueError, match=f"^{detail}$"):
        validate_simulation_html(payload)


def test_allows_internal_fragment_links_and_inline_form_controls() -> None:
    payload = b"""<!doctype html><html><body>
    <a href="#help">Hilfe</a><form><input type="range"><button type="button">Los</button></form>
    <section id="help">Erklaerung</section></body></html>"""

    validate_simulation_html(payload)
