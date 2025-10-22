"""Teaching API — File materials (Iteration 1b contract-first tests).

These tests define the expected behaviour of the upload intent, finalize and
download endpoints for file-based teaching materials. They follow the
contract-first + TDD workflow and will fail until the implementation provides
storage integration, migrations and web routes for file materials.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
import main  # type: ignore  # noqa: E402

from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_storage_adapter():
    import routes.teaching as teaching  # noqa: E402

    storage = FakeStorageAdapter()
    try:
        original = teaching.STORAGE_ADAPTER
    except Exception:  # pragma: no cover - fallback for older snapshots
        original = None
    null_adapter_cls = getattr(teaching, "NullStorageAdapter", FakeStorageAdapter)
    if hasattr(teaching, "set_storage_adapter"):
        teaching.set_storage_adapter(storage)
    else:  # pragma: no cover - compatibility path
        teaching.STORAGE_ADAPTER = storage
    try:
        yield storage
    finally:
        if hasattr(teaching, "set_storage_adapter"):
            teaching.set_storage_adapter(original or null_adapter_cls())
        else:
            teaching.STORAGE_ADAPTER = original


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


async def _create_unit(client: httpx.AsyncClient, title: str = "Physik") -> dict[str, Any]:
    resp = await client.post("/api/teaching/units", json={"title": title})
    assert resp.status_code == 201
    return resp.json()


async def _create_section(
    client: httpx.AsyncClient, unit_id: str, title: str = "Kapitel"
) -> dict[str, Any]:
    resp = await client.post(
        f"/api/teaching/units/{unit_id}/sections",
        json={"title": title},
    )
    assert resp.status_code == 201
    return resp.json()


class FakeStorageAdapter:
    """Stub storage adapter used by tests to capture presign/head/delete calls."""

    def __init__(self) -> None:
        self.presign_upload_calls: list[dict[str, Any]] = []
        self.head_calls: list[dict[str, Any]] = []
        self.presign_download_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    def presign_upload(self, **kwargs):
        self.presign_upload_calls.append(kwargs)
        bucket = kwargs.get("bucket", "materials")
        key = kwargs.get("key", "")
        headers = kwargs.get("headers", {})
        return {
            "url": "http://storage.local/upload",
            "headers": {"authorization": "Bearer stub", **headers},
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(),
        }

    def head_object(self, **kwargs) -> dict[str, Any]:
        self.head_calls.append(kwargs)
        return {"content_type": "application/pdf", "content_length": 1024}

    def delete_object(self, **kwargs) -> None:
        self.delete_calls.append(kwargs)

    def presign_download(self, **kwargs):
        self.presign_download_calls.append(kwargs)
        return {
            "url": "http://storage.local/download",
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat(),
        }


@pytest.mark.anyio
async def test_upload_intent_flow_requires_teacher_and_returns_presign_payload(_reset_storage_adapter):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    # Require DB-backed repo to hit real policies.
    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    async with (await _client()) as client:
        # Unauthenticated request is rejected.
        resp = await client.post(
            "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/"
            "00000000-0000-0000-0000-000000000000/materials/upload-intents",
            json={"filename": "plan.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        assert resp.status_code == 401

    teacher = main.SESSION_STORE.create(sub="teacher-files", name="Frau Müller", roles=["teacher"])
    student = main.SESSION_STORE.create(sub="student-files", name="Max", roles=["student"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", student.session_id)
        resp = await client.post(
            "/api/teaching/units/00000000-0000-0000-0000-000000000000/sections/"
            "00000000-0000-0000-0000-000000000000/materials/upload-intents",
            json={"filename": "plan.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        assert resp.status_code == 403

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "Schülerliste.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert uuid.UUID(payload["intent_id"])
        assert uuid.UUID(payload["material_id"])
        assert payload["storage_key"].startswith("materials/teacher-files/")
        assert payload["url"].startswith("http://storage.local/upload")
        assert "authorization" in payload["headers"]
        assert "application/pdf" in payload["accepted_mime_types"]
        assert payload["max_size_bytes"] >= 1024
        expires_at = datetime.fromisoformat(payload["expires_at"])
        assert expires_at > datetime.now(timezone.utc)


@pytest.mark.anyio
async def test_finalize_and_download_flow_enforces_checks(_reset_storage_adapter):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-files", name="Frau Müller", roles=["teacher"])
    other = main.SESSION_STORE.create(sub="other-teacher", name="Herr Schulz", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        intent_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "Experimente.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        assert intent_resp.status_code == 200
        intent = intent_resp.json()

        finalize_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={
                "intent_id": intent["intent_id"],
                "title": "Sicherheitsleitfaden",
                "sha256": "f" * 64,
                "alt_text": "PDF mit Sicherheitsregeln",
            },
        )
        assert finalize_resp.status_code == 201
        material = finalize_resp.json()
        assert material["kind"] == "file"
        assert material["mime_type"] == "application/pdf"
        assert material["size_bytes"] == 1024
        assert material["sha256"] == "f" * 64
        assert material["filename_original"] == "Experimente.pdf"
        assert material["alt_text"] == "PDF mit Sicherheitsregeln"

        # Idempotent finalize returns same payload and 200.
        finalize_again = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={
                "intent_id": intent["intent_id"],
                "title": "Sicherheitsleitfaden",
                "sha256": "f" * 64,
            },
        )
        assert finalize_again.status_code == 200
        material_again = finalize_again.json()
        assert material_again["id"] == material["id"]

        # Download URL only allowed for owner.
        download = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{material['id']}"
            "/download-url",
            params={"disposition": "inline"},
        )
        assert download.status_code == 200
        dl_payload = download.json()
        assert dl_payload["url"].startswith("http://storage.local/download")
        assert datetime.fromisoformat(dl_payload["expires_at"]) > datetime.now(timezone.utc)

        # Other teacher cannot access the material.
        client.cookies.set("gustav_session", other.session_id)
        forbidden = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={
                "intent_id": intent["intent_id"],
                "title": "Sicherheitsleitfaden",
                "sha256": "f" * 64,
            },
        )
        assert forbidden.status_code == 403

        forbidden_download = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{material['id']}"
            "/download-url",
        )
        assert forbidden_download.status_code == 403

        # Invalid disposition returns 400.
        client.cookies.set("gustav_session", teacher.session_id)
        invalid_disp = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{material['id']}"
            "/download-url",
            params={"disposition": "invalid"},
        )
        assert invalid_disp.status_code == 400

        # Delete should remove storage object.
        delete_resp = await client.delete(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{material['id']}",
        )
        assert delete_resp.status_code == 204

        # Ensure storage adapter delete was triggered.
        assert _reset_storage_adapter.delete_calls, "Expected delete_object to be called"

        # Listing materials should now be empty again.
        lst = await client.get(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials",
        )
        assert lst.status_code == 200
        assert lst.json() == []


@pytest.mark.anyio
async def test_finalize_accepts_head_content_type_with_parameters(_reset_storage_adapter):
    """Finalize should accept storage head content-type with parameters (e.g., charset)."""
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-mime-param", name="Frau Müller", roles=["teacher"])

    # Configure fake storage to report a parameterized content-type for head_object
    def _head_with_params(**kwargs):
        _reset_storage_adapter.head_calls.append(kwargs)
        return {"content_type": "application/pdf; charset=UTF-8", "content_length": 1024}

    _reset_storage_adapter.head_object = _head_with_params  # type: ignore[assignment]

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        intent_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "Experimente.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        assert intent_resp.status_code == 200
        intent = intent_resp.json()

        finalize_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={
                "intent_id": intent["intent_id"],
                "title": "Sicherheitsleitfaden",
                "sha256": "f" * 64,
            },
        )
        assert finalize_resp.status_code == 201
        mat = finalize_resp.json()
        assert mat["kind"] == "file"


@pytest.mark.anyio
async def test_upload_intent_rejects_invalid_filename(_reset_storage_adapter):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-invalid-filename", name="Frau Müller", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "   ", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid_filename"


@pytest.mark.anyio
async def test_upload_intent_accepts_mime_with_uppercase(_reset_storage_adapter):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-uppercase-mime", name="Frau Müller", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "Schülerliste.PDF", "mime_type": "APPLICATION/PDF", "size_bytes": 1024},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["headers"]["content-type"] == "application/pdf"


@pytest.mark.anyio
async def test_upload_intent_rejects_size_exceeded(_reset_storage_adapter):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-size-exceeded", name="Frau Müller", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "groß.pdf", "mime_type": "application/pdf", "size_bytes": 25 * 1024 * 1024},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "size_exceeded"


@pytest.mark.anyio
async def test_finalize_rejects_expired_intent(_reset_storage_adapter):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-expired-intent", name="Frau Müller", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        intent_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "Experimente.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        intent = intent_resp.json()

        import psycopg  # type: ignore

        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            host = os.getenv("TEST_DB_HOST", "127.0.0.1")
            port = os.getenv("TEST_DB_PORT", "54322")
            dsn = f"postgresql://gustav_limited:gustav-limited@{host}:{port}/postgres"
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select set_config('app.current_sub', %s, true)", (teacher.sub,))
                cur.execute(
                    "update public.upload_intents set expires_at = now() - interval '1 minute' where id = %s",
                    (intent["intent_id"],),
                )
                conn.commit()

        finalize_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={
                "intent_id": intent["intent_id"],
                "title": "Überfällig",
                "sha256": "f" * 64,
            },
        )
        assert finalize_resp.status_code == 400
        assert finalize_resp.json()["detail"] == "intent_expired"


@pytest.mark.anyio
async def test_patch_file_material_allows_alt_text_update(_reset_storage_adapter):
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    from utils.db import require_db_or_skip

    require_db_or_skip()
    try:
        from teaching.repo_db import DBTeachingRepo  # type: ignore

        assert isinstance(teaching.REPO, DBTeachingRepo)
    except Exception:
        pytest.skip("DB-backed TeachingRepo required for this test")

    teacher = main.SESSION_STORE.create(sub="teacher-alt-text", name="Frau Müller", roles=["teacher"])

    async with (await _client()) as client:
        client.cookies.set("gustav_session", teacher.session_id)
        unit = await _create_unit(client)
        section = await _create_section(client, unit["id"])

        intent_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
            json={"filename": "Experimente.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
        )
        intent = intent_resp.json()

        finalize_resp = await client.post(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
            json={
                "intent_id": intent["intent_id"],
                "title": "Sicherheitsleitfaden",
                "sha256": "f" * 64,
                "alt_text": "PDF mit Sicherheitsregeln",
            },
        )
        material = finalize_resp.json()
        assert finalize_resp.status_code == 201

        patch_resp = await client.patch(
            f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{material['id']}",
            json={"alt_text": "Aktualisierte Beschreibung"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["alt_text"] == "Aktualisierte Beschreibung"


@pytest.mark.anyio
async def test_upload_flow_works_with_in_memory_repo(_reset_storage_adapter):
    """Ensure dev fallback repo implements complete file workflow."""
    main.SESSION_STORE = SessionStore()
    import routes.teaching as teaching  # noqa: E402

    original_repo = teaching.REPO
    original_adapter = teaching.STORAGE_ADAPTER
    try:
        fallback_repo = teaching._Repo()  # type: ignore[attr-defined]
        teaching.set_repo(fallback_repo)
        storage = FakeStorageAdapter()
        teaching.set_storage_adapter(storage)

        teacher = main.SESSION_STORE.create(sub="teacher-inmemory", name="Frau Müller", roles=["teacher"])

        async with (await _client()) as client:
            client.cookies.set("gustav_session", teacher.session_id)
            unit = await _create_unit(client)
            section = await _create_section(client, unit["id"])

            intent_resp = await client.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/upload-intents",
                json={"filename": "Experimente.pdf", "mime_type": "application/pdf", "size_bytes": 1024},
            )
            assert intent_resp.status_code == 200
            intent = intent_resp.json()

            finalize_resp = await client.post(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/finalize",
                json={
                    "intent_id": intent["intent_id"],
                    "title": "Sicherheitsleitfaden",
                    "sha256": "f" * 64,
                    "alt_text": "PDF mit Sicherheitsregeln",
                },
            )
            assert finalize_resp.status_code == 201
            material = finalize_resp.json()
            assert material["kind"] == "file"

            download = await client.get(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{material['id']}/download-url"
            )
            assert download.status_code == 200

            delete_resp = await client.delete(
                f"/api/teaching/units/{unit['id']}/sections/{section['id']}/materials/{material['id']}"
            )
            assert delete_resp.status_code == 204
    finally:
        teaching.set_repo(original_repo)
        if original_adapter is not None:
            teaching.set_storage_adapter(original_adapter)
