"""
OpenAPI Contract — Learning Upload Intents (RED)

Validiert, dass der Vertrag einen studentischen Upload‑Intent‑Endpunkt
bereitstellt, damit die UI Bild/PDF‑Uploads vorbereiten kann.
"""
from __future__ import annotations

from pathlib import Path


def _load_openapi() -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "api" / "openapi.yml").read_text(encoding="utf-8")


def test_openapi_has_learning_upload_intents_path():
    yml = _load_openapi()
    # Pfad vorhanden
    assert "/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents:" in yml
    # POST + cookieAuth
    assert "post:" in yml
    assert "cookieAuth" in yml
    # Request Schema enthält kind + filename + mime_type + size_bytes
    assert "StudentUploadIntentRequest:" in yml
    assert "kind:" in yml and "enum: [image, file]" in yml
    assert "filename:" in yml and "mime_type:" in yml and "size_bytes:" in yml
    # Response Schema enthält intent_id, storage_key, url
    assert "StudentUploadIntentResponse:" in yml
    assert "intent_id:" in yml and "storage_key:" in yml and "url:" in yml


def test_openapi_upload_intents_includes_403_forbidden():
    yml = _load_openapi()
    # Ensure 403 is documented for upload-intents
    assert "/api/learning/courses/{course_id}/tasks/{task_id}/upload-intents:" in yml
    # A minimal heuristic: after the path the '403' status code should appear
    assert "'403':" in yml or "403:" in yml
