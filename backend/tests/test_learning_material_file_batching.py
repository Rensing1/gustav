from __future__ import annotations

import importlib
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Iterator

import pytest


class _FakeCursor:
    def __init__(self, fetchone_results=None, fetchall_results=None) -> None:
        self.fetchone_results = list(fetchone_results or [])
        self.fetchall_results = list(fetchall_results or [])
        self.execute_calls: list[tuple[str, object]] = []

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return None

    def execute(self, query, params=None):  # type: ignore[no-untyped-def]
        self.execute_calls.append((" ".join(str(query).split()), params))

    def fetchone(self):  # type: ignore[no-untyped-def]
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None

    def fetchall(self):  # type: ignore[no-untyped-def]
        if self.fetchall_results:
            return self.fetchall_results.pop(0)
        return []


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return None

    def cursor(self) -> _FakeCursor:
        return self._cursor


def _patch_material_cursor(
    monkeypatch: pytest.MonkeyPatch, *, cursor: _FakeCursor, connect_calls: list[str]
) -> None:
    material_access = importlib.import_module("backend.web.material_file_access")

    @contextmanager
    def _fake_open_repo_cursor(
        *, repo=None, dsn=None
    ) -> Iterator[tuple[_FakeConnection, _FakeCursor]]:  # noqa: ANN001
        raw_dsn = str(dsn if dsn is not None else getattr(repo, "_dsn", "") or "")
        connect_calls.append(raw_dsn)
        yield _FakeConnection(cursor), cursor

    monkeypatch.setattr(material_access, "open_repo_cursor", _fake_open_repo_cursor)


def test_attach_section_material_files_batches_storage_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = importlib.import_module("backend.web.routes.learning")

    cursor = _FakeCursor(
        fetchall_results=[
            [
                (
                    "11111111-1111-1111-1111-111111111111",
                    "44444444-4444-4444-8444-444444444444",
                    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "file",
                    "application/pdf",
                    1024,
                    "materials/one.pdf",
                    "one.pdf",
                ),
                (
                    "22222222-2222-2222-2222-222222222222",
                    "44444444-4444-4444-8444-444444444444",
                    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "file",
                    "application/pdf",
                    1024,
                    "materials/two.pdf",
                    "two.pdf",
                ),
            ]
        ]
    )
    connect_calls: list[str] = []

    monkeypatch.setattr(learning, "_get_repo", lambda: SimpleNamespace(_dsn="postgresql://test"))
    _patch_material_cursor(monkeypatch, cursor=cursor, connect_calls=connect_calls)

    payload = learning._attach_section_material_files(
        student_sub="student-1",
        course_id="33333333-3333-4333-8333-333333333333",
        sections=[
            {
                "section": {"id": "44444444-4444-4444-8444-444444444444"},
                "materials": [
                    {"id": "11111111-1111-1111-1111-111111111111", "kind": "file"},
                    {"id": "22222222-2222-2222-2222-222222222222", "kind": "file"},
                ],
            }
        ],
    )

    assert len(connect_calls) == 1
    assert payload[0]["materials"][0]["file_url"] == (
        "/api/learning/courses/33333333-3333-4333-8333-333333333333/materials/"
        "11111111-1111-1111-1111-111111111111/file"
        "?disposition=inline"
    )
    assert payload[0]["materials"][1]["file_url"] == (
        "/api/learning/courses/33333333-3333-4333-8333-333333333333/materials/"
        "22222222-2222-2222-2222-222222222222/file"
        "?disposition=inline"
    )
    assert len(cursor.execute_calls) == 3
    assert any(
        "get_material_asset_metadata_batch_for_student" in query
        for query, _ in cursor.execute_calls
    )
    assert not any(
        "get_material_file_metadata_for_student" in query for query, _ in cursor.execute_calls
    )


def test_attach_modular_material_files_batches_storage_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = importlib.import_module("backend.web.routes.learning")

    cursor = _FakeCursor(
        fetchall_results=[
            [
                (
                    "55555555-5555-4555-8555-555555555555",
                    "77777777-7777-4777-8777-777777777777",
                    "88888888-8888-4888-8888-888888888888",
                    "file",
                    "application/pdf",
                    1024,
                    "materials/mod-one.pdf",
                    "mod-one.pdf",
                ),
                (
                    "66666666-6666-4666-8666-666666666666",
                    "77777777-7777-4777-8777-777777777777",
                    "88888888-8888-4888-8888-888888888888",
                    "file",
                    "application/pdf",
                    1024,
                    "materials/mod-two.pdf",
                    "mod-two.pdf",
                ),
            ]
        ],
    )
    connect_calls: list[str] = []

    monkeypatch.setattr(learning, "_get_repo", lambda: SimpleNamespace(_dsn="postgresql://test"))
    _patch_material_cursor(monkeypatch, cursor=cursor, connect_calls=connect_calls)

    payload = learning._attach_modular_material_files(
        student_sub="student-1",
        course_id="33333333-3333-4333-8333-333333333333",
        unit_id="88888888-8888-4888-8888-888888888888",
        module_id="99999999-9999-4999-8999-999999999999",
        payload={
            "materials": [
                {"id": "55555555-5555-4555-8555-555555555555", "kind": "file"},
                {"id": "66666666-6666-4666-8666-666666666666", "kind": "file"},
            ]
        },
    )

    assert len(connect_calls) == 1
    assert payload["materials"][0]["file_url"] == (
        "/api/learning/courses/33333333-3333-4333-8333-333333333333/materials/"
        "55555555-5555-4555-8555-555555555555/file"
        "?disposition=inline"
    )
    assert payload["materials"][1]["file_url"] == (
        "/api/learning/courses/33333333-3333-4333-8333-333333333333/materials/"
        "66666666-6666-4666-8666-666666666666/file"
        "?disposition=inline"
    )
    assert len(cursor.execute_calls) == 3
    assert any(
        "get_material_asset_metadata_batch_for_student" in query
        for query, _ in cursor.execute_calls
    )
    assert not any(
        "get_material_file_metadata_for_student" in query for query, _ in cursor.execute_calls
    )


def test_attach_section_material_files_enriches_simulation_with_one_asset_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    material_id = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    section_id = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
    unit_id = "cccccccc-3333-4333-8333-cccccccccccc"
    course_id = "dddddddd-4444-4444-8444-dddddddddddd"
    cursor = _FakeCursor(
        fetchall_results=[
            [
                (
                    material_id,
                    section_id,
                    unit_id,
                    "simulation",
                    "text/html",
                    2048,
                    "materials/parlament.html",
                    "parlament.html",
                )
            ]
        ]
    )
    connect_calls: list[str] = []

    monkeypatch.setattr(learning, "_get_repo", lambda: SimpleNamespace(_dsn="postgresql://test"))
    _patch_material_cursor(monkeypatch, cursor=cursor, connect_calls=connect_calls)

    payload = learning._attach_section_material_files(
        student_sub="student-1",
        course_id=course_id,
        sections=[
            {
                "section": {"id": section_id},
                "materials": [{"id": material_id, "kind": "simulation"}],
            }
        ],
    )

    assert len(connect_calls) == 1
    assert payload[0]["materials"][0]["file_url"] is None
    assert payload[0]["materials"][0]["simulation_url"] == (
        f"/api/learning/courses/{course_id}/materials/{material_id}/simulation"
    )
    assert len(cursor.execute_calls) == 3
    assert any(
        "get_material_asset_metadata_batch_for_student" in query
        for query, _ in cursor.execute_calls
    )
