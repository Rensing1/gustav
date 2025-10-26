"""
Unit Edit Form Component

Purpose: Simple SSR form to edit a learning unit (title, summary). Submits to
POST /units/{unit_id}/edit with CSRF. The API enforces author permissions.
"""
from typing import Optional, Dict
from components.base import Component
from .fields import TextInputField, TextAreaField
from .submit import SubmitButton


class UnitEditForm(Component):
    """Render an edit form for unit metadata (title, optional summary)."""

    def __init__(self, unit_id: str, csrf_token: str, values: Optional[Dict[str, str]] = None, error: Optional[str] = None) -> None:
        self.unit_id = unit_id
        self.csrf_token = csrf_token
        self.values = values or {}
        self.error = error

    def render(self) -> str:
        fields = [
            TextInputField("title", "Titel", required=True),
            TextAreaField("summary", "Zusammenfassung (optional)"),
        ]
        rendered_fields = [f.render(value=self.values.get(getattr(f, "field_id", ""), ""), class_="form-input") for f in fields]
        fields_html = "\n".join(rendered_fields)
        error_html = f'<div class="form-error" role="alert">{self.escape(self.error)}</div>' if self.error else ""
        submit_btn = SubmitButton("Speichern")
        return f"""
        <form method="post" action="/units/{self.escape(self.unit_id)}/edit">
            <input type="hidden" name="csrf_token" value="{self.escape(self.csrf_token)}">
            {fields_html}
            {error_html}
            <div class="form-actions">
                {submit_btn.render()}
            </div>
        </form>
        """

