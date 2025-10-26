"""
Course Edit Form Component

Purpose: Simple form for editing a course via SSR. Uses CSRF and submits to
POST /courses/{course_id}/edit, which delegates to the API PATCH endpoint.
"""
from typing import Optional, Dict
from components.base import Component
from .fields import TextInputField
from .submit import SubmitButton


class CourseEditForm(Component):
    """Render an edit form for course metadata (title, subject, grade_level, term)."""

    def __init__(self, course_id: str, csrf_token: str, values: Optional[Dict[str, str]] = None, error: Optional[str] = None) -> None:
        self.course_id = course_id
        self.csrf_token = csrf_token
        self.values = values or {}
        self.error = error

    def render(self) -> str:
        fields = [
            TextInputField("title", "Kursname", required=True),
            TextInputField("subject", "Fach (optional)"),
            TextInputField("grade_level", "Klassenstufe (optional)"),
            TextInputField("term", "Halbjahr/Schuljahr (optional)"),
        ]
        rendered_fields = [
            f.render(value=self.values.get(f.field_id, ""), class_="form-input") for f in fields
        ]
        fields_html = "\n".join(rendered_fields)
        error_html = ""
        if self.error:
            error_html = f'<div class="form-error" role="alert">{self.escape(self.error)}</div>'
        submit_btn = SubmitButton("Speichern")
        return f"""
        <form method="post" action="/courses/{self.escape(self.course_id)}/edit">
            <input type="hidden" name="csrf_token" value="{self.escape(self.csrf_token)}">
            {fields_html}
            {error_html}
            <div class="form-actions">
                {submit_btn.render()}
            </div>
        </form>
        """
