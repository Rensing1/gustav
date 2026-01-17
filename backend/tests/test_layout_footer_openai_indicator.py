"""
Layout footer indicator — smoke tests.

Why:
    Lehrkräfte sollen im Footer einen kleinen Status zur KI-Konfiguration sehen.
    Schüler:innen sollen keine internen Status-Anfragen/UI-Elemente bekommen.
"""

from __future__ import annotations

from backend.web.components.layout import Layout


def test_layout_renders_openai_status_chip_for_teachers() -> None:
    html = Layout(
        title="Test",
        content="<div>Hi</div>",
        user={"sub": "t", "name": "T", "role": "teacher", "roles": ["teacher"]},
        current_path="/",
    ).render()
    assert 'id="openai-status"' in html


def test_layout_hides_openai_status_chip_for_students() -> None:
    html = Layout(
        title="Test",
        content="<div>Hi</div>",
        user={"sub": "s", "name": "S", "role": "student", "roles": ["student"]},
        current_path="/",
    ).render()
    assert 'id="openai-status"' not in html

