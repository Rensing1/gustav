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


def test_constraint_supports_feedback_invalid_analysis_detects_allowed_code() -> None:
    definition = (
        "CHECK ((error_code IS NULL) OR (error_code = ANY "
        "(ARRAY['feedback_failed'::text, 'feedback_invalid_analysis'::text])))"
    )
    assert mod.constraint_supports_feedback_invalid_analysis(definition) is True


def test_constraint_supports_feedback_invalid_analysis_rejects_missing_code() -> None:
    definition = "CHECK ((error_code = ANY (ARRAY['vision_failed'::text, 'feedback_failed'::text])))"
    assert mod.constraint_supports_feedback_invalid_analysis(definition) is False


def test_result_signature_exposes_h5p_score_columns() -> None:
    signature = "TABLE(student_sub text, task_id uuid, score_raw integer, score_max integer)"
    assert mod.result_signature_supports_latest_h5p_scores(signature) is True


def test_result_signature_rejects_missing_h5p_score_columns() -> None:
    signature = "TABLE(student_sub text, task_id uuid, h5p_completed boolean)"
    assert mod.result_signature_supports_latest_h5p_scores(signature) is False


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
    monkeypatch.setattr(mod, "fetch_learning_submissions_error_code_constraintdef", lambda _conn: "feedback_invalid_analysis")
    monkeypatch.setattr(
        mod,
        "fetch_live_h5p_helper_result_signature",
        lambda _conn: "TABLE(student_sub text, task_id uuid, score_raw integer, score_max integer)",
    )
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 2
    assert "does not allow kind='calliope'" in err.getvalue()


def test_run_preflight_returns_error_when_feedback_invalid_analysis_is_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    row = ("CHECK ((kind = ANY (ARRAY['native'::text, 'calliope'::text])))",)
    monkeypatch.setattr(mod, "_connect", lambda _dsn: _FakeConn(row))
    monkeypatch.setattr(
        mod,
        "fetch_learning_submissions_error_code_constraintdef",
        lambda _conn: "CHECK ((error_code = ANY (ARRAY['vision_failed'::text, 'feedback_failed'::text])))",
    )
    monkeypatch.setattr(
        mod,
        "fetch_live_h5p_helper_result_signature",
        lambda _conn: "TABLE(student_sub text, task_id uuid, score_raw integer, score_max integer)",
    )
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 2
    assert "feedback_invalid_analysis" in err.getvalue()


def test_run_preflight_returns_error_when_h5p_helper_columns_are_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    row = ("CHECK ((kind = ANY (ARRAY['native'::text, 'calliope'::text])))",)
    monkeypatch.setattr(mod, "_connect", lambda _dsn: _FakeConn(row))
    monkeypatch.setattr(
        mod,
        "fetch_learning_submissions_error_code_constraintdef",
        lambda _conn: "CHECK ((error_code = ANY (ARRAY['feedback_invalid_analysis'::text, 'feedback_failed'::text])))",
    )
    monkeypatch.setattr(
        mod,
        "fetch_live_h5p_helper_result_signature",
        lambda _conn: "TABLE(student_sub text, task_id uuid, h5p_completed boolean)",
    )
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 2
    assert "score_raw/score_max" in err.getvalue()


def test_run_preflight_succeeds_when_calliope_is_allowed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    row = ("CHECK ((kind = ANY (ARRAY['native'::text, 'calliope'::text])))",)
    monkeypatch.setattr(mod, "_connect", lambda _dsn: _FakeConn(row))
    monkeypatch.setattr(
        mod,
        "fetch_learning_submissions_error_code_constraintdef",
        lambda _conn: "CHECK ((error_code = ANY (ARRAY['feedback_invalid_analysis'::text, 'feedback_failed'::text])))",
    )
    monkeypatch.setattr(
        mod,
        "fetch_live_h5p_helper_result_signature",
        lambda _conn: "TABLE(student_sub text, task_id uuid, score_raw integer, score_max integer)",
    )
    out = io.StringIO()
    err = io.StringIO()
    rc = mod.run_preflight(dsn="postgresql://x", out=out, err=err)
    assert rc == 0
    assert "DB preflight OK" in out.getvalue()
    assert err.getvalue() == ""
