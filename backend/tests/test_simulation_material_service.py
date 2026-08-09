"""Use-case tests for simulation upload and finalization."""

from datetime import datetime, timezone
from hashlib import sha256

import pytest

from backend.teaching.services.materials import MaterialsService


HTML = b"<!doctype html><html><body><button>Start</button><script>let x=1</script></body></html>"


class Repo:
    def __init__(self) -> None:
        self.intents: dict[str, dict] = {}
        self.materials: dict[str, dict] = {}

    def section_exists_for_author(self, *_args) -> bool:
        return True

    def create_file_upload_intent(self, unit_id, section_id, author_id, **values):
        row = {
            "unit_id": unit_id,
            "section_id": section_id,
            "author_id": author_id,
            "consumed_at": None,
            **values,
        }
        self.intents[values["intent_id"]] = row
        return row

    def get_upload_intent_owned(self, intent_id, *_args):
        return self.intents.get(intent_id)

    def get_material_owned(self, _unit_id, _section_id, material_id, _author_id):
        return self.materials.get(material_id)

    def finalize_upload_intent_create_material(self, intent_id, unit_id, section_id, author_id, **values):
        intent = self.intents[intent_id]
        material = {
            "id": intent["material_id"],
            "unit_id": unit_id,
            "section_id": section_id,
            "kind": intent["material_kind"],
            "mime_type": intent["mime_type"],
            "filename_original": intent["filename"],
            "storage_key": intent["storage_key"],
            "size_bytes": intent["size_bytes"],
            **values,
        }
        self.materials[material["id"]] = material
        intent["consumed_at"] = datetime.now(timezone.utc)
        return material, True


class Storage:
    def __init__(self, payload: bytes = HTML) -> None:
        self.payload = payload
        self.deleted: list[str] = []

    def presign_upload(self, **_kwargs):
        return {"url": "https://storage.test/upload", "headers": {}}

    def head_object(self, **_kwargs):
        return {"content_type": "text/html; charset=utf-8", "content_length": len(self.payload)}

    def read_object(self, *, key: str, max_bytes: int, **_kwargs):
        assert max_bytes == 5 * 1024 * 1024
        return self.payload

    def delete_object(self, *, key: str, **_kwargs):
        self.deleted.append(key)


def test_simulation_upload_uses_its_own_mime_and_size_policy() -> None:
    service = MaterialsService(repo=Repo())
    storage = Storage()

    intent = service.create_file_upload_intent(
        "unit",
        "section",
        "teacher",
        filename="modell.html",
        mime_type="text/html",
        size_bytes=len(HTML),
        material_kind="simulation",
        storage=storage,
    )

    assert intent["kind"] == "simulation"
    assert intent["accepted_mime_types"] == ["text/html"]
    assert intent["max_size_bytes"] == 5 * 1024 * 1024


def test_simulation_finalize_verifies_actual_bytes_and_preserves_orientation() -> None:
    repo = Repo()
    service = MaterialsService(repo=repo)
    storage = Storage()
    intent = service.create_file_upload_intent(
        "unit", "section", "teacher",
        filename="modell.html", mime_type="text/html", size_bytes=len(HTML),
        material_kind="simulation", storage=storage,
    )

    material, created = service.finalize_file_material(
        "unit", "section", "teacher",
        intent_id=intent["intent_id"], title="Modell", sha256=sha256(HTML).hexdigest(),
        alt_text=None, body_md="Verändere den Regler.", storage=storage,
    )

    assert created is True
    assert material["kind"] == "simulation"
    assert material["body_md"] == "Verändere den Regler."
    assert material["alt_text"] is None


def test_simulation_finalize_deletes_rejected_online_html() -> None:
    payload = b"<html><body><script>fetch('https://example.test')</script></body></html>"
    repo = Repo()
    service = MaterialsService(repo=repo)
    storage = Storage(payload)
    intent = service.create_file_upload_intent(
        "unit", "section", "teacher",
        filename="modell.html", mime_type="text/html", size_bytes=len(payload),
        material_kind="simulation", storage=storage,
    )

    with pytest.raises(ValueError, match="^simulation_not_self_contained$"):
        service.finalize_file_material(
            "unit", "section", "teacher",
            intent_id=intent["intent_id"], title="Modell", sha256=sha256(payload).hexdigest(),
            alt_text=None, body_md="", storage=storage,
        )

    assert storage.deleted == [intent["storage_key"]]
