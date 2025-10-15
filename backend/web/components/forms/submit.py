"""
Submit button component.

Keeps handling of loading labels and disabled state consistent.
"""

from typing import Optional

from ..base import Component


class SubmitButton(Component):
    """Primary form action button."""

    def __init__(
        self,
        label: str,
        *,
        loading_label: str = "Speichern...",
        is_loading: bool = False,
        disabled: bool = False,
        data_action: Optional[str] = None,
    ) -> None:
        self.label = label
        self.loading_label = loading_label
        self.is_loading = is_loading
        self.disabled = disabled
        self.data_action = data_action

    def render(self) -> str:
        label = self.loading_label if self.is_loading else self.label
        attrs = self.attributes(
            type="submit",
            class_="btn btn-primary",
            disabled=self.disabled or self.is_loading,
            data_action=self.data_action,
            aria_busy="true" if self.is_loading else None,
        )
        return f"<button {attrs}>{self.escape(label)}</button>"
