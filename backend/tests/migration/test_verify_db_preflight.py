from __future__ import annotations

import io

from backend.tools import verify_db_preflight as mod


class _FakeCursor:
    def __init__(self, row: tuple[str] | None) -> None:
        self._row = row
        self.executed_sql = ""

    def execute(self, sql: str) -> None:
        self.executed_sql = sql

    def fetchone(self) -> tuple[str] | None:
        return self._row

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


class _FakeConn:
    def __init__(self, row: tuple[str] | None) -> None:
        self._row = row

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._row)

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


def test_build_dsn_prefers_database_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@db.local:5432/app")
    assert mod.build_dsn() == "postgresql://x:y@db.local:5432/app"


def test_build_dsn_uses_local_defaults(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DB_HOST", raising=False)
    monkeypatch.delenv("TEST_DB_PORT", raising=False)
    monkeypatch.delenv("APP_DB_USER", raising=False)
    monkeypatch.delenv("APP_DB_PASSWORD", raising=False)
    assert mod.build_dsn() == "postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"


def test_constraint_supports_calliope_detects_allowed_kind() -> None:
    definition = "CHECK ((kind = ANY (ARRAY['native'::text, 'calliope'::text])))"
    assert mod.constraint_supports_calliope(definition) is True


def test_constraint_supports_calliope_rejects_missing_or_other_kinds() -> None:
    assert mod.constraint_supports_calliope(None) is False
    assert mod.constraint_supports_calliope("CHECK ((kind = ANY (ARRAY['native'::text, 'h5p'::text])))") is False


def test_fetch_unit_tasks_kind_constraintdef_reads_pg_constraint() -> None:
    conn = _FakeConn(("CHECK ((kind = ANY (ARRAY['native'::text, 'calliope'::text])))",))
    got = mod.fetch_unit_tasks_kind_constraintdef(conn)
    assert got and "calliope" in got


def test_run_preflight_returns_error_when_db_unreachable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _fail_connect(_dsn: str):
        raise RuntimeError("db_down")

    monkeypatch.setattr(mod, "_connect", _fail_connect)
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 2
    assert "Database preflight failed" in err.getvalue()
    assert "supabase migration up" in err.getvalue()


def test_run_preflight_returns_error_when_constraint_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(mod, "_connect", lambda _dsn: _FakeConn(None))
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 2
    assert "unit_tasks_kind_check is missing" in err.getvalue()


def test_run_preflight_returns_error_when_calliope_is_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    row = ("CHECK ((kind = ANY (ARRAY['native'::text, 'h5p'::text])))",)
    monkeypatch.setattr(mod, "_connect", lambda _dsn: _FakeConn(row))
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 2
    assert "does not allow kind='calliope'" in err.getvalue()


def test_run_preflight_succeeds_when_calliope_is_allowed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    row = ("CHECK ((kind = ANY (ARRAY['native'::text, 'calliope'::text])))",)
    monkeypatch.setattr(mod, "_connect", lambda _dsn: _FakeConn(row))
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 0
    assert "DB preflight OK" in out.getvalue()
    assert err.getvalue() == ""
