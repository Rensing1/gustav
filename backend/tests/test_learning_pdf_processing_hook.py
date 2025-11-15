import os
import types
import uuid
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

from backend.web import main


def _student_session():
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    return student


@pytest.mark.anyio
async def test_pdf_submission_triggers_processing_in_dev(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    student = _student_session()
    course_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    # Arrange: enable dev upload stub and verification root
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))

    # Create a fake uploaded PDF file at the expected storage_key
    storage_key = f"learning/{course_id}/{task_id}/{student.sub}/test.pdf".lower()  # type: ignore[attr-defined]
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = b"%PDF-1.4\n%fake\n"
    target.write_bytes(pdf_bytes)

    # Patch pipeline to observe calls
    called = {"n": 0}

    def _dummy_process(pdf_bytes: bytes):
        called["n"] += 1
        # Return shape compatible with our pipeline (pages, meta)
        return ([], types.SimpleNamespace(page_count=1, dpi=300, grayscale=True, used_annotations=True))

    import sys as _sys
    monkeypatch.setitem(_sys.modules, "backend.vision.pipeline", types.SimpleNamespace(process_pdf_bytes=_dummy_process))  # type: ignore

    # Act: submit PDF metadata
    from hashlib import sha256
    digest = sha256(pdf_bytes).hexdigest()
    payload = {
        "kind": "file",
        "storage_key": storage_key,
        "mime_type": "application/pdf",
        "size_bytes": target.stat().st_size,
        "sha256": digest,
    }

    # Avoid touching the real DB layer: stub the use case to return a minimal submission
    class _FakeUC:
        def __init__(self, *a, **k):
            pass

        def execute(self, input_data):
            return {"id": str(uuid.uuid4()), "analysis_status": "pending"}

    # Patch CreateSubmissionUseCase on both module aliases to avoid alias drift
    # in full-suite runs (router/global lookup stays consistent at call time).
    from backend.web.routes import learning as learning_routes
    monkeypatch.setattr(learning_routes, "CreateSubmissionUseCase", _FakeUC)
    try:
        import importlib as _importlib
        lr_alias = _importlib.import_module("routes.learning")
        monkeypatch.setattr(lr_alias, "CreateSubmissionUseCase", _FakeUC, raising=False)
    except Exception:
        pass
    # Fallback: also patch the real UC class' execute method to a no-op
    # returning a minimal pending submission, so even if an alias drifts,
    # the call site will not raise PermissionError.
    try:
        import backend.learning.usecases.submissions as _uc_mod  # type: ignore
        monkeypatch.setattr(
            _uc_mod.CreateSubmissionUseCase,
            "execute",
            lambda self, input_data: {"id": str(uuid.uuid4()), "analysis_status": "pending"},
            raising=False,
        )
    except Exception:
        pass

    # Ensure we are evaluated under dev semantics for this request only
    # (guards against sporadic prod detection in a full suite sequence)
    main.SETTINGS.override_environment("dev")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.post(f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions", json=payload, headers={"Origin": "http://test"})

    # If this ever fails in a full run, surface diagnostics for triage
    assert r.status_code == 202, (
        f"unexpected status={r.status_code}, "
        f"csrf={r.headers.get('X-CSRF-Diag')}, submissions={r.headers.get('X-Submissions-Diag')}"
    )
    # Ensure our processing hook was invoked exactly once
    assert called["n"] == 1
