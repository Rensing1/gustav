"""Unit tests for privacy-preserving invitation delivery."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import logging
import smtplib

import pytest

from backend.learning.workers import process_learning_submission_jobs as learning_worker
from backend.teaching.course_invitation_mail import (
    CourseInviteMailJob,
    SmtpSettings,
    build_course_invitation_message,
    process_course_invitation_mail_once,
)


class FakeRepository:
    def __init__(self, job: CourseInviteMailJob | None):
        self.job = job
        self.completed: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str, str, bool]] = []
        self.purged = 0

    def purge(self) -> int:
        self.purged += 1
        return 0

    def claim(self) -> CourseInviteMailJob | None:
        job, self.job = self.job, None
        return job

    def complete(self, delivery_id: str, lease_token: str) -> bool:
        self.completed.append((delivery_id, lease_token))
        return True

    def fail(self, delivery_id: str, lease_token: str, error_code: str, retryable: bool) -> bool:
        self.failed.append((delivery_id, lease_token, error_code, retryable))
        return True


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, host: str, port: int, timeout: float):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in = False
        self.messages = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def ehlo(self):
        return None

    def starttls(self, *, context):
        assert context.check_hostname is True
        assert context.verify_mode != 0
        self.started_tls = True

    def login(self, username: str, password: str):
        assert username == "smtp-user"
        assert password == "smtp-password"
        self.logged_in = True

    def send_message(self, message):
        self.messages.append(message)


def _job() -> CourseInviteMailJob:
    return CourseInviteMailJob(
        delivery_id="00000000-0000-0000-0000-000000000001",
        lease_token="00000000-0000-0000-0000-000000000002",
        recipient_email="student@school.example",
        invitation_id="00000000-0000-0000-0000-000000000003",
        token_nonce="nonce-with-at-least-twenty-characters",
        course_title="Informatik 9a",
        expires_at=datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
    )


def _settings() -> SmtpSettings:
    return SmtpSettings(
        host="smtp.school.example",
        port=587,
        username="smtp-user",
        password="smtp-password",
        from_email="noreply@school.example",
        from_name="GUSTAV-Lernplattform",
        use_starttls=True,
        timeout_seconds=15.0,
    )


def test_message_has_one_recipient_and_plain_and_html_parts() -> None:
    message = build_course_invitation_message(
        job=_job(),
        settings=_settings(),
        invite_url="https://app.localhost/invite#signed-capability",
    )
    assert message["To"] == "student@school.example"
    assert message["Bcc"] is None
    assert message["Subject"] == "Einladung zum GUSTAV-Kurs Informatik 9a"
    assert message.is_multipart()
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "https://app.localhost/invite#signed-capability" in body
    assert "16.08.2026" in body


def test_success_uses_verified_starttls_and_completes_delivery() -> None:
    FakeSmtp.instances.clear()
    repository = FakeRepository(_job())
    processed = process_course_invitation_mail_once(
        repository=repository,
        settings=_settings(),
        signing_secret="test-course-invite-secret-with-32-bytes",
        web_base="https://app.localhost",
        smtp_factory=FakeSmtp,
    )
    assert processed is True
    assert repository.completed == [
        ("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002")
    ]
    assert repository.failed == []
    smtp = FakeSmtp.instances[0]
    assert smtp.started_tls is True
    assert smtp.logged_in is True
    assert len(smtp.messages) == 1


def test_disabled_starttls_fails_closed_before_claiming_or_sending() -> None:
    FakeSmtp.instances.clear()
    job = _job()
    repository = FakeRepository(job)

    processed = process_course_invitation_mail_once(
        repository=repository,
        settings=replace(_settings(), use_starttls=False),
        signing_secret="test-course-invite-secret-with-32-bytes",
        web_base="https://app.localhost",
        smtp_factory=FakeSmtp,
    )

    assert processed is False
    assert repository.job is job
    assert repository.completed == []
    assert repository.failed == []
    assert FakeSmtp.instances == []


def test_invalid_smtp_port_is_isolated_before_claim(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    job = _job()
    repository = FakeRepository(job)
    monkeypatch.setenv("KC_SMTP_PORT", "not-a-port")
    caplog.set_level(logging.INFO)

    assert process_course_invitation_mail_once(
        repository=repository,
        settings=None,
        signing_secret="test-course-invite-secret-with-32-bytes",
        web_base="https://app.localhost",
        smtp_factory=FakeSmtp,
    ) is False
    assert repository.job is job
    assert "configuration_invalid" in caplog.text


@pytest.mark.parametrize(
    ("exc", "expected_code", "retryable"),
    [
        (smtplib.SMTPResponseException(451, b"temporary"), "smtp_4xx", True),
        (smtplib.SMTPResponseException(550, b"rejected"), "smtp_5xx", False),
        (TimeoutError("timeout for student@school.example"), "smtp_network", True),
    ],
)
def test_failures_are_classified_without_logging_recipient(
    exc: Exception,
    expected_code: str,
    retryable: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingSmtp(FakeSmtp):
        def send_message(self, message):
            raise exc

    repository = FakeRepository(_job())
    caplog.set_level(logging.INFO)
    processed = process_course_invitation_mail_once(
        repository=repository,
        settings=_settings(),
        signing_secret="test-course-invite-secret-with-32-bytes",
        web_base="https://app.localhost",
        smtp_factory=FailingSmtp,
    )
    assert processed is True
    assert repository.failed[0][2:] == (expected_code, retryable)
    assert "student@school.example" not in caplog.text
    assert "signed-capability" not in caplog.text


def test_idle_tick_still_runs_privacy_cleanup() -> None:
    repository = FakeRepository(None)
    assert process_course_invitation_mail_once(
        repository=repository,
        settings=_settings(),
        signing_secret="test-course-invite-secret-with-32-bytes",
        web_base="https://app.localhost",
        smtp_factory=FakeSmtp,
    ) is False
    assert repository.purged == 1


@pytest.mark.parametrize("stage", ["purge", "claim"])
def test_repository_failures_are_isolated_from_the_shared_worker(
    stage: str, caplog: pytest.LogCaptureFixture
) -> None:
    class FailingRepository(FakeRepository):
        def purge(self) -> int:
            if stage == "purge":
                raise RuntimeError("contains student@school.example")
            return super().purge()

        def claim(self) -> CourseInviteMailJob | None:
            if stage == "claim":
                raise RuntimeError("contains student@school.example")
            return super().claim()

    caplog.set_level(logging.INFO)
    assert process_course_invitation_mail_once(
        repository=FailingRepository(_job()),
        settings=_settings(),
        signing_secret="test-course-invite-secret-with-32-bytes",
        web_base="https://app.localhost",
        smtp_factory=FakeSmtp,
    ) is False
    assert "student@school.example" not in caplog.text
    assert f"stage={stage}" in caplog.text


def test_failure_acknowledgement_error_does_not_escape_or_log_pii(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingSmtp(FakeSmtp):
        def send_message(self, message):
            raise TimeoutError("student@school.example")

    class FailingRepository(FakeRepository):
        def fail(
            self,
            delivery_id: str,
            lease_token: str,
            error_code: str,
            retryable: bool,
        ) -> bool:
            raise RuntimeError("student@school.example")

    caplog.set_level(logging.INFO)
    assert process_course_invitation_mail_once(
        repository=FailingRepository(_job()),
        settings=_settings(),
        signing_secret="test-course-invite-secret-with-32-bytes",
        web_base="https://app.localhost",
        smtp_factory=FailingSmtp,
    ) is True
    assert "student@school.example" not in caplog.text
    assert "stage=fail" in caplog.text


def test_existing_worker_loop_polls_teaching_mail_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(learning_worker, "run_once", lambda **_kwargs: False)

    def process_mail(*, dsn: str) -> bool:
        calls.append(dsn)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return True

    with pytest.raises(KeyboardInterrupt):
        learning_worker.run_forever(
            dsn="postgresql://worker",
            vision_adapter=object(),
            feedback_adapter=object(),
            course_invite_mail_processor=process_mail,
            mail_poll_interval=0,
        )
    assert calls == ["postgresql://worker", "postgresql://worker"]


def test_shared_worker_continues_after_teaching_mail_processor_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(learning_worker, "run_once", lambda **_kwargs: False)

    def process_mail(*, dsn: str) -> bool:
        calls.append(dsn)
        if len(calls) == 1:
            raise RuntimeError("student@school.example")
        raise KeyboardInterrupt

    caplog.set_level(logging.INFO)
    with pytest.raises(KeyboardInterrupt):
        learning_worker.run_forever(
            dsn="postgresql://worker",
            vision_adapter=object(),
            feedback_adapter=object(),
            course_invite_mail_processor=process_mail,
            mail_poll_interval=0,
            poll_interval=0,
        )
    assert calls == ["postgresql://worker", "postgresql://worker"]
    assert "student@school.example" not in caplog.text
