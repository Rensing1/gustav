"""PostgreSQL integration test for worker-only invitation mail cleanup."""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from backend.teaching.course_invitation_mail import (
    PostgresCourseInviteMailRepository,
    SmtpSettings,
    process_course_invitation_mail_once,
)
from backend.teaching.course_invitations import recipient_digest
from backend.teaching.repo_db import DBTeachingRepo
from backend.tests.utils.db import require_db_or_skip


pytestmark = pytest.mark.db_write

SERVICE_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
APP_DSN = "postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres"
WORKER_DSN = "postgresql://gustav_worker:CHANGE_ME_DEV@127.0.0.1:54322/postgres"
SIGNING_SECRET = "test-course-invite-secret-with-32-bytes"


class AcceptingSmtp:
    def __init__(self, *_args, **_kwargs):
        self.messages = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def ehlo(self):
        return None

    def starttls(self, *, context):
        assert context.check_hostname is True
        return None

    def send_message(self, message):
        self.messages.append(message)


def test_worker_sends_and_immediately_erases_successful_plaintext_address() -> None:
    require_db_or_skip()
    course_id = str(uuid4())
    owner_sub = f"mail-owner-{uuid4()}"
    address = "worker-test@school.example"

    try:
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.courses(
                    id, title, subject, grade_level, school_year_start, teacher_id, status
                ) values (%s, 'Worker-Mail-Test', 'Informatik', '9', 2026, %s, 'active')
                """,
                (course_id, owner_sub),
            )

        repo = DBTeachingRepo(APP_DSN)
        invitation = repo.create_course_invitation(
            course_id, owner_sub, "database-worker-nonce-with-32-characters"
        )
        assert invitation is not None
        digest = recipient_digest(address, invitation["id"], SIGNING_SECRET)
        queued = repo.queue_course_invite_mail_batch(
            course_id,
            invitation["id"],
            owner_sub,
            [{"email": address, "digest": digest}],
        )
        assert queued and queued["queued"] == 1
        # Keep this integration test deterministic even when another local test
        # left a newer invitation delivery in the shared developer database.
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "update public.course_invite_mail_deliveries "
                "set next_attempt_at = '2000-01-01T00:00:00Z' where invitation_id = %s",
                (invitation["id"],),
            )

        assert process_course_invitation_mail_once(
            dsn=WORKER_DSN,
            settings=SmtpSettings(
                host="smtp.test",
                port=1025,
                username="",
                password="",
                from_email="noreply@school.example",
                from_name="GUSTAV-Lernplattform",
                use_starttls=True,
            ),
            signing_secret=SIGNING_SECRET,
            web_base="https://app.localhost",
            smtp_factory=AcceptingSmtp,
        ) is True

        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "select status, recipient_email, recipient_digest "
                "from public.course_invite_mail_deliveries where invitation_id = %s",
                (invitation["id"],),
            )
            row = cur.fetchone()
        assert row == ("sent", None, digest)
    finally:
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute("delete from public.courses where id = %s", (course_id,))


@pytest.mark.parametrize("dsn", [APP_DSN, WORKER_DSN])
def test_invitation_mail_tables_are_not_directly_readable(dsn: str) -> None:
    """Application and worker roles may use only their narrow definer functions."""

    require_db_or_skip()
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("select recipient_email from public.course_invite_mail_deliveries")


def test_only_transient_failures_can_be_retried_and_addresses_are_purged() -> None:
    require_db_or_skip()
    course_id = str(uuid4())
    owner_sub = f"retry-owner-{uuid4()}"
    address = f"retry-{uuid4()}@school.example"

    try:
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.courses(
                    id, title, subject, grade_level, school_year_start, teacher_id, status
                ) values (%s, 'Retry-Test', 'Informatik', '9', 2026, %s, 'active')
                """,
                (course_id, owner_sub),
            )

        app_repo = DBTeachingRepo(APP_DSN)
        invitation = app_repo.create_course_invitation(
            course_id, owner_sub, "retry-database-nonce-with-32-characters"
        )
        assert invitation is not None
        digest = recipient_digest(address, invitation["id"], SIGNING_SECRET)
        queued = app_repo.queue_course_invite_mail_batch(
            course_id,
            invitation["id"],
            owner_sub,
            [{"email": address, "digest": digest}],
        )
        assert queued and queued["queued"] == 1

        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "update public.course_invite_mail_deliveries "
                "set next_attempt_at = '1900-01-01T00:00:00Z' where invitation_id = %s",
                (invitation["id"],),
            )

        worker_repo = PostgresCourseInviteMailRepository(WORKER_DSN)
        first_job = worker_repo.claim()
        assert first_job and first_job.invitation_id == invitation["id"]
        assert worker_repo.fail(
            first_job.delivery_id, first_job.lease_token, "smtp_4xx", True
        )

        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "select status, retryable, retry_count, next_attempt_at > now(), "
                "purge_after > now(), purge_after <= now() + interval '7 days 1 second' "
                "from public.course_invite_mail_deliveries "
                "where invitation_id = %s",
                (invitation["id"],),
            )
            assert cur.fetchone() == ("failed", True, 1, True, True, True)

        assert app_repo.retry_course_invite_mail_deliveries(
            course_id, invitation["id"], owner_sub
        ) == 1
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "update public.course_invite_mail_deliveries "
                "set next_attempt_at = '1900-01-01T00:00:00Z' where invitation_id = %s",
                (invitation["id"],),
            )

        second_job = worker_repo.claim()
        assert second_job and second_job.invitation_id == invitation["id"]
        assert worker_repo.fail(
            second_job.delivery_id, second_job.lease_token, "smtp_5xx", False
        )
        assert app_repo.retry_course_invite_mail_deliveries(
            course_id, invitation["id"], owner_sub
        ) == 0

        capped_address = f"retry-cap-{uuid4()}@school.example"
        capped_digest = recipient_digest(
            capped_address, invitation["id"], SIGNING_SECRET
        )
        capped = app_repo.queue_course_invite_mail_batch(
            course_id,
            invitation["id"],
            owner_sub,
            [{"email": capped_address, "digest": capped_digest}],
        )
        assert capped and capped["queued"] == 1
        for attempt in range(5):
            with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
                cur.execute(
                    "update public.course_invite_mail_deliveries "
                    "set next_attempt_at = '1900-01-01T00:00:00Z' "
                    "where invitation_id = %s and recipient_digest = %s",
                    (invitation["id"], capped_digest),
                )
            capped_job = worker_repo.claim()
            assert capped_job and capped_job.recipient_email == capped_address
            assert worker_repo.fail(
                capped_job.delivery_id, capped_job.lease_token, "smtp_4xx", True
            )

        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "select status, retryable, retry_count "
                "from public.course_invite_mail_deliveries "
                "where invitation_id = %s and recipient_digest = %s",
                (invitation["id"], capped_digest),
            )
            assert cur.fetchone() == ("failed", False, 5)
        assert app_repo.retry_course_invite_mail_deliveries(
            course_id, invitation["id"], owner_sub
        ) == 0

        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "update public.course_invite_mail_deliveries "
                "set purge_after = '1900-01-01T00:00:00Z' where invitation_id = %s",
                (invitation["id"],),
            )
        assert worker_repo.purge() >= 1
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "select status, retryable, recipient_email "
                "from public.course_invite_mail_deliveries where invitation_id = %s",
                (invitation["id"],),
            )
            rows = cur.fetchall()
            assert rows and all(row == ("failed", False, None) for row in rows)
    finally:
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute("delete from public.courses where id = %s", (course_id,))
