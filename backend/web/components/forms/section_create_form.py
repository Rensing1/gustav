"""
Section Creation Form Component
"""
from typing import Optional
from components.base import Component
from .fields import TextInputField
from .submit import SubmitButton

class SectionCreateForm(Component):
    """
    A component that renders the form for creating a new section in a unit.
    """

    def __init__(
        self,
        unit_id: str,
        csrf_token: str,
        error: Optional[str] = None,
        values: Optional[dict] = None,
        noun: str = "Abschnitt",
    ):
        self.unit_id = unit_id
        self.csrf_token = csrf_token
        self.error = error
        self.values = values or {}
        self.noun = noun

    def render(self) -> str:
        noun = (self.noun or "Abschnitt").strip() or "Abschnitt"
        title_field = TextInputField("title", f"Titel des {noun}", required=True)
        error_html = f'<div class="form-error" role="alert">{self.escape(self.error)}</div>' if self.error else ""
        submit_btn = SubmitButton(f"{noun} hinzufügen")
        safe_unit_id = self.escape(self.unit_id)

        form_html = f"""
        <form method="post" action="/units/{safe_unit_id}/sections" hx-post="/units/{safe_unit_id}/sections" hx-target="#section-list-section" hx-swap="outerHTML">
            <input type="hidden" name="csrf_token" value="{self.escape(self.csrf_token)}">
            {title_field.render(value=self.values.get("title", ""), class_="form-input")}
            {error_html}
            <div class="form-actions">
                {submit_btn.render()}
            </div>
        </form>
        """
        return form_html
