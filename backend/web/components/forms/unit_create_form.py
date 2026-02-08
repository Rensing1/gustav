"""
Unit Creation Form Component
"""
from typing import Optional
from components.base import Component
from .fields import TextInputField, TextAreaField, SelectField
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
        unit_type_field = SelectField(
            "unit_type",
            "Typ der Lerneinheit",
            required=True,
            help_text=(
                "Linear: Abschnitte werden nacheinander freigeschaltet. "
                "Modular: Abschnitte werden als Module in einem Lernpfad (Graph) organisiert."
            ),
        )

        # In a real app, you'd have more specific error messages
        error_html = f'<div class="form-error" role="alert">{self.escape(self.error)}</div>' if self.error else ""

        submit_btn = SubmitButton("Lerneinheit anlegen")

        unit_type = str(self.values.get("unit_type") or "linear").strip().lower()

        form_html = f"""
        <form method="post" action="/units" hx-post="/units" hx-target="#unit-list-section" hx-swap="outerHTML">
            <input type="hidden" name="csrf_token" value="{self.escape(self.csrf_token)}">
            {title_field.render(value=self.values.get("title", ""), class_="form-input")}
            {summary_field.render(value=self.values.get("summary", ""), class_="form-textarea", rows=3)}
            {unit_type_field.render(
                options=[("linear", "Linear"), ("modular", "Modular")],
                value=unit_type,
                class_="form-input",
            )}
            {error_html}
            <div class="form-actions">
                {submit_btn.render()}
            </div>
        </form>
        """
        return form_html
