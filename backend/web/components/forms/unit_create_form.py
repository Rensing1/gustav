"""
Unit Creation Form Component
"""
from typing import Optional
from components.base import Component
from .fields import TextInputField, TextAreaField
from .submit import SubmitButton

class UnitCreateForm(Component):
    """
    A component that renders the form for creating a new learning unit.
    """

    def __init__(self, csrf_token: str, error: Optional[str] = None, values: Optional[dict] = None):
        self.csrf_token = csrf_token
        self.error = error
        self.values = values or {}

    def render(self) -> str:
        """Renders the unit creation form."""
        title_field = TextInputField("title", "Titel der Lerneinheit", required=True)
        summary_field = TextAreaField("summary", "Kurze Zusammenfassung (optional)")

        # In a real app, you'd have more specific error messages
        error_html = f'<div class="form-error" role="alert">{self.escape(self.error)}</div>' if self.error else ""

        submit_btn = SubmitButton("Lerneinheit anlegen")

        form_html = f"""
        <form method="post" action="/units" hx-post="/units" hx-target="#unit-list-section" hx-swap="outerHTML">
            <input type="hidden" name="csrf_token" value="{self.escape(self.csrf_token)}">
            {title_field.render(value=self.values.get("title", ""), class_="form-input")}
            {summary_field.render(value=self.values.get("summary", ""), class_="form-textarea", rows=3)}
            {error_html}
            <div class="form-actions">
                {submit_btn.render()}
            </div>
        </form>
        """
        return form_html
