from __future__ import annotations

from backend.web.components.layout import Layout


def test_layout_head_does_not_load_learning_upload_js() -> None:
    """The learning upload intent flow lives in `gustav.js`; avoid duplicate pipelines."""
    layout = Layout(title="t", content="<p>x</p>", user=None, show_nav=False)
    head = layout._render_head()
    assert "/static/js/learning_upload.js" not in head

