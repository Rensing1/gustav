from __future__ import annotations

from types import SimpleNamespace

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


def test_attach_section_material_files_batches_storage_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    import routes.learning as learning  # noqa: E402

    cursor = _FakeCursor(
        fetchall_results=[
            [
                ("11111111-1111-1111-1111-111111111111", "materials/one.pdf"),
                ("22222222-2222-2222-2222-222222222222", "materials/two.pdf"),
            ]
        ]
    )
    connect_calls: list[str] = []

    class _Adapter:
        def presign_download(self, *, bucket, key, expires_in, disposition):  # type: ignore[no-untyped-def]
            return {"url": f"http://storage.local/{key}"}

    monkeypatch.setattr(learning, "_get_repo", lambda: SimpleNamespace(_dsn="postgresql://test"))
    monkeypatch.setattr(learning, "_teaching_storage_adapter", lambda: _Adapter())
    monkeypatch.setattr(
        learning.psycopg,
        "connect",
        lambda dsn: connect_calls.append(dsn) or _FakeConnection(cursor),
    )

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
    assert payload[0]["materials"][0]["file_url"] == "http://storage.local/materials/one.pdf"
    assert payload[0]["materials"][1]["file_url"] == "http://storage.local/materials/two.pdf"
    assert len(cursor.execute_calls) == 2


def test_attach_modular_material_files_batches_storage_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    import routes.learning as learning  # noqa: E402

    cursor = _FakeCursor(
        fetchone_results=[(True,), (True,), ("77777777-7777-4777-8777-777777777777",), (True,)],
        fetchall_results=[
            [
                ("55555555-5555-4555-8555-555555555555", "materials/mod-one.pdf"),
                ("66666666-6666-4666-8666-666666666666", "materials/mod-two.pdf"),
            ]
        ],
    )
    connect_calls: list[str] = []

    class _Adapter:
        def presign_download(self, *, bucket, key, expires_in, disposition):  # type: ignore[no-untyped-def]
            return {"url": f"http://storage.local/{key}"}

    monkeypatch.setattr(learning, "_get_repo", lambda: SimpleNamespace(_dsn="postgresql://test"))
    monkeypatch.setattr(learning, "_teaching_storage_adapter", lambda: _Adapter())
    monkeypatch.setattr(
        learning.psycopg,
        "connect",
        lambda dsn: connect_calls.append(dsn) or _FakeConnection(cursor),
    )

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
    assert payload["materials"][0]["file_url"] == "http://storage.local/materials/mod-one.pdf"
    assert payload["materials"][1]["file_url"] == "http://storage.local/materials/mod-two.pdf"
    assert len(cursor.execute_calls) == 7
