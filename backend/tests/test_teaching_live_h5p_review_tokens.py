from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.teaching.live_h5p_review import issue_h5p_review_token


def _decode_part(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _decrypt_token(token: str, *, secret: str) -> dict:
    version, nonce_b64, ciphertext_b64 = token.split(".")
    assert version == "v1"
    plaintext = AESGCM(hashlib.sha256(secret.encode("utf-8")).digest()).decrypt(
        _decode_part(nonce_b64),
        _decode_part(ciphertext_b64),
        b"gustav-h5p-review-v1",
    )
    return json.loads(plaintext.decode("utf-8"))


def test_issue_h5p_review_token_returns_none_without_secret(monkeypatch):
    monkeypatch.delenv("H5P_REVIEW_TOKEN_SECRET", raising=False)

    assert (
        issue_h5p_review_token(
            owner_sub="teacher-1",
            task_id="task-1",
            student_sub="student-1",
            content_id="1",
            now_seconds=1000,
        )
        is None
    )


def test_issue_h5p_review_token_encrypts_minimal_bound_claims():
    token = issue_h5p_review_token(
        owner_sub="teacher-1",
        task_id="task-1",
        student_sub="student-1",
        content_id="1",
        secret="review-secret",
        now_seconds=1000,
    )

    assert isinstance(token, str)
    payload = _decrypt_token(token, secret="review-secret")
    assert payload == {
        "teacher_sub": "teacher-1",
        "student_sub": "student-1",
        "task_id": "task-1",
        "content_id": "1",
        "exp": 1600,
    }

    # Base64-decoding every public segment must not reveal stable subjects.
    encoded_parts = token.split(".")[1:]
    public_bytes = b"".join(_decode_part(part) for part in encoded_parts)
    assert b"teacher-1" not in public_bytes
    assert b"student-1" not in public_bytes
