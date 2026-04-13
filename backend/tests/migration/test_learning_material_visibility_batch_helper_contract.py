"""
DB contract for batched student material visibility lookups.

Why:
    Learning material lists should keep one set-based DB path for visible file
    materials. The batch helper must not fall back to per-material modular
    unlock checks, otherwise the Python-side batching only hides an SQL N+1.
"""

from __future__ import annotations

import os

import pytest

from backend.tests.utils.db import require_db_or_skip as _require_db_or_skip


_BATCH_SIG = "public.get_material_file_metadata_batch_for_student(text, uuid, uuid[])"
_SINGLE_SIG = "public.get_material_file_metadata_for_student(text, uuid, uuid)"


def _dsn() -> str:
    host = os.getenv("TEST_DB_HOST", "127.0.0.1")
    port = os.getenv("TEST_DB_PORT", "54322")
    user = os.getenv("APP_DB_USER", "gustav_app")
    password = os.getenv("APP_DB_PASSWORD", "CHANGE_ME_DEV")
    return os.getenv("DATABASE_URL") or f"postgresql://{user}:{password}@{host}:{port}/postgres"


@pytest.mark.anyio
async def test_material_visibility_batch_helper_is_set_based_for_modular_unlocks() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select to_regprocedure(%s)", (_BATCH_SIG,))
            batch_regproc = (cur.fetchone() or [None])[0]
            assert batch_regproc is not None, "Batch helper migration not applied."

            cur.execute("select pg_get_functiondef(to_regprocedure(%s))", (_BATCH_SIG,))
            batch_body = str((cur.fetchone() or [""])[0] or "").lower()

    assert "public.get_modular_unit_module_states_for_student(" in batch_body
    assert "public.modular_section_is_open_or_done_for_student(" not in batch_body


@pytest.mark.anyio
async def test_material_visibility_single_helper_delegates_to_batch_helper() -> None:
    _require_db_or_skip()
    try:
        import psycopg  # type: ignore
    except Exception:
        pytest.skip("psycopg not available")

    with psycopg.connect(_dsn()) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("select to_regprocedure(%s)", (_SINGLE_SIG,))
            single_regproc = (cur.fetchone() or [None])[0]
            assert single_regproc is not None, "Single-material helper missing."

            cur.execute("select pg_get_functiondef(to_regprocedure(%s))", (_SINGLE_SIG,))
            single_body = str((cur.fetchone() or [""])[0] or "").lower()

    assert "get_material_file_metadata_batch_for_student(" in single_body
