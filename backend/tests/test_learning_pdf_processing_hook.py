import os
import types
import uuid
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport

from backend.web import main
from backend.tests.runtime_auth_helpers import install_session_store


def _student_session(monkeypatch: pytest.MonkeyPatch):
    store = install_session_store(monkeypatch, main)
    return store.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])


@pytest.mark.anyio
@pytest.mark.parametrize("use_explicit_root", [True, False])
async def test_pdf_submission_triggers_processing_in_dev(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    use_explicit_root: bool,
):
    student = _student_session(monkeypatch)
    course_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    # Arrange: enable dev upload stub and choose the same local root the upload
    # validation path will use.
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    if use_explicit_root:
        monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
        upload_root = tmp_path
    else:
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("STORAGE_VERIFY_ROOT", raising=False)
        upload_root = tmp_path / ".tmp" / "dev_uploads"

    # Create a fake uploaded PDF file at the expected storage_key
    storage_key = f"learning/{course_id}/{task_id}/{student.sub}/test.pdf".lower()  # type: ignore[attr-defined]
    target = upload_root / storage_key
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
    fake_repo = types.SimpleNamespace(get_task_kind_for_student=lambda **_: "native")
    monkeypatch.setattr(learning_routes, "_get_repo", lambda: fake_repo)
    monkeypatch.setattr(learning_routes, "CreateSubmissionUseCase", _FakeUC)
    for route in main.app.routes:
        endpoint = getattr(route, "endpoint", None)
        if getattr(endpoint, "__name__", "") == "create_submission":
            monkeypatch.setitem(endpoint.__globals__, "_get_repo", lambda: fake_repo)
            monkeypatch.setitem(endpoint.__globals__, "CreateSubmissionUseCase", _FakeUC)
    try:
        import importlib as _importlib
        lr_alias = _importlib.import_module("routes.learning")
        monkeypatch.setattr(lr_alias, "_get_repo", lambda: fake_repo, raising=False)
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
    main.RUNTIME.settings.override_environment("dev")

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


@pytest.mark.anyio
async def test_pdf_submission_does_not_trigger_processing_in_prod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Even with STORAGE_VERIFY_ROOT set, the PDF hook must not run in prod-like envs."""
    student = _student_session(monkeypatch)
    course_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))

    storage_key = f"learning/{course_id}/{task_id}/{student.sub}/test.pdf".lower()  # type: ignore[attr-defined]
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = b"%PDF-1.4\n%fake\n"
    target.write_bytes(pdf_bytes)

    called = {"n": 0}

    def _dummy_process(pdf_bytes: bytes):
        called["n"] += 1
        return ([], types.SimpleNamespace(page_count=1, dpi=300, grayscale=True, used_annotations=True))

    import sys as _sys
    monkeypatch.setitem(_sys.modules, "backend.vision.pipeline", types.SimpleNamespace(process_pdf_bytes=_dummy_process))  # type: ignore

    from hashlib import sha256
    digest = sha256(pdf_bytes).hexdigest()
    payload = {
        "kind": "file",
        "storage_key": storage_key,
        "mime_type": "application/pdf",
        "size_bytes": target.stat().st_size,
        "sha256": digest,
    }

    class _FakeUC:
        def __init__(self, *a, **k):
            pass

        def execute(self, input_data):
            return {"id": str(uuid.uuid4()), "analysis_status": "pending"}

    from backend.web.routes import learning as learning_routes
    fake_repo = types.SimpleNamespace(get_task_kind_for_student=lambda **_: "native")
    monkeypatch.setattr(learning_routes, "_get_repo", lambda: fake_repo)
    monkeypatch.setattr(learning_routes, "CreateSubmissionUseCase", _FakeUC)
    for route in main.app.routes:
        endpoint = getattr(route, "endpoint", None)
        if getattr(endpoint, "__name__", "") == "create_submission":
            monkeypatch.setitem(endpoint.__globals__, "_get_repo", lambda: fake_repo)
            monkeypatch.setitem(endpoint.__globals__, "CreateSubmissionUseCase", _FakeUC)
    try:
        import importlib as _importlib
        lr_alias = _importlib.import_module("routes.learning")
        monkeypatch.setattr(lr_alias, "_get_repo", lambda: fake_repo, raising=False)
        monkeypatch.setattr(lr_alias, "CreateSubmissionUseCase", _FakeUC, raising=False)
    except Exception:
        pass
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

    main.RUNTIME.settings.override_environment("prod")

    async with httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        client.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)  # type: ignore[attr-defined]
        r = await client.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            json=payload,
            headers={"Origin": "http://test"},
        )

    assert r.status_code == 202
    assert called["n"] == 0
