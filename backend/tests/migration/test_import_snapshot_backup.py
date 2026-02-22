from __future__ import annotations

import io
import gzip
import tarfile
from pathlib import Path

import pytest

from backend.tools import import_snapshot_backup as mod


def _write_tar_gz(path: Path, *, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_safe_extract_tar_rejects_parent_traversal(tmp_path: Path) -> None:
    tar_path = tmp_path / "bad.tgz"
    _write_tar_gz(tar_path, members={"../evil.txt": b"nope"})

    with tarfile.open(tar_path, "r:gz") as tar:
        with pytest.raises(RuntimeError, match="parent traversal"):
            mod._safe_extract_tar(tar, tmp_path / "out")


def test_safe_extract_tar_rejects_symlink(tmp_path: Path) -> None:
    tar_path = tmp_path / "bad_symlink.tgz"
    with tarfile.open(tar_path, "w:gz") as tar:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)

    with tarfile.open(tar_path, "r:gz") as tar:
        with pytest.raises(RuntimeError, match="symlink"):
            mod._safe_extract_tar(tar, tmp_path / "out")


def test_resolve_snapshot_files_from_directory(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "supabase_db.sql.gz").write_bytes(b"dummy")
    (snapshot / "storage_buckets.tar.gz").write_bytes(b"dummy")

    files = mod.resolve_snapshot_files(snapshot, tmp_path / "extract")
    assert files.root == snapshot
    assert files.supabase_db_sql_gz.name == "supabase_db.sql.gz"
    assert files.storage_buckets_tar_gz.name == "storage_buckets.tar.gz"


def test_resolve_snapshot_files_from_tarball(tmp_path: Path) -> None:
    snapshot_tgz = tmp_path / "snapshot.tgz"
    _write_tar_gz(
        snapshot_tgz,
        members={
            "backup/supabase_db.sql.gz": b"dummy",
            "backup/storage_buckets.tar.gz": b"dummy",
        },
    )

    extract_root = tmp_path / "extract"
    files = mod.resolve_snapshot_files(snapshot_tgz, extract_root)
    assert files.root == extract_root
    assert files.supabase_db_sql_gz.exists()
    assert files.storage_buckets_tar_gz.exists()


def test_ensure_local_dsn_blocks_remote_hosts() -> None:
    with pytest.raises(RuntimeError, match="non-local DSN"):
        mod.ensure_local_dsn("postgresql://u:p@db.example.com:5432/postgres", allow_remote=False)

    # Explicit override
    mod.ensure_local_dsn("postgresql://u:p@db.example.com:5432/postgres", allow_remote=True)


def test_ensure_superuser_for_reset_blocks_non_superuser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_is_superuser_dsn", lambda _dsn: False, raising=False)
    with pytest.raises(RuntimeError, match="superuser"):
        mod.ensure_superuser_for_reset("postgresql://u:p@127.0.0.1:54322/postgres")

    monkeypatch.setattr(mod, "_is_superuser_dsn", lambda _dsn: True, raising=False)
    mod.ensure_superuser_for_reset("postgresql://u:p@127.0.0.1:54322/postgres")


def test_reset_db_for_restore_drops_extensions_before_schemas(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class FakeCompleted:
        def __init__(self) -> None:
            self.stdout = ""

    def fake_run(cmd: list[str], **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return FakeCompleted()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod._reset_db_for_restore("postgresql://u:p@127.0.0.1:54322/postgres")

    assert len(calls) == 4
    assert "drop extension" in (calls[0][-1] or "").lower()
    assert "drop publication" in (calls[1][-1] or "").lower()
    assert "drop schema" in (calls[2][-1] or "").lower()
    assert "create schema" in (calls[3][-1] or "").lower()
    assert "public" in (calls[3][-1] or "").lower()


def test_is_graphql_public_grant_line() -> None:
    assert mod._is_graphql_public_grant_line(
        b'GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO anon;'
    )
    assert not mod._is_graphql_public_grant_line(
        b"-- GRANT ALL ON FUNCTION graphql_public.graphql(\"operationName\" text, query text, variables jsonb, extensions jsonb) TO anon;"
    )


def test_build_object_url_encodes_bucket_and_key() -> None:
    url = mod._build_object_url("http://127.0.0.1:54321", "section materials", "a b/ü.txt")
    assert url.endswith("/storage/v1/object/section%20materials/a%20b/%C3%BC.txt")


def test_inspect_storage_tar_detects_bucket_depth(tmp_path: Path) -> None:
    storage_tar = tmp_path / "storage_buckets.tar.gz"
    with tarfile.open(storage_tar, "w:gz") as tar:
        for name in [
            "stub/stub/section_materials/a.txt",
            "stub/stub/submissions/b.txt",
        ]:
            info = tarfile.TarInfo(name)
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))

    buckets, files, total_bytes = mod._inspect_storage_tar(storage_tar)
    assert files == 2
    assert total_bytes == 2
    assert buckets == ["section_materials", "submissions"]


def test_collect_storage_objects_uses_db_bucket_ids(tmp_path: Path) -> None:
    root = tmp_path / "storage_extracted"
    (root / "stub" / "stub" / "section_materials").mkdir(parents=True)
    (root / "stub" / "stub" / "submissions").mkdir(parents=True)
    (root / "stub" / "stub" / "section_materials" / "a b.txt").write_text("x", encoding="utf-8")
    (root / "stub" / "stub" / "submissions" / "ü.txt").write_text("y", encoding="utf-8")
    (root / "README.txt").write_text("ignore", encoding="utf-8")

    objects, buckets, skipped = mod._collect_storage_objects(
        storage_root=root,
        bucket_ids={"section_materials", "submissions"},
    )

    assert buckets == {"section_materials", "submissions"}
    assert (("section_materials", "a b.txt") in [(b, k) for (b, k, _) in objects]) is True
    assert (("submissions", "ü.txt") in [(b, k) for (b, k, _) in objects]) is True
    assert any(p.endswith("README.txt") for p in skipped)


def test_upload_storage_objects_posts_encoded_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "storage_extracted"
    (root / "stub" / "stub" / "section_materials").mkdir(parents=True)
    (root / "stub" / "stub" / "submissions").mkdir(parents=True)
    (root / "stub" / "stub" / "section_materials" / "a b.txt").write_text("x", encoding="utf-8")
    (root / "stub" / "stub" / "submissions" / "ü.txt").write_text("y", encoding="utf-8")
    (root / "README.txt").write_text("ignore", encoding="utf-8")

    monkeypatch.setattr(mod, "_fetch_storage_bucket_ids", lambda _dsn: ["section_materials", "submissions"])

    ensured: dict[str, list[str]] = {}

    def fake_ensure_buckets(_base_url: str, _key: str, buckets) -> None:
        ensured["buckets"] = list(buckets)

    monkeypatch.setattr(mod, "_ensure_buckets", fake_ensure_buckets)

    class FakeResponse:
        def __init__(self, status_code: int = 200, text: str = "") -> None:
            self.status_code = status_code
            self.text = text

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def post(self, url: str, headers: dict[str, str], data, timeout) -> FakeResponse:  # type: ignore[no-untyped-def]
            body = data.read()
            self.calls.append({"url": url, "headers": headers, "body": body, "timeout": timeout})
            return FakeResponse()

    fake_session = FakeSession()
    monkeypatch.setattr(mod.requests, "Session", lambda: fake_session)

    result = mod._upload_storage_objects(
        base_url="http://127.0.0.1:54321",
        service_role_key="srk",
        storage_root=root,
        dsn="postgresql://u:p@127.0.0.1:54322/postgres",
        dry_run=False,
    )

    assert result["uploaded"] == 2
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["skipped_files"] == 1
    assert ensured["buckets"] == ["section_materials", "submissions"]

    urls = {c["url"] for c in fake_session.calls}
    assert "http://127.0.0.1:54321/storage/v1/object/section_materials/a%20b.txt" in urls
    assert "http://127.0.0.1:54321/storage/v1/object/submissions/%C3%BC.txt" in urls

    for call in fake_session.calls:
        headers = call["headers"]
        assert headers["apikey"] == "srk"
        assert headers["Authorization"] == "Bearer srk"
        assert headers["x-upsert"] == "true"


def test_guess_content_type_prefers_key_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "bucket" / "x" / "1763317293475-e36ed3455e6249f5baa87127aa42991c.pdf" / "59682179-f7aa-48d4-bb51-a723705c3791"
    assert mod._guess_content_type(file_path, "bucket/1763317293475-e36ed3455e6249f5baa87127aa42991c.pdf/59682179-f7aa-48d4-bb51-a723705c3791") == "application/pdf"


def test_guess_content_type_falls_back_to_octet_stream(tmp_path: Path) -> None:
    file_path = tmp_path / "bucket" / "noext"
    assert mod._guess_content_type(file_path, "bucket/noext") == "application/octet-stream"


def test_resolve_snapshot_files_reads_optional_keycloak_dump(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "supabase_db.sql.gz").write_bytes(b"db")
    (snapshot / "storage_buckets.tar.gz").write_bytes(b"storage")
    (snapshot / "keycloak_db.sql.gz").write_bytes(b"kc")

    files = mod.resolve_snapshot_files(snapshot, tmp_path / "extract")

    assert files.keycloak_db_sql_gz is not None
    assert files.keycloak_db_sql_gz.name == "keycloak_db.sql.gz"


def test_resolve_snapshot_files_keeps_keycloak_dump_optional(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "supabase_db.sql.gz").write_bytes(b"db")
    (snapshot / "storage_buckets.tar.gz").write_bytes(b"storage")

    files = mod.resolve_snapshot_files(snapshot, tmp_path / "extract")

    assert files.keycloak_db_sql_gz is None


def test_is_unsupported_pg_setting_line() -> None:
    assert mod._is_unsupported_pg_setting_line(b"SET transaction_timeout = 0;")
    assert not mod._is_unsupported_pg_setting_line(b"SET statement_timeout = 0;")


def test_build_keycloak_localization_sql_contains_local_values() -> None:
    sql = mod._build_keycloak_localization_sql(
        realm="gustav",
        web_client_id="gustav-web",
        app_base_url="https://app.localhost",
    )

    assert "https://app.localhost/*" in sql
    assert "https://app.localhost" in sql
    assert "client_id = 'gustav-web'" in sql
    assert "name = 'gustav'" in sql


def test_build_keycloak_admin_client_secret_sql_contains_target_values() -> None:
    sql = mod._build_keycloak_admin_client_secret_sql(
        admin_realm="master",
        admin_client_id="gustav-admin-cli",
        admin_client_secret="LOCAL_SECRET",
    )

    assert "update client set secret = 'LOCAL_SECRET'" in sql
    assert "name = 'master'" in sql
    assert "client_id = 'gustav-admin-cli'" in sql


def test_restore_keycloak_db_resets_before_replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    keycloak_sql_gz = tmp_path / "keycloak_db.sql.gz"
    with gzip.open(keycloak_sql_gz, "wb") as f:
        f.write(b"select 1;\n")

    called = {"reset": 0}

    def fake_reset_keycloak_db_for_restore(**_kwargs) -> None:
        called["reset"] += 1

    monkeypatch.setattr(mod, "_reset_keycloak_db_for_restore", fake_reset_keycloak_db_for_restore)

    class FakeProc:
        def __init__(self) -> None:
            self.stdin = io.BytesIO()

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(mod.subprocess, "Popen", lambda *_args, **_kwargs: FakeProc())

    mod._restore_keycloak_db_sql_gz(
        db_sql_gz=keycloak_sql_gz,
        keycloak_db_container="gustav-keycloak-db",
        keycloak_db_user="keycloak",
        keycloak_db_name="keycloak",
    )

    assert called["reset"] == 1
