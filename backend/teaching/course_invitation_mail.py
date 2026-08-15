"""Teaching mail use case executed by the existing background worker.

Why:
    Course invitations reuse GUSTAV's configured SMTP relay without coupling
    Teaching business rules to the learning worker loop. Each claimed address
    is sent in its own message and is deleted by PostgreSQL immediately after a
    successful delivery acknowledgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
import logging
import os
import smtplib
import ssl
from typing import Protocol

from backend.teaching.course_invitations import build_invitation_token


LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class CourseInviteMailJob:
    """Privacy-sensitive snapshot leased to one worker process."""

    delivery_id: str
    lease_token: str
    recipient_email: str
    invitation_id: str
    token_nonce: str
    course_title: str
    expires_at: datetime


@dataclass(frozen=True)
class SmtpSettings:
    """SMTP settings shared with Keycloak through the existing KC_SMTP_* names."""

    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_starttls: bool
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "SmtpSettings":
        """Load the same relay configuration that sends verification mail."""

        return cls(
            host=os.getenv("KC_SMTP_HOST", "").strip(),
            port=int(os.getenv("KC_SMTP_PORT", "587")),
            username=os.getenv("KC_SMTP_USER", "").strip(),
            password=os.getenv("KC_SMTP_PASSWORD", ""),
            from_email=os.getenv("KC_SMTP_FROM", "").strip(),
            from_name=os.getenv("KC_SMTP_FROM_NAME", "GUSTAV-Lernplattform").strip(),
            use_starttls=os.getenv("KC_SMTP_STARTTLS", "true").strip().lower()
            in {"1", "true", "yes", "on"},
        )

    def validate(self) -> None:
        """Fail closed when a claimed mail cannot be delivered securely."""

        if (
            not self.host
            or not self.from_email
            or not (1 <= self.port <= 65535)
            or not self.use_starttls
        ):
            raise ValueError("smtp_configuration_invalid")


class CourseInviteMailRepository(Protocol):
    """Minimal database boundary used by one worker tick."""

    def purge(self) -> int: ...
    def claim(self) -> CourseInviteMailJob | None: ...
    def complete(self, delivery_id: str, lease_token: str) -> bool: ...
    def fail(
        self, delivery_id: str, lease_token: str, error_code: str, retryable: bool
    ) -> bool: ...


class PostgresCourseInviteMailRepository:
    """Least-privilege adapter around invitation-mail worker functions."""

    def __init__(self, dsn: str, *, psycopg_module=None) -> None:
        if psycopg_module is None:
            import psycopg as psycopg_module  # type: ignore

        self._dsn = dsn
        self._psycopg = psycopg_module

    def purge(self) -> int:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("select public.purge_course_invite_mail_recipients()")
                row = cur.fetchone()
        return int((row or [0])[0])

    def claim(self) -> CourseInviteMailJob | None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select delivery_id::text, lease_token::text, recipient_email,
                           invitation_id::text, token_nonce, course_title, expires_at
                      from public.claim_course_invite_mail_delivery()
                    """
                )
                row = cur.fetchone()
        if not row:
            return None
        return CourseInviteMailJob(
            delivery_id=row[0],
            lease_token=row[1],
            recipient_email=row[2],
            invitation_id=row[3],
            token_nonce=row[4],
            course_title=row[5],
            expires_at=row[6],
        )

    def complete(self, delivery_id: str, lease_token: str) -> bool:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select public.complete_course_invite_mail_delivery(%s, %s)",
                    (delivery_id, lease_token),
                )
                row = cur.fetchone()
        return bool(row and row[0])

    def fail(
        self, delivery_id: str, lease_token: str, error_code: str, retryable: bool
    ) -> bool:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select public.fail_course_invite_mail_delivery(%s, %s, %s, %s)",
                    (delivery_id, lease_token, error_code, retryable),
                )
                row = cur.fetchone()
        return bool(row and row[0])


def _safe_header(value: str) -> str:
    """Prevent user-managed text from introducing additional mail headers."""

    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def _expiry_text(expires_at: datetime) -> str:
    """Render a precise, timezone-aware expiry for the German mail copy."""

    return expires_at.astimezone().strftime("%d.%m.%Y um %H:%M Uhr %Z")


def build_course_invitation_message(
    *, job: CourseInviteMailJob, settings: SmtpSettings, invite_url: str
) -> EmailMessage:
    """Build one tracking-free multipart message for exactly one recipient.

    Permissions:
        The caller must hold a live lease returned by the worker-only database
        function. The address and capability must never be logged.
    """

    course_title = _safe_header(job.course_title)
    expiry = _expiry_text(job.expires_at)
    message = EmailMessage()
    message["Subject"] = f"Einladung zum GUSTAV-Kurs {course_title}"
    message["From"] = formataddr((_safe_header(settings.from_name), settings.from_email))
    message["To"] = job.recipient_email
    message.set_content(
        f"Hallo,\n\n"
        f"du wurdest zum GUSTAV-Kurs „{course_title}“ eingeladen. "
        f"Die Einladung ist bis {expiry} gültig.\n\n"
        "Wenn du GUSTAV noch nicht nutzt, kannst du dich über denselben Link "
        "registrieren und anschließend deine E-Mail-Adresse bestätigen. "
        "Wenn du bereits ein Konto hast, melde dich dort an.\n\n"
        f"{invite_url}\n\n"
        "Diese Nachricht enthält kein Tracking.\n"
    )
    message.add_alternative(
        "<p>Hallo,</p>"
        f"<p>du wurdest zum GUSTAV-Kurs <strong>„{escape(course_title)}“</strong> "
        f"eingeladen. Die Einladung ist bis {escape(expiry)} gültig.</p>"
        "<p>Wenn du GUSTAV noch nicht nutzt, kannst du dich über denselben Link "
        "registrieren und anschließend deine E-Mail-Adresse bestätigen. Wenn du "
        "bereits ein Konto hast, melde dich dort an.</p>"
        f'<p><a href="{escape(invite_url, quote=True)}">Kurseinladung öffnen</a></p>'
        "<p>Diese Nachricht enthält kein Tracking.</p>",
        subtype="html",
    )
    return message


def _failure_classification(exc: Exception) -> tuple[str, bool]:
    """Map SMTP exceptions to stable, address-free retry decisions."""

    if isinstance(exc, smtplib.SMTPResponseException):
        code = int(exc.smtp_code)
        return ("smtp_4xx", True) if 400 <= code < 500 else ("smtp_5xx", False)
    if isinstance(
        exc,
        (TimeoutError, ConnectionError, OSError, smtplib.SMTPServerDisconnected),
    ):
        return "smtp_network", True
    if isinstance(exc, ValueError):
        return "smtp_configuration", False
    return "smtp_failed", False


def process_course_invitation_mail_once(
    *,
    dsn: str | None = None,
    repository: CourseInviteMailRepository | None = None,
    settings: SmtpSettings | None = None,
    signing_secret: str | None = None,
    web_base: str | None = None,
    smtp_factory=smtplib.SMTP,
) -> bool:
    """Claim and deliver at most one invitation using verified SMTP transport.

    Behavior:
        Cleanup runs even on an idle tick. A successful delivery is acknowledged
        immediately so PostgreSQL clears the address. Failures store only a
        stable error code and retry flag; exception text is never logged.

    Permissions:
        `dsn` must authenticate as the dedicated `gustav_worker` role.
    """

    active_repository = repository
    if active_repository is None:
        if not dsn:
            raise ValueError("worker_dsn_required")
        active_repository = PostgresCourseInviteMailRepository(dsn)

    try:
        active_repository.purge()
    except Exception as exc:
        LOG.error(
            "course_invite_mail.repository_failed stage=purge error=%s",
            type(exc).__name__,
        )
        return False

    try:
        active_settings = settings or SmtpSettings.from_env()
        active_settings.validate()
    except Exception as exc:
        LOG.error(
            "course_invite_mail.configuration_invalid error=%s",
            type(exc).__name__,
        )
        return False

    try:
        job = active_repository.claim()
    except Exception as exc:
        LOG.error(
            "course_invite_mail.repository_failed stage=claim error=%s",
            type(exc).__name__,
        )
        return False
    if job is None:
        return False

    try:
        token = build_invitation_token(
            job.invitation_id,
            job.token_nonce,
            signing_secret or os.getenv("COURSE_INVITE_SIGNING_SECRET", ""),
        )
        invite_url = f"{(web_base or os.getenv('WEB_BASE', '')).rstrip('/')}/invite#{token}"
        if not invite_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("invite_web_base_invalid")
        message = build_course_invitation_message(
            job=job, settings=active_settings, invite_url=invite_url
        )
        with smtp_factory(
            active_settings.host,
            active_settings.port,
            timeout=active_settings.timeout_seconds,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            if active_settings.username:
                smtp.login(active_settings.username, active_settings.password)
            smtp.send_message(message)
    except Exception as exc:
        error_code, retryable = _failure_classification(exc)
        try:
            active_repository.fail(
                job.delivery_id, job.lease_token, error_code, retryable
            )
        except Exception as repository_exc:
            LOG.error(
                "course_invite_mail.repository_failed stage=fail error=%s",
                type(repository_exc).__name__,
            )
        LOG.warning(
            "course_invite_mail.failed delivery_id=%s code=%s retryable=%s",
            job.delivery_id,
            error_code,
            retryable,
        )
        return True

    try:
        completed = active_repository.complete(job.delivery_id, job.lease_token)
    except Exception as exc:
        LOG.error(
            "course_invite_mail.repository_failed stage=complete error=%s",
            type(exc).__name__,
        )
        return True
    if not completed:
        LOG.warning("course_invite_mail.ack_conflict delivery_id=%s", job.delivery_id)
        return True
    LOG.info("course_invite_mail.sent delivery_id=%s", job.delivery_id)
    return True
