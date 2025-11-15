"""
SSR (Student) — Regressions rund um PRG-Banner und History-Content

Ziele (RED):
- Das PRG zeigt den Erfolgsbanner nur dann, wenn der API-POST /submissions
  mit 2xx beantwortet wurde. Bei fehlerhaften Upload-POSTs (fehlende Felder)
  darf kein Erfolgsbanner erscheinen.
- Die History rendert bei Datei-/Bild-Abgaben den extrahierten Text aus
  `analysis_json.text`, wenn `text_body` leer ist.
"""
from __future__ import annotations

import re
import uuid
import pytest
import httpx
from httpx import ASGITransport

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip

import main  # type: ignore  # noqa: E402
from identity_access.stores import SessionStore  # type: ignore  # noqa: E402


pytestmark = pytest.mark.anyio("asyncio")


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.anyio
async def test_ui_prg_banner_not_shown_on_failed_upload_post():
    """PRG darf keinen Erfolgsbanner anzeigen, wenn die API 4xx liefert.

    Wir provozieren 400, indem wir im Upload-Modus ohne vorbereitete Hidden
    Fields (storage_key, mime_type, size_bytes, sha256) posten.
    """
    _require_db_or_skip()

    # Fixture: Kurs/Einheit/Aufgabe sichtbar und Student eingeschrieben
    from backend.tests.test_learning_api_contract import _prepare_learning_fixture  # type: ignore

    fixture = await _prepare_learning_fixture()

    main.SESSION_STORE = SessionStore()
    # Student-Session setzen
    student = main.SESSION_STORE.create(
        sub=fixture.student_sub,
        name="S",
        roles=["student"],
    )

    async with (await _client()) as c:
        c.cookies.set(main.SESSION_COOKIE_NAME, student.session_id)
        # Upload-Modus ohne Hidden-Felder → API 400 → PRG darf kein ok=submitted setzen
        post = await c.post(
            f"/learning/courses/{fixture.course_id}/tasks/{fixture.task['id']}/submit",
            data={"mode": "upload"},
            follow_redirects=False,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert post.status_code in (302, 303)
        loc = post.headers.get("location", "")
        # Vor dem Fix war hier immer ok=submitted enthalten
        follow = await c.get(loc)
        html = follow.text
        assert follow.status_code == 200
        assert "Erfolgreich eingereicht" not in html


def test_history_uses_analysis_text_when_text_body_empty():
    """_build_history_entry_from_record nutzt analysis_json.text als Fallback."""
    # Minimaler Record wie aus der API geliefert
    record = {
        "id": str(uuid.uuid4()),
        "attempt_nr": 1,
        "created_at": "2025-01-01T00:00:00+00:00",
        "text_body": "",  # leer bei Dateien/Bildern
        "analysis_json": {
            "schema": "criteria.v2",
            "text": "## Extracted\n\nHello",
            "criteria_results": [],
        },
        "feedback_md": None,
    }

    from main import _build_history_entry_from_record  # type: ignore

    entry = _build_history_entry_from_record(record, index=0, open_attempt_id="")
    assert hasattr(entry, "content_html")
    # Markdown-Content sollte im HTML landen
    assert re.search(r"Extracted|Hello", entry.content_html)
