"""
SSR (Student) — Unit detail page renders each item as a card and renders Markdown.

- Ensures materials are wrapped in a MaterialCard (`surface-panel material-entry`).
- Ensures tasks are wrapped in a TaskCard (`surface-panel task-panel`).
- Ensures markdown in material bodies renders to HTML (e.g., ** → <strong>, * → <em>).
"""
from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402

pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


async def _create_course(client: httpx.AsyncClient, title: str = "Mathe") -> str:
    r = await client.post("/api/teaching/courses", json={"title": title})
    assert r.status_code == 201
    return r.json()["id"]


async def _create_unit(client: httpx.AsyncClient, title: str) -> dict:
    r = await client.post("/api/teaching/units", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _create_section(client: httpx.AsyncClient, unit_id: str, title: str) -> dict:
    r = await client.post(f"/api/teaching/units/{unit_id}/sections", json={"title": title})
    assert r.status_code == 201
    return r.json()


async def _add_material_md(client: httpx.AsyncClient, unit_id: str, section_id: str, title: str, body: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/materials",
        json={"title": title, "body_md": body},
    )
    assert r.status_code == 201
    return r.json()


async def _add_task_md(client: httpx.AsyncClient, unit_id: str, section_id: str, *, instruction: str) -> dict:
    r = await client.post(
        f"/api/teaching/units/{unit_id}/sections/{section_id}/tasks",
        json={"instruction_md": instruction},
    )
    assert r.status_code == 201
    return r.json()


async def _attach_unit(client: httpx.AsyncClient, course_id: str, unit_id: str) -> dict:
    r = await client.post(f"/api/teaching/courses/{course_id}/modules", json={"unit_id": unit_id})
    assert r.status_code == 201
    return r.json()


async def _add_member(client: httpx.AsyncClient, course_id: str, student_sub: str) -> None:
    r = await client.post(f"/api/teaching/courses/{course_id}/members", json={"student_sub": student_sub})
    assert r.status_code in (201, 204)


def _visibility_path(course_id: str, module_id: str, section_id: str) -> str:
    return f"/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility"


@pytest.mark.anyio
async def test_student_unit_page_uses_cards_and_renders_markdown():
    """Materials/tasks render as individual cards; material markdown renders as HTML."""

    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    # Sessions
    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-cards", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-ui-cards", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        # Prepare data
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Cards")
        unit = await _create_unit(c, "Unit Cards")
        section = await _create_section(c, unit["id"], "Einführung")
        await _add_material_md(
            c,
            unit["id"],
            section["id"],
            title="Testmaterial Abschnitt 1",
            body="**Inhalt**: *Testmaterial Abschnitt 1*",
        )
        await _add_task_md(c, unit["id"], section["id"], instruction="Aufgabe: Schreibe einen Satz.")
        module = await _attach_unit(c, course_id, unit["id"])
        await c.patch(_visibility_path(course_id, module["id"], section["id"]), json={"visible": True})

        # Enroll the student so Learning API returns 200 for sections
        await _add_member(c, course_id, student.sub)

        # Student opens the unit page (SSR will contact Learning API using the cookie)
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit["id"]}")
        assert r.status_code == 200
        html = r.text
        # No debug prints in the passing path

    # Each item has its own card classes
    assert "surface-panel material-entry" in html
    assert "surface-panel task-panel" in html

    # Markdown rendered: bold and italic
    assert "<strong>Inhalt</strong>" in html
    assert "<em>Testmaterial Abschnitt 1</em>" in html
    # No raw markdown markers should remain (defense-in-depth)
    assert "**Inhalt**" not in html


@pytest.mark.anyio
async def test_student_unit_page_renders_markdown_table():
    """Markdown tables in materials render as HTML tables on the student page."""

    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore
        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore
        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-table", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-ui-table", name="Schüler", roles=["student"])  # type: ignore

    table_md = """|                                              | Familie Groborz | Familie Jensen |
|----------------------------------------------|------------------|----------------|
| **Gesamtbelastung durch Emissionshandel 2025** | 1.153 €          | 1.509 €        |
| **Entlastung durch Klimageld von 139 €**       | × 3 = 417 €      | × 5 = 695 €    |
| **Entlastung durch Klimageld von 317 €**       | × 3 = 951 €      | × 5 = 1.585 €  |"""

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Tabellen")
        unit = await _create_unit(c, "Unit Tabellen")
        section = await _create_section(c, unit["id"], "Tabellen")
        await _add_material_md(
            c,
            unit["id"],
            section["id"],
            title="Tabelle",
            body=table_md,
        )
        module = await _attach_unit(c, course_id, unit["id"])
        await c.patch(_visibility_path(course_id, module["id"], section["id"]), json={"visible": True})
        await _add_member(c, course_id, student.sub)

        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit['id']}")
        assert r.status_code == 200
        html = r.text

    assert "<table" in html
    assert "<th>Familie Groborz</th>" in html
    assert "<th>Familie Jensen</th>" in html
    assert "<td>1.153 €</td>" in html
    assert "<td>1.509 €</td>" in html
    assert "<strong>Gesamtbelastung durch Emissionshandel 2025</strong>" in html
    # Pipes should not remain in rendered HTML
    assert "| Familie Groborz | Familie Jensen |" not in html


class _FakeStorageAdapter:
    """Minimal storage adapter stub for file material tests.

    Provides just enough behaviour for upload-intent/finalize + download-url
    flows to work in tests without real Supabase connectivity.
    """

    def presign_upload(self, **kwargs):
        return {
            "url": "http://storage.local/upload",
            "headers": {"authorization": "Bearer stub"},
            "expires_at": "2099-01-01T00:00:00+00:00",
        }

    def head_object(self, **kwargs):
        # Return a content-length matching the declared size in tests and a PDF MIME.
        return {"content_type": "application/pdf", "content_length": 1024}

    def presign_download(self, **kwargs):
        return {"url": "http://storage.local/download", "expires_at": "2099-01-01T00:00:30+00:00"}


@pytest.mark.anyio
async def test_student_unit_page_renders_file_material_previews_pdf_and_image():
    """
    Student unit page should embed file materials (PDF + image) using the shared FilePreview.

    - PDF materials render a PDF preview container.
    - Image materials render an image preview container.
    """

    _require_db_or_skip()
    import routes.teaching as teaching  # noqa: E402
    import routes.learning as learning  # noqa: E402

    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
        from backend.learning.repo_db import DBLearningRepo  # type: ignore

        assert isinstance(learning.REPO, DBLearningRepo)
    except Exception:
        pytest.skip("DB-backed repos required")

    # Inject fake storage adapter for teaching materials file flow
    teaching.set_storage_adapter(_FakeStorageAdapter())

    main.SESSION_STORE = SessionStore()
    teacher = main.SESSION_STORE.create(sub="t-ui-files-student", name="Lehrkraft", roles=["teacher"])  # type: ignore
    student = main.SESSION_STORE.create(sub="s-ui-files-student", name="Schüler", roles=["student"])  # type: ignore

    async with (await _client()) as c:
        c.cookies.set("gustav_session", teacher.session_id)
        course_id = await _create_course(c, "Kurs Files")
        unit = await _create_unit(c, "Unit Files")
        section = await _create_section(c, unit["id"], "Einführung")

        # Create PDF material via upload-intent + finalize
        intent_pdf = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "doc.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )).json()
        pdf_mat = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={"intent_id": intent_pdf["intent_id"], "title": "PDF-Material", "sha256": "f" * 64},
        )).json()

        # Create image material via upload-intent + finalize
        intent_img = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "bild.png", "mime_type": "image/png", "size_bytes": 1024},
        )).json()
        img_mat = (await c.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={"intent_id": intent_img["intent_id"], "title": "Bild-Material", "sha256": "f" * 64},
        )).json()

        # Attach unit to course and release section
        module = await _attach_unit(c, course_id, unit["id"])
        await c.patch(_visibility_path(course_id, module["id"], section["id"]), json={"visible": True})

        # Enroll student
        await _add_member(c, course_id, student.sub)

        # Student opens unit page
        c.cookies.set("gustav_session", student.session_id)
        r = await c.get(f"/learning/courses/{course_id}/units/{unit['id']}")
        assert r.status_code == 200
        html = r.text

    # Both materials should appear with inline previews
    assert "PDF-Material" in html
    assert "Bild-Material" in html
    # PDF preview container with zoom hooks
    assert 'file-preview file-preview--pdf' in html
    # Image preview container with zoom hooks
    assert 'file-preview file-preview--image' in html
    # Shared hooks for JS-based zoom
    assert 'data-file-preview="true"' in html
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
    # No zoom class on initial render
    assert 'file-preview--zoomed' not in html
    # Presigned download URL is used in previews
    assert "http://storage.local/download" in html
