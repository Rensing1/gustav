"""
On-page navigation component.

Renders a compact list of anchor links that allow quick jumps to cards
within the current page (e.g. materials or tasks).
"""

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

from .base import Component


@dataclass
class OnPageNavItem:
    """Single entry in the on-page navigation."""

    anchor: str
    label: str
    icon: Optional[str] = None
    description: Optional[str] = None
    active: bool = False
    extra_classes: Sequence[str] = field(default_factory=tuple)


class OnPageNavigation(Component):
    """Renders a horizontal or vertical list of anchor links."""

    def __init__(
        self,
        items: Iterable[OnPageNavItem],
        *,
        orientation: str = "horizontal",
    ) -> None:
        self.items = list(items)
        self.orientation = orientation

    def render(self) -> str:
        classes = ["onpage-nav", f"onpage-nav--{self.orientation}"]
        list_items: List[str] = []

        for item in self.items:
            li_classes = ["onpage-nav__item"]
            li_classes.extend(item.extra_classes)
            if item.active:
                li_classes.append("is-active")

            icon_html = (
                f'<span class="onpage-nav__icon" aria-hidden="true">{self.escape(item.icon)}</span>'
                if item.icon
                else ""
            )
            description_html = (
                f'<span class="onpage-nav__description">{self.escape(item.description)}</span>'
                if item.description
                else ""
            )

            link_attrs = self.attributes(
                class_="onpage-nav__link",
                href=f"#{item.anchor}",
                data_action="jump-to-section",
            )

            list_items.append(
                f'<li class="{" ".join(li_classes)}">'
                f"<a {link_attrs}>"
                f"{icon_html}"
                f'<span class="onpage-nav__label">{self.escape(item.label)}</span>'
                f"{description_html}"
                "</a>"
                "</li>"
            )

        list_html = "".join(list_items)
        return (
            f'<nav class="{" ".join(classes)}" aria-label="Seiteninhalte">'
            f"<ul>{list_html}</ul>"
            "</nav>"
        )
