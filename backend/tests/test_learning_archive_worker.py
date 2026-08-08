"""Unit tests for safe, offline-readable learner exports."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from backend.learning.workers.course_lifecycle_jobs import ExportTooLarge, build_export_zip
from backend.learning.workers import course_lifecycle_jobs as lifecycle
from backend.learning.workers import process_learning_submission_jobs as worker


def _snapshot() -> dict:
    return {
        "course": {"id": "course-1", "title": "Politik 10", "school_year_start": 2025},
        "cutoff_at": "2026-07-01T12:00:00+00:00",
        "submissions": [
            {
                "id": "submission-1", "kind": "file", "created_at": "2026-06-01T10:00:00+00:00",
                "text_body": None, "feedback_md": "<script>alert(1)</script> Gute Arbeit",
                "analysis_json": {"criteria": ["begründet"]}, "storage_key": "private/student/../lösung.pdf",
                "mime_type": "application/pdf", "task_snapshot": {"instruction_md": "Begründe <b>sachlich</b>."},
            }
        ],
    }


def test_export_zip_is_offline_readable_and_escapes_content() -> None:
    archive = build_export_zip(_snapshot(), load_file=lambda _key: b"PDF", max_bytes=100_000)
    with zipfile.ZipFile(io.BytesIO(archive)) as result:
        assert {"index.html", "manifest.json"}.issubset(result.namelist())
        assert all(".." not in name for name in result.namelist())
        html = result.read("index.html").decode("utf-8")
        assert "&lt;script&gt;" in html
        assert "<script" not in html
        assert "http://" not in html and "https://" not in html
        manifest = json.loads(result.read("manifest.json"))
        assert manifest["course"]["title"] == "Politik 10"
        assert len(manifest["submissions"]) == 1


def test_export_fails_atomically_when_limit_is_exceeded() -> None:
    with pytest.raises(ExportTooLarge):
        build_export_zip(_snapshot(), load_file=lambda _key: b"x" * 20_000, max_bytes=1_000)


def test_course_deletions_are_not_starved_by_expired_export_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(worker, "process_export_once", lambda **_kwargs: calls.append("export") or False)
    monkeypatch.setattr(worker, "process_deletion_once", lambda **_kwargs: calls.append("delete") or True)
    monkeypatch.setattr(worker, "process_expired_export_once", lambda **_kwargs: calls.append("expire") or True)

    processed = worker.run_lifecycle_once(dsn="postgresql://worker", storage_adapter=object())

    assert processed is True
    assert calls == ["export", "delete", "expire"]


class _Cursor:
    def __init__(self, connection: "_Connection") -> None:
        self.connection = connection

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: object = None) -> None:
        self.connection.queries.append((" ".join(query.split()), params))

    def fetchone(self) -> object:
        return self.connection.rows.pop(0)


class _Connection:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.queries: list[tuple[str, object]] = []
        self.commits = 0

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        self.commits += 1


def test_course_deletion_worker_uses_leased_commands_not_direct_table_dml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection(
        [
            ("delete_object", "job-1", "outbox-1", "submissions", "private/file", "lease-1"),
            (True,),
        ]
    )
    deleted: list[tuple[str, str]] = []
    adapter = type(
        "Storage",
        (),
        {"delete_object": lambda _self, *, bucket, key: deleted.append((bucket, key))},
    )()
    monkeypatch.setattr(lifecycle.psycopg, "connect", lambda _dsn: connection)

    assert lifecycle.process_deletion_once(dsn="postgresql://worker", storage_adapter=adapter)

    assert deleted == [("submissions", "private/file")]
    sql = " ".join(query for query, _params in connection.queries)
    assert "learning_worker_claim_course_deletion" in sql
    assert "learning_worker_complete_storage_deletion" in sql
    assert "update public.course_deletion_jobs" not in sql
    assert "update public.storage_deletion_outbox" not in sql


def test_failed_storage_deletion_is_nacked_through_the_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection(
        [
            ("delete_object", "job-1", "outbox-1", "submissions", "private/file", "lease-1"),
            (True,),
        ]
    )
    adapter = type(
        "Storage",
        (),
        {"delete_object": lambda _self, **_kwargs: (_ for _ in ()).throw(RuntimeError())},
    )()
    monkeypatch.setattr(lifecycle.psycopg, "connect", lambda _dsn: connection)

    assert lifecycle.process_deletion_once(dsn="postgresql://worker", storage_adapter=adapter)

    sql = " ".join(query for query, _params in connection.queries)
    assert "learning_worker_fail_storage_deletion" in sql
    assert "storage_delete_failed" in str(connection.queries[-1][1])


def test_expired_export_cleanup_uses_a_recoverable_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _Connection([("export-1", "exports/export-1.zip", "lease-1"), (True,)])
    deleted: list[tuple[str, str]] = []
    adapter = type(
        "Storage",
        (),
        {"delete_object": lambda _self, *, bucket, key: deleted.append((bucket, key))},
    )()
    monkeypatch.setattr(lifecycle.psycopg, "connect", lambda _dsn: connection)

    assert lifecycle.process_expired_export_once(
        dsn="postgresql://worker", storage_adapter=adapter
    )

    assert deleted == [("learning-exports", "exports/export-1.zip")]
    sql = " ".join(query for query, _params in connection.queries)
    assert "learning_worker_claim_expired_export" in sql
    assert "learning_worker_complete_expired_export" in sql
    assert "update public.learning_export_jobs" not in sql


class _ScriptedCursor:
    def __init__(self, connection: "_ScriptedConnection") -> None:
        self.connection = connection
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql: str, params=None) -> None:
        self.connection.queries.append((" ".join(sql.split()), params))
        self.row = self.connection.rows.pop(0) if self.connection.rows else None

    def fetchone(self):
        return self.row


class _ScriptedConnection:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.queries: list[tuple[str, object]] = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self) -> _ScriptedCursor:
        return _ScriptedCursor(self)

    def commit(self) -> None:
        self.commits += 1


def test_expired_export_cleanup_persists_failure_backoff_through_worker_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _ScriptedConnection(
        [("export-1", "exports/export-1.zip", "lease-1"), (True,)]
    )

    class Storage:
        def delete_object(self, **_kwargs) -> None:
            raise RuntimeError("temporary storage failure")

    monkeypatch.setattr(lifecycle.psycopg, "connect", lambda _dsn: connection)

    assert lifecycle.process_expired_export_once(
        dsn="postgresql://worker",
        storage_adapter=Storage(),
    )

    sql = " ".join(query for query, _params in connection.queries)
    assert "learning_worker_claim_expired_export" in sql
    assert "learning_worker_fail_expired_export" in sql
    assert "update public.learning_export_jobs" not in sql
