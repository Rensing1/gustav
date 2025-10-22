from datetime import datetime, timezone

from teaching.services.materials import MaterialsService, MaterialFileSettings


class _RepoStub:
    def __init__(self):
        self._material = {
            "id": "m1",
            "unit_id": "u1",
            "section_id": "s1",
            "kind": "file",
            "storage_key": "materials/a/b/c/file.pdf",
        }

    # Protocol methods used by generate_file_download_url
    def get_material_owned(self, unit_id, section_id, material_id, author_id):
        if material_id == self._material["id"]:
            return dict(self._material)
        return None


class _AdapterNoExpiry:
    def presign_download(self, *, bucket: str, key: str, expires_in: int, disposition: str):
        # Return URL without expires_at so the service computes a fallback
        return {"url": f"http://example.local/{bucket}/{key}"}


def test_generate_download_url_falls_back_to_server_expiry_when_missing():
    repo = _RepoStub()
    service = MaterialsService(repo, settings=MaterialFileSettings())
    now = datetime.now(timezone.utc)
    res = service.generate_file_download_url(
        "u1",
        "s1",
        "m1",
        "author",
        disposition="inline",
        storage=_AdapterNoExpiry(),
    )
    assert res["url"].startswith("http://example.local/")
    # Should be an ISO timestamp in the near future
    expires = datetime.fromisoformat(res["expires_at"])  # type: ignore[arg-type]
    assert expires > now
