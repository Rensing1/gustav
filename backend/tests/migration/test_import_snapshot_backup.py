from __future__ import annotations

import argparse
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


def test_reset_db_for_restore_only_drops_app_schemas(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class FakeCompleted:
        def __init__(self) -> None:
            self.stdout = ""

    def fake_run(cmd: list[str], **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return FakeCompleted()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod._reset_db_for_restore("postgresql://u:p@127.0.0.1:54322/postgres")

    assert len(calls) == 2
    assert "where nspname in ('legacy_raw', 'public')" in (calls[0][-1] or "").lower()
    assert "drop schema if exists %i cascade" in (calls[0][-1] or "").lower()
    assert "auth" not in (calls[0][-1] or "").lower()
    assert "drop extension" not in (calls[0][-1] or "").lower()
    assert "create schema" in (calls[1][-1] or "").lower()
    assert "public" in (calls[1][-1] or "").lower()


def test_normalize_restore_target_ownership_updates_app_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class FakeCompleted:
        def __init__(self) -> None:
            self.stdout = ""

    def fake_run(cmd: list[str], **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return FakeCompleted()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod._normalize_restore_target_ownership("postgresql://u:p@127.0.0.1:54322/postgres", "postgres")

    assert len(calls) == 1
    sql = calls[0][-1].lower()
    assert "alter schema %i owner to %i" in sql
    assert "alter table %i.%i owner to %i" in sql
    assert "alter sequence %i.%i owner to %i" in sql
    assert "alter function %i.%i(%s) owner to %i" in sql
    assert "'legacy_raw', 'public'" in sql
    assert "target_owner text := 'postgres'" in sql


def test_main_normalizes_restore_target_ownership_after_restore(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    db_dump = snapshot_dir / "supabase_db.sql.gz"
    storage_tar = snapshot_dir / "storage_buckets.tar.gz"
    db_dump.write_bytes(b"dummy")
    storage_tar.write_bytes(b"dummy")

    args = argparse.Namespace(
        snapshot=str(snapshot_dir),
        dsn="postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres",
        supabase_url=None,
        supabase_service_role_key=None,
        workdir=str(tmp_path / "workdir"),
        no_reset=False,
        skip_storage=True,
        skip_keycloak=True,
        keycloak_db_container="gustav-keycloak-db",
        keycloak_db_user="keycloak",
        keycloak_db_name="keycloak",
        keycloak_container="gustav-keycloak",
        keycloak_realm="gustav",
        keycloak_web_client_id="gustav-web",
        keycloak_web_base="https://app.localhost",
        keycloak_admin_realm="gustav",
        keycloak_admin_client_id="gustav-admin-cli",
        keycloak_admin_client_secret="",
        dry_run=False,
        allow_remote_dsn=False,
        verbose=False,
    )

    owner_calls: list[tuple[str, str]] = []
    sync_calls: list[tuple[str, list[mod.SnapshotMigration]]] = []

    monkeypatch.setattr(mod, "parse_args", lambda: args)
    monkeypatch.setattr(mod, "configure_logging", lambda _verbose: None)
    monkeypatch.setattr(mod, "resolve_snapshot_files", lambda *_args: mod.SnapshotFiles(snapshot_dir, db_dump, storage_tar))
    monkeypatch.setattr(
        mod,
        "extract_snapshot_migration_history",
        lambda _dump: [
            mod.SnapshotMigration(
                "20260223122000",
                "{\"select 1\"}",
                "storage_submissions_bucket_allow_makecode_hex",
                "20260223122000\t{\"select 1\"}\tstorage_submissions_bucket_allow_makecode_hex",
            )
        ],
    )
    monkeypatch.setattr(mod, "_psql_check", lambda _dsn: None)
    monkeypatch.setattr(mod, "ensure_superuser_for_reset", lambda _dsn: True)
    monkeypatch.setattr(mod, "_reset_db_for_restore", lambda _dsn: None)
    monkeypatch.setattr(mod, "_restore_db_sql_gz", lambda _dump, _dsn: None)
    monkeypatch.setattr(mod, "_ensure_graphql_public_function", lambda _dsn: None)
    monkeypatch.setattr(
        mod,
        "_normalize_restore_target_ownership",
        lambda dsn, owner: owner_calls.append((dsn, owner)),
    )
    monkeypatch.setattr(mod, "sync_snapshot_migration_history", lambda dsn, rows: sync_calls.append((dsn, rows)))

    assert mod.main() == 0
    assert owner_calls == [(args.dsn, "postgres")]
    assert sync_calls == [
        (
            args.dsn,
            [
                mod.SnapshotMigration(
                    "20260223122000",
                    "{\"select 1\"}",
                    "storage_submissions_bucket_allow_makecode_hex",
                    "20260223122000\t{\"select 1\"}\tstorage_submissions_bucket_allow_makecode_hex",
                )
            ],
        )
    ]


def test_extract_snapshot_migration_history_reads_supabase_copy_block(tmp_path: Path) -> None:
    dump_path = tmp_path / "supabase_db.sql.gz"
    with gzip.open(dump_path, "wt", encoding="utf-8") as f:
        f.write("SET statement_timeout = 0;\n")
        f.write("COPY supabase_migrations.schema_migrations (version, statements, name) FROM stdin;\n")
        f.write("20260223122000\t{\"select 1\"}\tstorage_submissions_bucket_allow_makecode_hex\n")
        f.write("20260314124500\t{\"select 2\"}\tlearning_worker_feedback_invalid_analysis\n")
        f.write("\\.\n")

    rows = mod.extract_snapshot_migration_history(dump_path)

    assert [row.version for row in rows] == ["20260223122000", "20260314124500"]
    assert rows[-1].name == "learning_worker_feedback_invalid_analysis"
    assert rows[-1].statements == "{\"select 2\"}"
    assert rows[-1].copy_line == (
        "20260314124500\t{\"select 2\"}\tlearning_worker_feedback_invalid_analysis"
    )


def test_sync_snapshot_migration_history_replaces_local_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    stdin_payload: list[str] = []

    class FakeStdin:
        def write(self, chunk: str) -> None:
            stdin_payload.append(chunk)

        def close(self) -> None:
            return None

    class FakeProc:
        def __init__(self) -> None:
            self.stdin = FakeStdin()

        def wait(self) -> int:
            return 0

    def fake_popen(cmd: list[str], **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return FakeProc()

    monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)

    mod.sync_snapshot_migration_history(
        "postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres",
        [
            mod.SnapshotMigration(
                version="20260223122000",
                statements="{\"select 1\"}",
                name="storage_submissions_bucket_allow_makecode_hex",
                copy_line="20260223122000\t{\"select 1\"}\tstorage_submissions_bucket_allow_makecode_hex",
            ),
            mod.SnapshotMigration(
                version="20260314124500",
                statements="{\"select 2\"}",
                name="learning_worker_feedback_invalid_analysis",
                copy_line="20260314124500\t{\"select 2\"}\tlearning_worker_feedback_invalid_analysis",
            ),
        ],
    )

    assert calls == [["psql", "postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres", "-v", "ON_ERROR_STOP=1"]]
    payload = "".join(stdin_payload)
    assert "truncate table supabase_migrations.schema_migrations;\n" in payload.lower()
    assert "copy supabase_migrations.schema_migrations(version, statements, name) from stdin;\n" in payload.lower()
    assert "20260223122000\t{\"select 1\"}\tstorage_submissions_bucket_allow_makecode_hex\n" in payload
    assert "20260314124500\t{\"select 2\"}\tlearning_worker_feedback_invalid_analysis\n" in payload
    assert payload.endswith("\\.\n")


def test_filter_dump_lines_skips_managed_schema_objects_but_keeps_public_data() -> None:
    dump_lines = [
        b"SET row_security = off;\n",
        b"\n",
        b"--\n",
        b"-- Name: auth; Type: SCHEMA; Schema: -; Owner: -\n",
        b"--\n",
        b"\n",
        b"CREATE SCHEMA auth;\n",
        b"\n",
        b"--\n",
        b"-- Name: users; Type: TABLE; Schema: auth; Owner: -\n",
        b"--\n",
        b"\n",
        b"CREATE TABLE auth.users (\n",
        b"    id uuid\n",
        b");\n",
        b"\n",
        b"--\n",
        b"-- Name: users; Type: TABLE DATA; Schema: auth; Owner: -\n",
        b"--\n",
        b"\n",
        b"COPY auth.users (id) FROM stdin;\n",
        b"00000000-0000-0000-0000-000000000001\n",
        b"\\.\n",
        b"\n",
        b"--\n",
        b"-- Name: courses; Type: TABLE; Schema: public; Owner: -\n",
        b"--\n",
        b"\n",
        b"CREATE TABLE public.courses (\n",
        b"    id uuid\n",
        b");\n",
        b"\n",
        b"--\n",
        b"-- Name: courses; Type: TABLE DATA; Schema: public; Owner: -\n",
        b"--\n",
        b"\n",
        b"COPY public.courses (id) FROM stdin;\n",
        b"00000000-0000-0000-0000-000000000002\n",
        b"\\.\n",
    ]

    filtered = b"".join(mod._iter_filtered_dump_lines(dump_lines))

    assert b"SET row_security = off;" in filtered
    assert b"CREATE SCHEMA auth;" not in filtered
    assert b"CREATE TABLE auth.users" not in filtered
    assert b"COPY auth.users" not in filtered
    assert b"00000000-0000-0000-0000-000000000001" not in filtered
    assert b"CREATE TABLE public.courses" in filtered
    assert b"COPY public.courses" in filtered
    assert b"00000000-0000-0000-0000-000000000002" in filtered


def test_filter_dump_lines_skips_managed_copy_payload_and_terminator() -> None:
    dump_lines = [
        b"--\n",
        b"-- Name: migrations; Type: TABLE DATA; Schema: storage; Owner: -\n",
        b"--\n",
        b"\n",
        b"COPY storage.migrations (id) FROM stdin;\n",
        b"1\n",
        b"2\n",
        b"\\.\n",
        b"\n",
        b"--\n",
        b"-- Name: units; Type: TABLE DATA; Schema: public; Owner: -\n",
        b"--\n",
        b"\n",
        b"COPY public.units (id) FROM stdin;\n",
        b"3\n",
        b"\\.\n",
    ]

    filtered = b"".join(mod._iter_filtered_dump_lines(dump_lines))

    assert b"COPY storage.migrations" not in filtered
    assert b"\n1\n" not in filtered
    assert b"\n2\n" not in filtered
    assert filtered.count(b"\\.\n") == 1
    assert b"COPY public.units" in filtered
    assert b"\n3\n" in filtered


def test_filter_dump_lines_keeps_real_pg_dump_data_headers_for_public_tables() -> None:
    dump_lines = [
        b"--\n",
        b"-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: -\n",
        b"--\n",
        b"\n",
        b"COPY auth.users (id) FROM stdin;\n",
        b"1\n",
        b"\\.\n",
        b"\n",
        b"--\n",
        b"-- Data for Name: courses; Type: TABLE DATA; Schema: public; Owner: -\n",
        b"--\n",
        b"\n",
        b"COPY public.courses (id) FROM stdin;\n",
        b"2\n",
        b"\\.\n",
    ]

    filtered = b"".join(mod._iter_filtered_dump_lines(dump_lines))

    assert b"COPY auth.users" not in filtered
    assert b"\n1\n" not in filtered
    assert b"COPY public.courses" in filtered
    assert b"\n2\n" in filtered


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


def test_collect_storage_objects_strips_snapshot_version_suffix_from_key(tmp_path: Path) -> None:
    root = tmp_path / "storage_extracted"
    version = "da24679c-0bd2-472b-a4e7-d194e7659a60"
    logical_key = (
        "30e70a0e-b55c-4918-be90-82573329153c/"
        "16f30ed6-4698-42c1-bb88-f6323b3e8171/"
        "c02d4da4-471b-47bb-8444-0cca77682a9d/"
        "1772546358062-b843ef87bcb8416f8605d08f2fb6ecab.jpg"
    )
    file_path = root / "stub" / "stub" / "submissions" / logical_key / version
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"jpeg-bytes")

    objects, buckets, skipped = mod._collect_storage_objects(
        storage_root=root,
        bucket_ids={"submissions"},
    )

    assert buckets == {"submissions"}
    assert skipped == []
    assert [(bucket, key) for (bucket, key, _) in objects] == [("submissions", logical_key)]


def test_collect_storage_objects_strips_snapshot_version_suffix_for_pdf_key(tmp_path: Path) -> None:
    root = tmp_path / "storage_extracted"
    version = "3cdef07f-4a4e-42f6-a1d6-c1bdbd7237e4"
    logical_key = (
        "30e70a0e-b55c-4918-be90-82573329153c/"
        "193006fb-6ee0-459a-b0ab-7b4dd19d71a7/"
        "c02d4da4-471b-47bb-8444-0cca77682a9d/"
        "1769790779528-0ee5763906414d6da72ab1498a7d3874.pdf"
    )
    file_path = root / "backup" / "backup" / "submissions" / logical_key / version
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"%PDF")

    objects, buckets, skipped = mod._collect_storage_objects(
        storage_root=root,
        bucket_ids={"submissions"},
    )

    assert buckets == {"submissions"}
    assert skipped == []
    assert [(bucket, key) for (bucket, key, _) in objects] == [("submissions", logical_key)]


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
    allowlist_sync: dict[str, object] = {}

    def fake_sync_bucket_allowlists(_dsn: str, buckets) -> None:
        allowlist_sync["dsn"] = _dsn
        allowlist_sync["buckets"] = list(buckets)

    monkeypatch.setattr(mod, "_sync_bucket_allowlists", fake_sync_bucket_allowlists)

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
    assert allowlist_sync == {
        "dsn": "postgresql://u:p@127.0.0.1:54322/postgres",
        "buckets": ["section_materials", "submissions"],
    }

    urls = {c["url"] for c in fake_session.calls}
    assert "http://127.0.0.1:54321/storage/v1/object/section_materials/a%20b.txt" in urls
    assert "http://127.0.0.1:54321/storage/v1/object/submissions/%C3%BC.txt" in urls

    for call in fake_session.calls:
        headers = call["headers"]
        assert headers["apikey"] == "srk"
        assert headers["Authorization"] == "Bearer srk"
        assert headers["x-upsert"] == "true"


def test_sync_bucket_allowlists_adds_makecode_hex_for_submissions(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class FakeCompleted:
        def __init__(self) -> None:
            self.stdout = ""

    def fake_run(cmd: list[str], **_kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return FakeCompleted()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod._sync_bucket_allowlists(
        "postgresql://u:p@127.0.0.1:54322/postgres",
        ["materials", "submissions"],
    )

    assert len(calls) == 1
    sql = (calls[0][-1] or "").lower()
    assert "update storage.buckets" in sql
    assert "where id = 'submissions'" in sql
    assert "application/x.makecode.hex" in sql


def test_guess_content_type_prefers_key_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "bucket" / "x" / "1763317293475-e36ed3455e6249f5baa87127aa42991c.pdf" / "59682179-f7aa-48d4-bb51-a723705c3791"
    assert mod._guess_content_type(file_path, "bucket/1763317293475-e36ed3455e6249f5baa87127aa42991c.pdf/59682179-f7aa-48d4-bb51-a723705c3791") == "application/pdf"


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (
            "submissions/course/task/student/1771234567890-project.sb3/object-id",
            "application/x.scratch.sb3",
        ),
        (
            "submissions/course/task/student/1771234567890-robot.hex/object-id",
            "application/x.makecode.hex",
        ),
    ],
)
def test_guess_content_type_handles_snapshot_submission_extensions(
    tmp_path: Path, key: str, expected: str
) -> None:
    file_path = tmp_path / "bucket" / "opaque-object-id"

    assert mod._guess_content_type(file_path, key) == expected


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
