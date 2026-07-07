"""Small shared cursor helper for web-layer DB fallback paths.

Why:
    Several web routes still execute narrowly scoped SQL as part of product-safe
    compatibility paths. Those routes must stay explicit and readable, but should
    avoid repeating connection bootstrap code.

Design:
    - Single shared `psycopg.connect` construction path.
    - Lightweight failure mode when DSN or driver is unavailable.
    - Minimal context manager that yields `(conn, cursor)`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Tuple


try:
    import psycopg  # type: ignore
except Exception:  # pragma: no cover - defensive, exercised in tests when mocked
    psycopg = None  # type: ignore[assignment]


@contextmanager
def open_repo_cursor(*, repo: object | None = None, dsn: str | None = None) -> Iterator[Tuple[Any, Any]]:
    """Open a DB cursor for a repository-backed web fallback path.

    Args:
        repo: Repository-like object that exposes `_dsn`.
        dsn: Optional explicit DSN override.

    Yields:
        (conn, cursor)

    Raises:
        RuntimeError: When psycopg is unavailable or DSN is missing.
    """

    if psycopg is None:
        raise RuntimeError("psycopg3 is required for repository DB access")

    conn_dsn = dsn if dsn is not None else str(getattr(repo, "_dsn", "") or "")
    if not conn_dsn:
        raise RuntimeError("repository dsn is not available")

    with psycopg.connect(conn_dsn) as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:  # type: ignore[attr-defined]
            yield conn, cur
