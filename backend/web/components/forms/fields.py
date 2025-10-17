"""
Form field components.

These small components keep markup consistent across forms while staying
simple enough for students to understand.
"""

from typing import Optional

from ..base import Component


class FormField(Component):
    """Wrapper that renders label, input slot, help, and error text."""

    def __init__(
        self,
        field_id: str,
        label: str,
        *,
        required: bool = False,
        help_text: Optional[str] = None,
        error_text: Optional[str] = None,
        state: str = "default",
    ) -> None:
        self.field_id = field_id
        self.label = label
        self.required = required
        self.help_text = help_text
        self.error_text = error_text
        self.state = state

    def render(self, input_html: str) -> str:
        state_class = f" form-field--{self.state}" if self.state != "default" else ""
        required_marker = (
            '<span class="form-required" aria-hidden="true">*</span>'
            if self.required
            else ""
        )
        help_html = (
            f'<p class="form-help" id="{self.field_id}-help">{self.escape(self.help_text)}</p>'
            if self.help_text
            else ""
        )
        error_html = (
            f'<p class="form-error" role="alert" id="{self.field_id}-error">{self.escape(self.error_text)}</p>'
            if self.error_text
            else ""
        )

        label_attrs = self.attributes(
            for_=self.field_id,
            class_="form-label",
        )

        return (
            f'<div class="form-field{state_class}">'
            f"<label {label_attrs}>"
            f"{self.escape(self.label)}{required_marker}"
            "</label>"
            f"{input_html}"
            f"{help_html}"
            f"{error_html}"
            "</div>"
        )


class TextAreaField(FormField):
    """Convenience helper for textareas."""

    def render(self, value: str = "", rows: int = 5, **attrs: str) -> str:
        textarea_attrs = self.attributes(
            id=self.field_id,
            name=self.field_id,
            rows=str(rows),
            aria_describedby=f"{self.field_id}-help" if self.help_text else None,
            aria_invalid="true" if self.error_text else "false",
            **attrs,
        )
        input_html = f"<textarea {textarea_attrs}>{self.escape(value)}</textarea>"
        return super().render(input_html)


class FileUploadField(FormField):
    """File upload control with consistent styling."""

    def render(self, accept: Optional[str] = None, **attrs: str) -> str:
        input_attrs = self.attributes(
            id=self.field_id,
            name=self.field_id,
            type="file",
            aria_describedby=f"{self.field_id}-help" if self.help_text else None,
            aria_invalid="true" if self.error_text else "false",
            accept=accept,
            **attrs,
        )
        input_html = f"<input {input_attrs}>"
        return super().render(input_html)


class TextInputField(FormField):
    """Single-line text input field with consistent wrapper and labeling.

    Parameters:
        field_id: Name/id attribute for the input.
        label: Visible label text.
        input_type: One of 'text', 'email', 'password'. Defaults to 'text'.
        required: Whether the field is required.
        help_text: Optional help text shown below the field.
        error_text: Optional error message shown below the field.

    Behavior:
        - Renders <input> with appropriate ARIA attributes.
        - Wraps input using FormField to provide consistent structure.
    """

    def render(
        self,
        *,
        value: str = "",
        input_type: str = "text",
        autocomplete: Optional[str] = None,
        placeholder: Optional[str] = None,
        **attrs: str,
    ) -> str:
        input_attrs = self.attributes(
            id=self.field_id,
            name=self.field_id,
            type=input_type,
            value=value,
            autocomplete=autocomplete,
            placeholder=placeholder,
            aria_describedby=f"{self.field_id}-help" if self.help_text else None,
            aria_invalid="true" if self.error_text else "false",
            **attrs,
        )
        input_html = f"<input {input_attrs}>"
        return super().render(input_html)
