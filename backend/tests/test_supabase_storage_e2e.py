import os
import sys
import uuid
from hashlib import sha256

import httpx
import pytest
from httpx import ASGITransport


pytestmark = pytest.mark.supabase_integration


def _should_run():
    return os.getenv("RUN_SUPABASE_E2E") == "1" and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")


async def _client(app):
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.skipif(not _should_run(), reason="Supabase E2E disabled; set RUN_SUPABASE_E2E=1 and env vars")
@pytest.mark.anyio
async def test_e2e_supabase_upload_finalize_download_delete_flow(monkeypatch):
    """
    High-level E2E smoke test against a real Supabase Storage instance:
      - Request upload intent for a file material
      - PUT file to signed upload URL (direct to Supabase)
      - Finalize intent and persist material
      - Generate download URL and fetch bytes
      - Delete material and verify download becomes 404

    Preconditions:
      - RUN_SUPABASE_E2E=1
      - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY set (service role)
      - Buckets provisioned by migrations or AUTO_CREATE_STORAGE_BUCKETS=true
    """
    # Ensure app wiring picks up bucket auto-provisioning (dev convenience)
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")
    # Avoid proxy/stub paths; use direct signed URLs
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")
    # Local dev helpers: rewrite signed URL host to SUPABASE_URL host
    monkeypatch.setenv("SUPABASE_REWRITE_SIGNED_URL_HOST", "true")

    # Import the app fresh so storage wiring runs with current env
    for name in list(sys.modules.keys()):
        if name in {"main", "routes.teaching", "backend.web.routes.teaching", "teaching.storage_supabase", "backend.teaching.storage_supabase"}:
            del sys.modules[name]
    import backend.web.main as main  # type: ignore
    from identity_access.stores import SessionStore  # type: ignore

    # Create a teacher session
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore

    async with (await _client(main.app)) as c:
        # Create a unit and a section
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "E2E Unit"}, headers={"Origin": "http://test"})
        assert r_unit.status_code == 201, r_unit.text
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Intro"}, headers={"Origin": "http://test"})
        assert r_section.status_code == 201, r_section.text
        section_id = r_section.json()["id"]

        # Prepare a small PDF payload
        pdf_bytes = b"%PDF-1.4\n% GustAV E2E PDF\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
        size = len(pdf_bytes)

        # Request upload intent
        r_intent = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
            json={"filename": "e2e.pdf", "mime_type": "application/pdf", "size_bytes": size},
            headers={"Origin": "http://test"},
        )
        assert r_intent.status_code == 200, r_intent.text
        intent = r_intent.json()
        assert intent.get("url") and intent.get("headers")

    # Upload directly to Supabase signed URL (outside ASGI client)
    upload_headers = {k.lower(): v for k, v in dict(intent.get("headers", {})).items()}
    # Ensure content-type is present for the upload
    if "content-type" not in upload_headers:
        upload_headers["content-type"] = "application/pdf"
    put = httpx.put(intent["url"], content=pdf_bytes, headers=upload_headers, timeout=30)
    assert 200 <= put.status_code < 300, f"upload failed: {put.status_code} {put.text}"

    # Finalize with checksum
    checksum = sha256(pdf_bytes).hexdigest()
    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_finalize = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize",
            json={
                "intent_id": intent["intent_id"],
                "title": "E2E PDF",
                "sha256": checksum,
                "alt_text": "Test PDF",
            },
            headers={"Origin": "http://test"},
        )
        assert r_finalize.status_code in (200, 201), r_finalize.text
        material = r_finalize.json()
        material_id = material["id"]

        # Generate download URL and fetch
        r_dl = await c.get(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url",
            params={"disposition": "inline"},
        )
        assert r_dl.status_code == 200, r_dl.text
        dl = r_dl.json()
        resp = httpx.get(dl["url"], timeout=30)
        assert resp.status_code == 200
        assert resp.content == pdf_bytes

        # Delete material
        r_del = await c.delete(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}",
            headers={"Origin": "http://test"},
        )
        assert r_del.status_code == 204, r_del.text

        # Subsequent download-url should be 404
        r_dl2 = await c.get(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url"
        )
        assert r_dl2.status_code == 404


@pytest.mark.skipif(not _should_run(), reason="Supabase E2E disabled; set RUN_SUPABASE_E2E=1 and env vars")
@pytest.mark.anyio
async def test_e2e_learning_submission_file_upload_finalize(monkeypatch):
    """
    Learning Submissions E2E against real Supabase Storage:
      - Teacher creates course/unit/section/task and releases section
      - Student requests upload-intent for a PDF
      - PUT file to Supabase signed URL
      - Student POSTs submission with storage metadata and sha256
      - List submissions returns the created submission
    """
    # Ensure adapter wiring and no proxy/stub shortcuts
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")
    monkeypatch.setenv("SUPABASE_REWRITE_SIGNED_URL_HOST", "true")
    # Enforce strict CSRF checks path for submissions too
    monkeypatch.setenv("STRICT_CSRF_SUBMISSIONS", "true")

    # Fresh import for wiring with current env
    for name in list(sys.modules.keys()):
        if name in {"main", "routes.teaching", "routes.learning", "backend.web.routes.teaching", "backend.web.routes.learning", "teaching.storage_supabase", "backend.teaching.storage_supabase"}:
            del sys.modules[name]
    import backend.web.main as main  # type: ignore
    import routes.learning as learning  # noqa: F401  # ensure module is loaded
    from identity_access.stores import SessionStore  # type: ignore

    # Teacher and student sessions
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    async with (await _client(main.app)) as c:
        # Create course/unit/section/task
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "E2E Course"}, headers={"Origin": "http://test"})
        assert r_course.status_code == 201, r_course.text
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "E2E Unit"}, headers={"Origin": "http://test"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Sec"}, headers={"Origin": "http://test"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Aufgabe", "criteria": ["K"], "max_attempts": 3},
            headers={"Origin": "http://test"},
        )
        task_id = r_task.json()["id"]
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
        module_id = r_module.json()["id"]
        r_vis = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r_vis.status_code == 200, r_vis.text
        # Enrol student
        r_member = await c.post(
            f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name}, headers={"Origin": "http://test"}
        )
        assert r_member.status_code == 201, r_member.text

    # Student requests upload-intent
    pdf_bytes = b"%PDF-1.4\n% GUSTAV Learning E2E\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    size = len(pdf_bytes)
    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_intent = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "file", "filename": "submission.pdf", "mime_type": "application/pdf", "size_bytes": size},
            headers={"Origin": "http://test"},
        )
        assert r_intent.status_code == 200, r_intent.text
        intent = r_intent.json()

    # Upload to Supabase
    upload_headers = {k.lower(): v for k, v in dict(intent.get("headers", {})).items()}
    if "content-type" not in upload_headers:
        upload_headers["content-type"] = "application/pdf"
    put = httpx.put(intent["url"], content=pdf_bytes, headers=upload_headers, timeout=30)
    assert 200 <= put.status_code < 300, f"upload failed: {put.status_code} {put.text}"

    # Submit finalized payload
    checksum = sha256(pdf_bytes).hexdigest()
    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_submit = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            json={
                "kind": "file",
                "storage_key": intent["storage_key"],
                "mime_type": "application/pdf",
                "size_bytes": size,
                "sha256": checksum,
            },
            headers={"Origin": "http://test"},
        )
        assert r_submit.status_code in (201, 202), r_submit.text
        sub = r_submit.json()
        assert sub.get("id") and sub.get("kind") in {"file", "image", "text"}
        assert r_submit.headers.get("Cache-Control") == "private, no-store"

        # List submissions should include the new one
        r_list = await c.get(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions?limit=5&offset=0"
        )
        assert r_list.status_code == 200, r_list.text
        items = r_list.json()
        assert isinstance(items, list) and any(it.get("id") == sub.get("id") for it in items)


@pytest.mark.skipif(not _should_run(), reason="Supabase E2E disabled; set RUN_SUPABASE_E2E=1 and env vars")
@pytest.mark.anyio
async def test_e2e_learning_submission_image_upload_finalize(monkeypatch):
    """
    Learning Submissions E2E (image):
      - Seed course/unit/section/task and release
      - Student requests upload-intent for image/png
      - PUT to signed URL
      - POST submission with finalized metadata
      - Verify submission appears in list
    """
    monkeypatch.setenv("AUTO_CREATE_STORAGE_BUCKETS", "true")
    monkeypatch.setenv("ENABLE_STORAGE_UPLOAD_PROXY", "false")
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "false")
    monkeypatch.setenv("STRICT_CSRF_SUBMISSIONS", "true")
    monkeypatch.setenv("SUPABASE_REWRITE_SIGNED_URL_HOST", "true")

    for name in list(sys.modules.keys()):
        if name in {"main", "routes.teaching", "routes.learning", "backend.web.routes.teaching", "backend.web.routes.learning", "teaching.storage_supabase", "backend.teaching.storage_supabase"}:
            del sys.modules[name]
    import backend.web.main as main  # type: ignore
    import routes.learning as learning  # noqa: F401
    from identity_access.stores import SessionStore  # type: ignore

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_course = await c.post("/api/teaching/courses", json={"title": "E2E Course IMG"}, headers={"Origin": "http://test"})
        assert r_course.status_code == 201, r_course.text
        course_id = r_course.json()["id"]
        r_unit = await c.post("/api/teaching/units", json={"title": "E2E Unit IMG"}, headers={"Origin": "http://test"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "Sec"}, headers={"Origin": "http://test"})
        section_id = r_section.json()["id"]
        r_task = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
            json={"instruction_md": "Bild-Aufgabe", "criteria": ["Qualität"], "max_attempts": 3},
            headers={"Origin": "http://test"},
        )
        task_id = r_task.json()["id"]
        r_module = await c.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id}, headers={"Origin": "http://test"})
        module_id = r_module.json()["id"]
        r_vis = await c.patch(
            f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility",
            json={"visible": True},
            headers={"Origin": "http://test"},
        )
        assert r_vis.status_code == 200, r_vis.text
        r_member = await c.post(
            f"/api/teaching/courses/{course_id}/members", json={"sub": student.sub, "name": student.name}, headers={"Origin": "http://test"}
        )
        assert r_member.status_code == 201, r_member.text

    # Tiny PNG-like byte sequence (content isn't parsed server-side)
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...\x00\x00IEND\xaeB`\x82"
    size = len(png_bytes)
    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_intent = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents",
            json={"kind": "image", "filename": "img.png", "mime_type": "image/png", "size_bytes": size},
            headers={"Origin": "http://test"},
        )
        assert r_intent.status_code == 200, r_intent.text
        intent = r_intent.json()

    upload_headers = {k.lower(): v for k, v in dict(intent.get("headers", {})).items()}
    if "content-type" not in upload_headers:
        upload_headers["content-type"] = "image/png"
    put = httpx.put(intent["url"], content=png_bytes, headers=upload_headers, timeout=30)
    assert 200 <= put.status_code < 300, f"upload failed: {put.status_code} {put.text}"

    checksum = sha256(png_bytes).hexdigest()
    async with (await _client(main.app)) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r_submit = await c.post(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions",
            json={
                "kind": "image",
                "storage_key": intent["storage_key"],
                "mime_type": "image/png",
                "size_bytes": size,
                "sha256": checksum,
            },
            headers={"Origin": "http://test"},
        )
        assert r_submit.status_code in (201, 202), r_submit.text
        sub = r_submit.json()
        assert sub.get("id") and sub.get("kind") == "image"

        r_list = await c.get(
            f"/api/learning/courses/{course_id}/tasks/{task_id}/submissions?limit=5&offset=0"
        )
        assert r_list.status_code == 200, r_list.text
        items = r_list.json()
        assert any(it.get("id") == sub.get("id") for it in items)
