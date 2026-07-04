"""Rendering helpers for retired learning submission history SSR fragments."""

from __future__ import annotations

from typing import Any, Mapping

from backend.storage.mime_types import PDF_MIME
from backend.web.components import FilePreview, HistoryEntry
from backend.web.components.base import Component
from backend.web.components.markdown import render_markdown_safe
from backend.web.evidence_rendering import render_submission_text_html
from backend.web.ssr_helpers import is_analysis_in_progress


def _build_history_entry_from_record(
    record: dict[str, Any],
    *,
    course_id: str,
    task_id: str,
    index: int,
    open_attempt_id: str,
) -> HistoryEntry:
    """Render a submission record into a HistoryEntry for the learner history accordion.

    Why:
        Legacy Learning history fragments still need deterministic rendering in
        tests while the FastAPI product HTML routes are being retired.

    Permissions:
        Caller must ensure the current session may view this submission
        (student ownership or teacher course access). This helper performs no
        authorization checks.
    """

    if not isinstance(record, dict):
        return HistoryEntry(
            label=f"Versuch #{index + 1}",
            timestamp="",
            content_html='<div class="analysis-text"><p class="text-muted">Keine Daten vorhanden.</p></div>',
            expanded=(index == 0),
        )

    label = f"Versuch #{record.get('attempt_nr', '')}"
    timestamp = str(record.get("created_at") or "")
    submission_id = str(record.get("id") or "")
    expanded = bool(open_attempt_id and submission_id == open_attempt_id) or (not open_attempt_id and index == 0)

    if str(record.get("kind") or "") == "h5p":
        raw = record.get("score_raw")
        max_ = record.get("score_max")
        score_html = '<p class="text-muted">Keine Punkte verfügbar.</p>'
        try:
            if raw is not None and max_ is not None:
                score_html = f"<p><strong>Punkte:</strong> {Component.escape(str(int(raw)))}/{Component.escape(str(int(max_)))}</p>"
        except Exception:
            score_html = '<p class="text-muted">Keine Punkte verfügbar.</p>'
        return HistoryEntry(
            label=label,
            timestamp=timestamp,
            content_html=f'<div class="analysis-text">{score_html}</div>',
            expanded=expanded,
            submission_id=submission_id,
        )

    artifact_html = _render_submission_artifact_container(
        record,
        course_id=course_id,
        task_id=task_id,
        submission_id=submission_id,
    )
    has_artifact = bool(artifact_html)
    text_container_html = _render_submission_text_container(
        record,
        submission_id=submission_id,
        has_artifact=has_artifact,
        oob=False,
    )
    result_container_html = _render_submission_result_container(record, submission_id=submission_id, oob=False)

    content_html = '<div class="analysis-text">' + artifact_html + text_container_html + "</div>"
    feedback_html = result_container_html

    return HistoryEntry(
        label=label,
        timestamp=timestamp,
        content_html=content_html,
        feedback_html=feedback_html,
        status_html="",
        expanded=expanded,
        submission_id=submission_id,
    )


def _render_analysis_criteria_section(analysis: Mapping[str, object]) -> str:
    """Render the per-criterion block for criteria.v1/v2 payloads."""

    schema_tag = analysis.get("schema")
    if schema_tag not in {"criteria.v1", "criteria.v2"}:
        return ""

    criteria_list = analysis.get("criteria_results")
    if not isinstance(criteria_list, list):
        return ""

    cards: list[str] = []
    for item in criteria_list:
        if not isinstance(item, dict):
            continue
        raw_title = item.get("criterion")
        if not raw_title:
            continue

        title = Component.escape(str(raw_title))
        explanation_html = ""
        if item.get("explanation_md"):
            explanation_html = render_markdown_safe(str(item["explanation_md"]))
            if explanation_html:
                explanation_html = f'<div class="analysis-criterion__body">{explanation_html}</div>'

        badge_html = ""
        raw_score = item.get("score")
        if raw_score is not None:
            score_clamped, max_score, badge_variant = _normalise_criterion_score(raw_score, item.get("max_score"))
            if score_clamped is not None:
                badge_html = (
                    f'<span class="badge {badge_variant}" aria-label="Punkte {score_clamped} von {max_score}">'
                    f"{score_clamped}/{max_score}"
                    f'<span class="sr-only"> Punkte {score_clamped} von {max_score}</span>'
                    "</span>"
                )

        header_parts = [f'<span class="analysis-criterion__title">{title}</span>']
        if badge_html:
            header_parts.append(badge_html)
        header_html = '<header class="analysis-criterion__header">' + "".join(header_parts) + "</header>"
        cards.append(f'<article class="analysis-criterion">{header_html}{explanation_html}</article>')

    if not cards:
        return ""

    return (
        '<section class="analysis-criteria">'
        '<p class="analysis-criteria__heading"><strong>Auswertung</strong></p>'
        + "".join(cards)
        + "</section>"
    )


def _render_submission_telemetry(record: Mapping[str, Any]) -> str:
    """Render telemetry fields for legacy tests without exposing raw provider details."""

    try:
        attempts = int(record.get("vision_attempts") or 0)
    except (TypeError, ValueError):
        attempts = 0
    attempts = max(0, attempts)
    last_attempt_raw = str(record.get("feedback_last_attempt_at") or "").strip()
    vision_error = str(record.get("vision_last_error") or "").strip()
    feedback_error = str(record.get("feedback_last_error") or "").strip()

    attempts_item = (
        '<li data-testid="vision-attempts">'
        '<span class="analysis-telemetry__label">Vision-Versuche</span>'
        f'<span class="analysis-telemetry__value">{Component.escape(str(attempts))}</span>'
        "</li>"
    )
    last_attempt_value = Component.escape(last_attempt_raw) if last_attempt_raw else "–"
    feedback_time_item = (
        '<li data-testid="feedback-last-attempt">'
        '<span class="analysis-telemetry__label">Letzter Feedback-Versuch</span>'
        f'<span class="analysis-telemetry__value">{last_attempt_value}</span>'
        "</li>"
    )
    items = [attempts_item, feedback_time_item]
    if vision_error:
        items.append(
            '<li data-testid="vision-last-error">'
            '<span class="analysis-telemetry__label text-muted">Vision-Fehler (nur Lehrkraft)</span>'
            f'<span class="analysis-telemetry__value">{Component.escape(vision_error)}</span>'
            "</li>"
        )
    if feedback_error:
        items.append(
            '<li data-testid="feedback-last-error">'
            '<span class="analysis-telemetry__label text-muted">Feedback-Fehler (nur Lehrkraft)</span>'
            f'<span class="analysis-telemetry__value">{Component.escape(feedback_error)}</span>'
            "</li>"
        )

    return (
        '<section class="analysis-telemetry" aria-label="Analysefortschritt">'
        '<p class="analysis-telemetry__heading"><strong>Analysefortschritt</strong></p>'
        '<ul class="analysis-telemetry__list">'
        + "".join(items)
        + "</ul>"
        "</section>"
    )


def _normalise_criterion_score(raw_score: object, raw_max_score: object) -> tuple[int | None, int, str]:
    """Clamp scores to 0..10 and choose a badge variant; returns None when score is invalid."""

    try:
        score_int = int(raw_score)
    except (TypeError, ValueError):
        return None, 10, "badge-warning"

    score_clamped = max(0, min(10, score_int))
    max_score = raw_max_score if isinstance(raw_max_score, int) and raw_max_score >= 1 else 10

    if score_clamped <= 3:
        badge_variant = "badge-error"
    elif score_clamped <= 7:
        badge_variant = "badge-warning"
    else:
        badge_variant = "badge-success"

    return score_clamped, max_score, badge_variant


def _render_history_entries_html(entries: list[HistoryEntry]) -> str:
    """Render history entries into the accordion HTML fragment."""

    parts: list[str] = []
    for entry in entries:
        open_attr = " open" if entry.expanded else ""
        submission_attr = (
            f' data-submission-id="{Component.escape(entry.submission_id)}"' if entry.submission_id else ""
        )
        inner_segments = [entry.content_html, entry.feedback_html, entry.status_html]
        inner_html = "".join(segment for segment in inner_segments if segment)
        parts.append(
            f'<details{open_attr}{submission_attr} class="task-panel__history-entry">'
            f'<summary class="task-panel__history-summary">'
            f'<span class="task-panel__history-label">{Component.escape(entry.label)}</span>'
            f'<span class="task-panel__history-timestamp">{Component.escape(entry.timestamp)}</span>'
            "</summary>"
            f'<div class="task-panel__history-body">{inner_html}</div>'
            "</details>"
        )
    return '<section class="task-panel__history">' + "".join(parts) + "</section>"


def _render_analysis_in_progress_hint() -> str:
    """Render a small spinner hint shown while submission analysis runs."""

    return (
        '<div class="status-chip" role="status" aria-live="polite">'
        '<span class="spinner spinner--sm" aria-hidden="true"></span>'
        '<span class="status-chip__text">Analyse läuft … wir aktualisieren gleich.</span>'
        "</div>"
    )


def _is_legacy_extracted_text_placeholder(text: str) -> bool:
    """Return True when the text matches our legacy OCR/PDF placeholder stub."""

    t = (text or "").strip()
    return t.startswith("OCR placeholder for ") or t.startswith("PDF text placeholder for ")


def _render_task_history_poll_element(*, course_id: str, task_id: str, active: bool) -> str:
    """Render the HTMX poll element responsible for granular OOB updates."""

    poll_id = f"task-history-poll-{Component.escape(task_id)}"
    if not active:
        return f'<div id="{poll_id}"></div>'
    return (
        f'<div id="{poll_id}"'
        f' hx-get="/learning/courses/{course_id}/tasks/{task_id}/history/poll"'
        f' hx-trigger="every 10s" hx-target="this" hx-swap="outerHTML"></div>'
    )


def _render_submission_text_container(
    record: Mapping[str, Any],
    *,
    submission_id: str,
    has_artifact: bool,
    oob: bool,
) -> str:
    """Render the extracted text block of a submission."""

    analysis = record.get("analysis_json")
    text_src = str(record.get("text_body") or "")
    if not text_src.strip() and isinstance(analysis, dict):
        extracted = str(analysis.get("text") or "").strip()
        if extracted and not _is_legacy_extracted_text_placeholder(extracted):
            text_src = extracted

    text_html = render_submission_text_html(text_src=text_src)
    if not text_html and not has_artifact:
        text_html = '<p class="text-muted">Keine Antwort hinterlegt.</p>'

    oob_attr = ' hx-swap-oob="true"' if oob else ""
    return f'<div id="submission-text-{Component.escape(submission_id)}"{oob_attr}>{text_html}</div>'


def _render_submission_result_container(record: Mapping[str, Any], *, submission_id: str, oob: bool) -> str:
    """Render the status/feedback/result block of a submission."""

    status = str(record.get("analysis_status") or "")
    if is_analysis_in_progress(status):
        inner = _render_analysis_in_progress_hint()
    else:
        inner = _render_submission_result_static_html(record, submission_id=submission_id)

    oob_attr = ' hx-swap-oob="true"' if oob else ""
    return f'<div id="submission-result-{Component.escape(submission_id)}"{oob_attr}>{inner}</div>'


_IMAGE_TOO_COMPLEX_FOR_PROVIDER_MESSAGE = (
    "Das Bild ist wahrscheinlich zu groß oder zu komplex. Bitte lade einen kleineren Ausschnitt hoch, "
    "zum Beispiel nur die Zeichnung statt des ganzen Bildschirms."
)


def _public_submission_failure_message(record: Mapping[str, Any]) -> str:
    """Return a learner-facing failure message without exposing internal provider codes."""

    detail = str(record.get("vision_last_error") or record.get("feedback_last_error") or "").strip()
    if detail == "image_too_complex_for_provider":
        return _IMAGE_TOO_COMPLEX_FOR_PROVIDER_MESSAGE
    return detail


def _render_submission_result_static_html(record: Mapping[str, Any], *, submission_id: str) -> str:
    """Render the final feedback/error content for a submission."""

    status = str(record.get("analysis_status") or "")
    created_at = str(record.get("created_at") or "")
    created_at_html = Component.escape(created_at) if created_at else "–"
    submission_id_html = Component.escape(str(submission_id))

    analysis = record.get("analysis_json")
    feedback_src = record.get("feedback_md") or record.get("feedback")

    criteria_html = ""
    if status != "failed" and isinstance(analysis, dict):
        criteria_html = _render_analysis_criteria_section(analysis)

    sections: list[str] = []
    if status == "failed":
        code_raw = record.get("error_code") or "processing_failed"
        code_html = Component.escape(str(code_raw))
        detail = _public_submission_failure_message(record)
        detail_html = (
            Component.escape(str(detail)) if detail else '<span class="text-muted">Keine Details verfügbar.</span>'
        )
        sections.append(
            '<section class="analysis-error">'
            '<p class="analysis-error__heading"><strong>Analyse fehlgeschlagen</strong></p>'
            f'<p class="analysis-error__code"><code>{code_html}</code></p>'
            f'<p class="analysis-error__message">{detail_html}</p>'
            f'<p class="analysis-error__meta"><strong>Abgabe-ID:</strong> <code>{submission_id_html}</code></p>'
            f'<p class="analysis-error__meta"><strong>Zeitstempel:</strong> {created_at_html}</p>'
            "</section>"
        )
        return "".join(sections)

    has_feedback = bool(feedback_src)
    has_criteria = bool(criteria_html)

    if has_feedback:
        criteria_block = ""
        if has_criteria:
            criteria_block = (
                '<details class="analysis-feedback__details">'
                '<summary class="analysis-feedback__summary">'
                "<span>Auswertung anzeigen</span>"
                '<span class="analysis-feedback__summary-icon" aria-hidden="true">▾</span>'
                "</summary>"
                f"{criteria_html}"
                "</details>"
            )
        sections.append(
            '<section class="analysis-feedback">'
            '<p class="analysis-feedback__heading"><strong>Rückmeldung</strong></p>'
            f"{render_markdown_safe(str(feedback_src))}"
            f"{criteria_block}"
            "</section>"
        )
    elif has_criteria:
        sections.append(
            '<details class="analysis-feedback__details">'
            '<summary class="analysis-feedback__summary">'
            "<span>Auswertung anzeigen</span>"
            '<span class="analysis-feedback__summary-icon" aria-hidden="true">▾</span>'
            "</summary>"
            f"{criteria_html}"
            "</details>"
        )

    return "".join(sections)


def _render_submission_artifact_container(
    record: Mapping[str, Any],
    *,
    course_id: str,
    task_id: str,
    submission_id: str,
) -> str:
    """Render the stable artifact preview block for a submission."""

    kind = str(record.get("kind") or "")
    file_url = str(record.get("file_url") or "").strip()
    if not file_url or kind not in {"image", "file"}:
        return ""
    mime = str(record.get("mime_type") or "").lower().strip()

    try:
        preview_html = FilePreview(
            url=file_url,
            mime=mime,
            title="Deine Abgabe",
            alt="Deine Abgabe",
            max_height="480px",
        ).render()
    except Exception:
        preview_html = ""
    if not preview_html:
        return ""

    safe_sid = Component.escape(submission_id)
    container_id = f"submission-artifact-{safe_sid}"

    open_tab_link = ""
    if mime == PDF_MIME:
        safe_url = Component.escape(file_url)
        open_tab_link = (
            f'<a class="btn btn-sm" href="{safe_url}" target="_blank" rel="noopener">In neuem Tab öffnen</a>'
        )

    return f'<div id="{container_id}">{preview_html}{open_tab_link}</div>'


def _strip_task_history_outer_wrapper(html: str) -> str:
    """Strip the outer ``section`` wrapper from rendered history HTML."""

    if not html.startswith("<section"):
        return html
    try:
        start = html.find(">") + 1
        end = html.rfind("</section>")
        return html[start:end]
    except Exception:
        return html
