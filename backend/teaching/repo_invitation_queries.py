"""PostgreSQL queries for course invitations.

Why:
    Invitation state changes must remain atomic and protected by PostgreSQL.
    This adapter only supplies the authenticated subject and maps the narrowly
    scoped SECURITY DEFINER function results into plain dictionaries.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _iso(value: Any) -> str | None:
    """Serialize database timestamps without changing their timezone."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _set_actor(cur, actor_sub: str) -> None:
    """Set the transaction-local identity consumed by RLS helpers."""

    cur.execute("select set_config('app.current_sub', %s, true)", (actor_sub,))


def create_invitation(
    *, dsn: str, psycopg_module, course_id: str, owner_sub: str, nonce: str
) -> dict[str, Any] | None:
    """Rotate and create the owner's 24-hour invitation in one transaction."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            _set_actor(cur, owner_sub)
            cur.execute(
                "select id::text, course_id::text, token_nonce, expires_at, created_at "
                "from public.create_course_invitation(%s, %s)",
                (course_id, nonce),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "course_id": row[1],
        "token_nonce": row[2],
        "expires_at": _iso(row[3]),
        "created_at": _iso(row[4]),
        "redemption_count": 0,
        "email_status": {"pending": 0, "sent": 0, "failed": 0},
    }


def get_active_invitation(
    *, dsn: str, psycopg_module, course_id: str, owner_sub: str
) -> dict[str, Any] | None:
    """Return the active invitation and aggregate counters to its owner."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            _set_actor(cur, owner_sub)
            cur.execute(
                """
                select id::text, course_id::text, token_nonce, expires_at, created_at,
                       redemption_count, pending_count, sent_count, failed_count
                  from public.get_active_course_invitation(%s)
                """,
                (course_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "course_id": row[1],
        "token_nonce": row[2],
        "expires_at": _iso(row[3]),
        "created_at": _iso(row[4]),
        "redemption_count": int(row[5]),
        "email_status": {
            "pending": int(row[6]),
            "sent": int(row[7]),
            "failed": int(row[8]),
        },
    }


def revoke_invitation(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    invitation_id: str,
    owner_sub: str,
) -> bool:
    """Revoke one invitation if the caller owns its course."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            _set_actor(cur, owner_sub)
            cur.execute(
                "select public.revoke_course_invitation(%s, %s)",
                (course_id, invitation_id),
            )
            row = cur.fetchone()
    return bool(row and row[0])


def preview_invitation(
    *, dsn: str, psycopg_module, invitation_id: str, nonce: str
) -> dict[str, Any] | None:
    """Resolve only the public, data-minimal invitation preview."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select course_title, expires_at "
                "from public.preview_course_invitation(%s, %s)",
                (invitation_id, nonce),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"course_title": row[0], "expires_at": _iso(row[1])}


def redeem_invitation(
    *, dsn: str, psycopg_module, invitation_id: str, nonce: str, student_sub: str
) -> dict[str, str] | None:
    """Atomically redeem an invitation for the authenticated learner."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            _set_actor(cur, student_sub)
            cur.execute(
                "select result, course_id::text "
                "from public.redeem_course_invitation(%s, %s)",
                (invitation_id, nonce),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"result": row[0], "course_id": row[1]}


def queue_mail_batch(
    *,
    dsn: str,
    psycopg_module,
    course_id: str,
    invitation_id: str,
    owner_sub: str,
    deliveries: list[dict[str, str]],
) -> dict[str, Any] | None:
    """Persist privacy-limited, independently deliverable mail jobs."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            _set_actor(cur, owner_sub)
            cur.execute(
                "select batch_id::text, queued, skipped_duplicates "
                "from public.queue_course_invite_mail_batch(%s, %s, %s::jsonb)",
                (course_id, invitation_id, json.dumps(deliveries)),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"batch_id": row[0], "queued": int(row[1]), "skipped_duplicates": int(row[2])}


def get_mail_status(
    *, dsn: str, psycopg_module, course_id: str, invitation_id: str, owner_sub: str
) -> dict[str, Any] | None:
    """Return aggregate delivery state and retry-relevant failed addresses."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            _set_actor(cur, owner_sub)
            cur.execute(
                "select pending, sent, failed, failed_recipients "
                "from public.get_course_invite_mail_status(%s, %s)",
                (course_id, invitation_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "pending": int(row[0]),
        "sent": int(row[1]),
        "failed": int(row[2]),
        "failed_recipients": list(row[3] or []),
    }


def retry_mail_deliveries(
    *, dsn: str, psycopg_module, course_id: str, invitation_id: str, owner_sub: str
) -> int | None:
    """Requeue retryable failed deliveries while the invitation stays valid."""

    with psycopg_module.connect(dsn) as conn:
        with conn.cursor() as cur:
            _set_actor(cur, owner_sub)
            cur.execute(
                "select public.retry_course_invite_mail_deliveries(%s, %s)",
                (course_id, invitation_id),
            )
            row = cur.fetchone()
    changed = int((row or [-1])[0])
    return None if changed < 0 else changed
