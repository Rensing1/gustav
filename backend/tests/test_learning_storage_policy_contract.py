"""
Learning storage policy — shared constants and helper contract (RED).

These tests ensure that the learning upload flow exposes its MIME/size/path
limits and storage verification helper from a dedicated shared module instead
of duplicating them inside the FastAPI router.
"""

import importlib
import re

import pytest


def _import(name: str):
    """Import helper that surfaces assertion-friendly errors."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:  # pragma: no cover - drives RED state
        raise AssertionError(f"Expected module {name!r} to exist for shared storage policy") from exc


def test_learning_upload_policy_exposes_shared_limits():
    policy = _import("backend.storage.learning_policy")
    assert getattr(policy, "ALLOWED_IMAGE_MIME")
    assert getattr(policy, "ALLOWED_FILE_MIME")
    assert getattr(policy, "MAX_UPLOAD_BYTES")
    assert getattr(policy, "STORAGE_KEY_RE")

    assert policy.ALLOWED_IMAGE_MIME == {"image/jpeg", "image/png"}
    assert policy.ALLOWED_FILE_MIME == {"application/pdf"}
    assert policy.MAX_UPLOAD_BYTES == 10 * 1024 * 1024
    assert re.fullmatch(policy.STORAGE_KEY_RE, "a/b/file.pdf")


def test_storage_verification_helper_available_for_learning():
    verification = _import("backend.storage.verification")
    helper = getattr(verification, "verify_storage_object_integrity", None)
    assert callable(helper), "Expected verify_storage_object_integrity helper to be callable"

