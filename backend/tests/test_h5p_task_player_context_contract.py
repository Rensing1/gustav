"""
Contract test: H5P player model must carry a stable task context id.

Why:
    We persist H5P progress in two places:
    1) H5P internal "finished data" (resume/state) via the H5P service, and
    2) GUSTAV `learning_submissions(kind='h5p')` so the Teacher Live matrix can
       show attempted/completed status.

    The H5P service can only write the Learning submission when it knows the
    (course_id, task_id) context. We attach this context to the H5P
    `integration.ajax.setFinished` URL in `/h5p/player/model` *when the model
    request includes*:
      - `course_id` and
      - `context_id` (we use `context_id == task_id` in GUSTAV).

    The Lumi webcomponent does not reliably pass `contextId` to the model load
    callback in all embed modes. Therefore the GUSTAV player JS must always
    include `context_id` derived from the known task id (dataset attribute).

Note:
    This is a source-level contract guard. It does not execute JavaScript.
"""

from __future__ import annotations

from pathlib import Path


def test_h5p_player_model_request_includes_context_id_from_task_id() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    js_path = repo_root / "backend" / "web" / "static" / "js" / "h5p_task_player.js"
    assert js_path.is_file(), f"Missing JS file: {js_path}"

    js = js_path.read_text(encoding="utf-8")

    # The model fetch must always include context_id derived from the task id
    # (so the H5P service can persist a Learning submission from finishedData).
    assert "context_id" in js
    assert "stableContextId" in js, "Expected a stable context id fallback variable"
    assert "taskId || contextId" in js or "taskId||contextId" in js
    assert (
        "url.searchParams.set('context_id', stableContextId)" in js
        or 'url.searchParams.set("context_id", stableContextId)' in js
    )
