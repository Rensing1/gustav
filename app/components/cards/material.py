"""
MaterialCard component.

Provides a reusable card layout for learning materials such as PDFs,
links, markdown notes, and interactive embeds (e.g. H5P).
"""

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from ..base import Component


@dataclass
class MaterialAction:
    """Represents a footer action for a material card."""

    label: str
    href: Optional[str] = None
    primary: bool = False
    target: Optional[str] = None
    is_button: bool = False
    data_action: Optional[str] = None
    extra_classes: Sequence[str] = field(default_factory=tuple)


class MaterialCard(Component):
    """
    Renders a material card with optional preview, metadata, and actions.

    Args:
        material_id: Stable identifier used for anchoring.
        title: Display title of the material.
        icon: Emoji or small icon string placed next to the title.
        badge: Optional badge text (e.g. file type).
        preview_html: HTML snippet rendered inside the expandable body.
        meta_items: Sequence of (label, value) tuples shown under the preview.
        actions: Footer actions such as download or preview buttons.
        collapse_label: Text used in the summary element trigger.
        is_open: Whether the details element should be expanded by default.
    """

    def __init__(
        self,
        material_id: str,
        title: str,
        icon: str = "📄",
        badge: Optional[str] = None,
        *,
        preview_html: str = "",
        meta_items: Optional[Sequence[Tuple[str, str]]] = None,
        actions: Optional[Iterable[MaterialAction]] = None,
        collapse_label: str = "Vorschau & Details",
        is_open: bool = True,
        footnote: Optional[str] = None,
    ) -> None:
        self.material_id = material_id
        self.title = title
        self.icon = icon
        self.badge = badge
        self.preview_html = preview_html
        self.meta_items = list(meta_items) if meta_items else []
        self.actions = list(actions) if actions else []
        self.collapse_label = collapse_label
        self.is_open = is_open
        self.footnote = footnote

    # ------------------------------------------------------------------ #
    # Render helpers
    # ------------------------------------------------------------------ #

    def render(self) -> str:
        """Render the complete card."""
        header_html = self._render_header()
        body_html = self._render_body()
        footer_html = self._render_footer()

        return (
            f'<article class="surface-panel material-entry" id="{self.escape(self.material_id)}">'
            f"{header_html}"
            f"{body_html}"
            f"{footer_html}"
            "</article>"
        )

    def _render_header(self) -> str:
        badge_html = (
            f'<span class="material-entry__badge">{self.escape(self.badge)}</span>'
            if self.badge
            else ""
        )
        return (
            '<header class="material-entry__header">'
            '<div class="material-entry__title">'
            f'<span class="material-entry__icon" aria-hidden="true">{self.escape(self.icon)}</span>'
            f'<h3 class="material-entry__name">{self.escape(self.title)}</h3>'
            "</div>"
            f"{badge_html}"
            "</header>"
        )

    def _render_body(self) -> str:
        meta_html = ""
        if self.meta_items:
            rows = "".join(
                f'<div class="material-entry__meta-item"><span class="material-entry__meta-label">{self.escape(label)}</span><span class="material-entry__meta-value">{self.escape(value)}</span></div>'
                for label, value in self.meta_items
            )
            meta_html = f'<div class="material-entry__meta">{rows}</div>'

        details_html = ""
        if self.preview_html:
            open_attr = " open" if self.is_open else ""
            details_html = (
                f'<details class="material-entry__details"{open_attr}>'
                '<summary class="material-entry__summary">'
                f'<span>{self.escape(self.collapse_label)}</span>'
                '<span class="material-entry__summary-icon" aria-hidden="true">▾</span>'
                "</summary>"
                f'<div class="material-entry__preview">{self.preview_html}</div>'
                "</details>"
            )

        return meta_html + details_html

    def _render_footer(self) -> str:
        if not self.actions and not self.footnote:
            return ""

        actions_html: List[str] = []
        for action in self.actions:
            classes = ["btn", "btn-primary" if action.primary else "btn-secondary"]
            classes.extend(action.extra_classes)
            class_attr = " ".join(classes)

            label = self.escape(action.label)

            if action.is_button or not action.href:
                button_attrs = self.attributes(
                    class_=class_attr,
                    type="button",
                    data_action=action.data_action,
                )
                actions_html.append(f"<button {button_attrs}>{label}</button>")
            else:
                link_attrs = self.attributes(
                    class_=class_attr,
                    href=action.href,
                    target=action.target,
                    data_action=action.data_action,
                )
                actions_html.append(f"<a {link_attrs}>{label}</a>")

        action_group_html = (
            '<div class="material-entry__actions">' + "".join(actions_html) + "</div>"
            if actions_html
            else ""
        )

        footnote_html = (
            f'<span class="material-entry__footnote">{self.escape(self.footnote)}</span>'
            if self.footnote
            else ""
        )

        return (
            '<footer class="material-entry__footer">'
            f"{action_group_html}"
            f"{footnote_html}"
            "</footer>"
        )
