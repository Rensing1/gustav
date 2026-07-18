"""H5P review-token helpers for Teaching live detail read models."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_REVIEW_CREDENTIAL_AAD = b"gustav-h5p-review-v1"


def _base64url(value: bytes) -> str:
    """Encode binary credential parts without URL-unsafe padding."""

    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def issue_h5p_review_token(
    *,
    owner_sub: str,
    task_id: str,
    student_sub: str,
    content_id: str,
    secret: str | None = None,
    now_seconds: int | None = None,
) -> str | None:
    """Return a short-lived encrypted H5P review credential.

    The caller must already have verified course ownership. AES-GCM hides the
    stable teacher and student subjects while authenticating the minimal claims
    needed by the H5P sidecar: teacher, student, task, content and expiry.
    """

    review_secret = (secret if secret is not None else os.getenv("H5P_REVIEW_TOKEN_SECRET") or "").strip()
    if not review_secret:
        return None

    try:
        now = int(time.time() if now_seconds is None else now_seconds)
        payload_obj = {
            "teacher_sub": owner_sub,
            "student_sub": student_sub,
            "task_id": task_id,
            "content_id": content_id,
            "exp": now + 10 * 60,
        }
        raw_json = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        nonce = os.urandom(12)
        key = hashlib.sha256(review_secret.encode("utf-8")).digest()
        ciphertext = AESGCM(key).encrypt(nonce, raw_json, _REVIEW_CREDENTIAL_AAD)
        return f"v1.{_base64url(nonce)}.{_base64url(ciphertext)}"
    except Exception:
        return None
