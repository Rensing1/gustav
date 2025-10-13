"""
TaskCard component.

Encapsulates the visual structure for learning tasks, combining
instructions, submission history, feedback messages, and the active form.
"""

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from ..base import Component


@dataclass
class HistoryEntry:
    """Represents a single submission attempt within the task card."""

    label: str
    timestamp: str
    content_html: str = ""
    feedback_html: str = ""
    status_html: str = ""
    expanded: bool = False


@dataclass
class TaskMetaItem:
    """Key/value metadata shown under the instruction text."""

    label: str
    value: str


class TaskCard(Component):
    """
    Renders a task card with instruction, history accordion, and submit form.

    Args:
        task_id: Stable identifier for anchor navigation.
        title: Task title.
        instruction_html: Rich HTML description of the task.
        status_badge: Optional badge text (e.g. "Neu" or "In Bearbeitung").
        attempts_info: Short text describing remaining attempts.
        meta_items: Extra metadata shown in a definition list.
        history_entries: Past submissions rendered inside collapsible panels.
        feedback_banner_html: Optional banner shown above the form.
        form_html: HTML for the active submission form.
        form_actions_html: Optional footer with form-related actions.
    """

    def __init__(
        self,
        task_id: str,
        title: str,
        *,
        instruction_html: str,
        status_badge: Optional[str] = None,
        attempts_info: Optional[str] = None,
        meta_items: Optional[Sequence[TaskMetaItem]] = None,
        history_entries: Optional[Iterable[HistoryEntry]] = None,
        feedback_banner_html: Optional[str] = None,
        form_html: str = "",
        form_actions_html: Optional[str] = None,
    ) -> None:
        self.task_id = task_id
        self.title = title
        self.status_badge = status_badge
        self.instruction_html = instruction_html
        self.attempts_info = attempts_info
        self.meta_items = list(meta_items) if meta_items else []
        self.history_entries = list(history_entries) if history_entries else []
        self.feedback_banner_html = feedback_banner_html
        self.form_html = form_html
        self.form_actions_html = form_actions_html

    def render(self) -> str:
        header_html = self._render_header()
        instruction_html = self._render_instruction()
        history_html = self._render_history()
        form_html = self._render_form()

        return (
            f'<section class="surface-panel task-panel" id="{self.escape(self.task_id)}">'
            f"{header_html}"
            f"{instruction_html}"
            f"{history_html}"
            f"{form_html}"
            "</section>"
        )

    def _render_header(self) -> str:
        badge_html = (
            f'<span class="task-panel__badge">{self.escape(self.status_badge)}</span>'
            if self.status_badge
            else ""
        )
        attempts_html = (
            f'<p class="task-panel__attempts">{self.escape(self.attempts_info)}</p>'
            if self.attempts_info
            else ""
        )

        return (
            '<header class="task-panel__header">'
            '<div class="task-panel__title">'
            f'<h3 class="task-panel__name">{self.escape(self.title)}</h3>'
            f"{badge_html}"
            "</div>"
            f"{attempts_html}"
            "</header>"
        )

    def _render_instruction(self) -> str:
        meta_html = "".join(
            f'<div class="task-panel__meta-item"><span class="task-panel__meta-label">{self.escape(item.label)}</span><span class="task-panel__meta-value">{self.escape(item.value)}</span></div>'
            for item in self.meta_items
        )
        meta_block = (
            f'<div class="task-panel__meta">{meta_html}</div>' if self.meta_items else ""
        )

        return (
            '<section class="task-panel__instruction">'
            f'<div class="task-panel__instruction-text">{self.instruction_html}</div>'
            f"{meta_block}"
            "</section>"
        )

    def _render_history(self) -> str:
        if not self.history_entries:
            return ""

        entries_html: List[str] = []
        for index, entry in enumerate(self.history_entries):
            open_attr = " open" if entry.expanded else ""
            content_parts = [
                entry.content_html,
                entry.feedback_html,
                entry.status_html,
            ]
            inner_html = "".join(part for part in content_parts if part)

            entries_html.append(
                f'<details class="task-panel__history-entry"{open_attr}>'
                f'<summary class="task-panel__history-summary">'
                f'<span class="task-panel__history-label">{self.escape(entry.label)}</span>'
                f'<span class="task-panel__history-timestamp">{self.escape(entry.timestamp)}</span>'
                "</summary>"
                f'<div class="task-panel__history-body">{inner_html}</div>'
                "</details>"
            )

        return '<section class="task-panel__history">' + "".join(entries_html) + "</section>"

    def _render_form(self) -> str:
        banner_html = (
            f'<div class="task-panel__feedback">{self.feedback_banner_html}</div>'
            if self.feedback_banner_html
            else ""
        )

        actions_html = (
            f'<div class="task-panel__form-actions">{self.form_actions_html}</div>'
            if self.form_actions_html
            else ""
        )

        return (
            '<section class="task-panel__form">'
            f"{banner_html}"
            f'<div class="task-panel__form-body">{self.form_html}</div>'
            f"{actions_html}"
            "</section>"
        )
