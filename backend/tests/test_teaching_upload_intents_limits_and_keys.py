"""
Teaching upload-intents should use central config for limits and key helpers.

TDD: This test asserts that the max size in the response honors central config
and that the generated storage key follows the helper's shape.
"""
from __future__ import annotations

import importlib
import re
import uuid
import httpx
import pytest
from httpx import ASGITransport

from backend.tests.runtime_auth_helpers import install_session_store

teaching = importlib.import_module("backend.web.routes.teaching")


def _main():
    return importlib.import_module("backend.web.main")

pytestmark = pytest.mark.anyio("asyncio")


async def _client():
    main = _main()
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test", headers={"Origin": "http://test"})


async def _seed_unit_section(monkeypatch: pytest.MonkeyPatch):
    main = _main()
    session_store = install_session_store(monkeypatch, main)
    teacher = session_store.create(sub=f"t-{uuid.uuid4()}", name="T", roles=["teacher"])
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, teacher.session_id)
        r_unit = await c.post("/api/teaching/units", json={"title": "Einheit"})
        unit_id = r_unit.json()["id"]
        r_section = await c.post(f"/api/teaching/units/{unit_id}/sections", json={"title": "A"})
        section_id = r_section.json()["id"]
    return teacher.session_id, unit_id, section_id


class _Recorder:
    def __init__(self):
        self.calls: list[dict] = []

    def presign_upload(self, *, bucket: str, key: str, expires_in: int, headers: dict[str, str]) -> dict:
        self.calls.append({"bucket": bucket, "key": key, "expires_in": expires_in, "headers": headers})
        return {"url": f"http://storage/{bucket}/{key}", "headers": headers}

    def head_object(self, *, bucket: str, key: str) -> dict:
        return {"content_length": None}

    def delete_object(self, *, bucket: str, key: str) -> None:
        return None

    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str) -> dict:
        return {"url": f"http://storage/{bucket}/{key}", "expires_at": "2099-01-01T00:00:00Z"}


async def test_teaching_upload_intent_uses_config_limit_and_key_shape(monkeypatch):
    # Force distinct config values
    monkeypatch.setenv("MATERIALS_MAX_UPLOAD_BYTES", "4194304")  # 4 MiB
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "mat-cfg")

    # Reload config and modules to pick up env
    if "backend.storage.config" in importlib.sys.modules:
        importlib.reload(importlib.import_module("backend.storage.config"))
    teaching.MATERIAL_FILE_SETTINGS = teaching.MaterialFileSettings()
    recorder = _Recorder()
    teaching.set_storage_adapter(recorder)  # type: ignore[arg-type]

    sid, unit_id, section_id = await _seed_unit_section(monkeypatch)
    async with (await _client()) as c:
        main = _main()
        c.cookies.set(main.SESSION_COOKIE_NAME, sid)
        r = await c.post(
            f"/api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents",
            json={"filename": "Skript.PDF", "mime_type": "application/pdf", "size_bytes": 1024},
            headers={"Origin": "http://test"},
        )
    assert r.status_code == 200
    body = r.json()
    assert int(body.get("max_size_bytes", 0)) == 4 * 1024 * 1024
    assert recorder.calls, "adapter should be called"
    call = recorder.calls[-1]
    assert call["bucket"] == "mat-cfg"
    # Key shape: materials/{unit}/{section}/{material}/{uuid}.{ext}
    assert call["key"].startswith("materials/")
    assert call["key"].endswith(".pdf")
    assert re.match(r"^materials/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9a-f]+\.pdf$", call["key"]) is not None
