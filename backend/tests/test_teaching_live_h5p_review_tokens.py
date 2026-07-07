from __future__ import annotations

import base64
import hashlib
import hmac
import json

from backend.web.routes.teaching_live_h5p_review import issue_h5p_review_token


def _decode_token(token: str) -> tuple[dict, bytes, bytes]:
    payload_b64, sig_b64 = token.split(".")
    payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))
    sig_bytes = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
    return json.loads(payload_bytes.decode("utf-8")), payload_bytes, sig_bytes


def test_issue_h5p_review_token_returns_none_without_secret(monkeypatch):
    monkeypatch.delenv("H5P_REVIEW_TOKEN_SECRET", raising=False)

    assert (
        issue_h5p_review_token(
            owner_sub="teacher-1",
            course_id="course-1",
            task_id="task-1",
            student_sub="student-1",
            content_id="1",
            now_seconds=1000,
        )
        is None
    )


def test_issue_h5p_review_token_binds_teacher_student_course_task_content_and_expiry():
    token = issue_h5p_review_token(
        owner_sub="teacher-1",
        course_id="course-1",
        task_id="task-1",
        student_sub="student-1",
        content_id="1",
        secret="review-secret",
        now_seconds=1000,
    )

    assert isinstance(token, str)
    payload, payload_bytes, sig_bytes = _decode_token(token)
    assert payload == {
        "teacher_sub": "teacher-1",
        "student_sub": "student-1",
        "course_id": "course-1",
        "task_id": "task-1",
        "content_id": "1",
        "exp": 1600,
    }
    expected_sig = hmac.new(b"review-secret", payload_bytes, hashlib.sha256).digest()
    assert hmac.compare_digest(sig_bytes, expected_sig)
