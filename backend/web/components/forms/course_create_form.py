"""
Course Creation Form Component
"""
from typing import Optional
from components.base import Component
from .fields import TextInputField
from .submit import SubmitButton

class CourseCreateForm(Component):
    """
    A component that renders the form for creating a new course.
    It includes fields for title, subject, grade level, and term,
    along with CSRF protection and error display.
    """

    def __init__(self, csrf_token: str, error: Optional[str] = None, values: Optional[dict] = None):
        self.csrf_token = csrf_token
        self.error = error
        self.values = values or {}

    def render(self) -> str:
        """Renders the course creation form."""
        fields = [
            TextInputField("title", "Kursname", required=True),
            TextInputField("subject", "Fach (optional)"),
            TextInputField("grade_level", "Klassenstufe (optional)"),
            TextInputField("term", "Halbjahr/Schuljahr (optional)"),
        ]

        rendered_fields = []
        for field in fields:
            rendered_fields.append(
                field.render(
                    value=self.values.get(field.field_id, ""),
                    class_="form-input"
                )
            )

        error_html = ""
        if self.error:
            error_message = "Ein unbekannter Fehler ist aufgetreten."
            if self.error == "invalid_title":
                error_message = "Der Kursname ist ungültig. Er muss zwischen 1 und 200 Zeichen lang sein."
            elif self.error == "backend_error":
                error_message = "Der Kurs konnte aufgrund eines Serverfehlers nicht erstellt werden."
            
            error_html = f'<div class="form-error" role="alert">{self.escape(error_message)}</div>'

        submit_btn = SubmitButton("Kurs anlegen")

        all_form_fields_html = "\n".join(rendered_fields)

        form_html = f"""
        <form method="post" action="/courses" class="course-create-form" hx-post="/courses" hx-target="#course-list-section" hx-swap="outerHTML">
            <input type="hidden" name="csrf_token" value="{self.escape(self.csrf_token)}">
            {all_form_fields_html}
            {error_html}
            <div class="form-actions">
                {submit_btn.render()}
            </div>
        </form>
        """
        return form_html
