"""Submission-kind rules for the Learning bounded context."""

from __future__ import annotations

from backend.storage.mime_types import FILIUS_FLS_MIME, MAKECODE_HEX_MIME, SCRATCH_SB3_MIME


def validate_task_submission_kind(*, task_kind: str, submission_kind: str, mime_type: str | None) -> None:
    """Enforce which submission payloads are valid for a task kind.

    Why:
        Task kinds such as Scratch, Calliope, Filius and H5P have stricter
        payload requirements than native text/image tasks. This policy keeps
        those business rules in the Learning context so web routes and
        repositories can share the same validation without depending on each
        other's private helpers.

    Parameters:
        task_kind: Learning task type, for example `visual`, `scratch`,
            `calliope`, `filius` or `h5p`. Empty values behave like `native`.
        submission_kind: API submission kind such as `text`, `image`, `file`
            or `h5p`.
        mime_type: Declared MIME type for file/image submissions.

    Behavior:
        Raises `ValueError` with a stable API detail code when the payload kind
        does not match the task kind.

    Permissions:
        None. Callers must already know the authorized task kind for the
        current student and task.
    """
    task_kind = str(task_kind or "native").strip().lower()
    submission_kind = str(submission_kind or "").strip().lower()
    mime = str(mime_type or "").strip().lower()

    if task_kind == "h5p":
        if submission_kind != "h5p":
            raise ValueError("invalid_input")
        return
    if task_kind == "visual":
        if submission_kind not in ("image", "file"):
            raise ValueError("invalid_input")
        if submission_kind == "file" and mime in {SCRATCH_SB3_MIME, MAKECODE_HEX_MIME, FILIUS_FLS_MIME}:
            raise ValueError("invalid_file_payload")
        return
    if task_kind == "scratch":
        if submission_kind != "file":
            raise ValueError("invalid_input")
        if mime != SCRATCH_SB3_MIME:
            raise ValueError("invalid_file_payload")
        return
    if task_kind == "calliope":
        if submission_kind != "file":
            raise ValueError("invalid_input")
        if mime != MAKECODE_HEX_MIME:
            raise ValueError("invalid_file_payload")
        return
    if task_kind == "filius":
        if submission_kind != "file":
            raise ValueError("invalid_input")
        if mime != FILIUS_FLS_MIME:
            raise ValueError("invalid_file_payload")
        return

    if submission_kind == "h5p":
        raise ValueError("invalid_h5p_payload")
    if submission_kind == "file" and mime in {SCRATCH_SB3_MIME, MAKECODE_HEX_MIME, FILIUS_FLS_MIME}:
        raise ValueError("invalid_file_payload")


__all__ = ["validate_task_submission_kind"]
