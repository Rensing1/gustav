from backend.web.main import _render_submission_result_static_html


def test_complex_image_provider_failure_renders_student_action_hint() -> None:
    html = _render_submission_result_static_html(
        {
            "analysis_status": "failed",
            "error_code": "feedback_failed",
            "feedback_last_error": "image_too_complex_for_provider",
            "created_at": "2026-05-15T09:00:00+00:00",
        },
        submission_id="11111111-1111-1111-1111-111111111111",
    )

    assert "Das Bild ist wahrscheinlich zu groß oder zu komplex." in html
    assert "nur die Zeichnung statt des ganzen Bildschirms" in html
    assert "image_too_complex_for_provider" not in html
