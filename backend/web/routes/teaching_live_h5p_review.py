"""H5P review-token helpers for Teaching live detail routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


def issue_h5p_review_token(
    *,
    owner_sub: str,
    course_id: str,
    task_id: str,
    student_sub: str,
    content_id: str,
    secret: str | None = None,
    now_seconds: int | None = None,
) -> str | None:
    """Return a short-lived, signed H5P review capability token.

    Caller must already have verified course ownership. The token binds the
    teacher, student, course, task and H5P content id, so the H5P sidecar can
    fail closed without accepting a generic impersonation parameter.
    """

    review_secret = (secret if secret is not None else os.getenv("H5P_REVIEW_TOKEN_SECRET") or "").strip()
    if not review_secret:
        return None

    try:
        now = int(time.time() if now_seconds is None else now_seconds)
        payload_obj = {
            "teacher_sub": owner_sub,
            "student_sub": student_sub,
            "course_id": course_id,
            "task_id": task_id,
            "content_id": content_id,
            "exp": now + 10 * 60,
        }
        raw_json = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
        sig = hmac.new(review_secret.encode("utf-8"), raw_json, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
        return f"{payload_b64}.{sig_b64}"
    except Exception:
        return None
