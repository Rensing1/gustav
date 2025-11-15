"""
Learning API — Internal Upload Stub (TDD)

Why:
    In dev/offline mode we need a local upload target so the browser can PUT
    the selected file and the server can verify size/hash via
    STORAGE_VERIFY_ROOT. This test drives a minimal PUT endpoint that writes
    bytes and returns sha256 + size for later submission.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import httpx
from httpx import ASGITransport


pytestmark = pytest.mark.anyio("asyncio")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "backend" / "web"
if str(WEB_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(WEB_DIR))
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://local")


@pytest.mark.anyio
async def test_internal_upload_stub_writes_file_and_returns_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Prepare session and path
    os.environ["STORAGE_VERIFY_ROOT"] = str(tmp_path)
    monkeypatch.setenv("ENABLE_DEV_UPLOAD_STUB", "true")
    main.SESSION_STORE = SessionStore()  # in-memory sessions
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore

    storage_key = f"submissions/test/{uuid.uuid4().hex}.png"
    url = f"/api/learning/internal/upload-stub?storage_key={storage_key}"
    data = b"hello world" * 10

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        r = await c.put(url, content=data, headers={"Content-Type": "image/png", "Origin": "http://local"})

    assert r.status_code == 200
    body = r.json()
    assert int(body.get("size_bytes", 0)) == len(data)
    assert isinstance(body.get("sha256"), str) and len(body["sha256"]) == 64

    # Verify file exists on disk at STORAGE_VERIFY_ROOT/storage_key
    target = (tmp_path / storage_key)
    assert target.exists() and target.is_file()
    assert target.stat().st_size == len(data)


@pytest.mark.anyio
async def test_internal_upload_stub_returns_404_when_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENABLE_DEV_UPLOAD_STUB", raising=False)
    main.SESSION_STORE = SessionStore()
    student = main.SESSION_STORE.create(sub=f"s-{uuid.uuid4()}", name="S", roles=["student"])  # type: ignore
    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        res = await c.put(
            "/api/learning/internal/upload-stub?storage_key=submissions/test/file.png",
            content=b"x",
            headers={"Origin": "http://local", "Content-Type": "image/png"},
        )
    assert res.status_code == 404
