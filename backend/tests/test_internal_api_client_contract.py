"""Contracts for SSR-internal API client helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.web.internal_api import (
    internal_api_client,
    learning_internal_base,
    resolve_internal_base,
    teaching_internal_base,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_resolve_internal_base_prefers_context_then_shared_then_loopback(monkeypatch) -> None:
    """SSR-internal hops must use one deterministic base and matching Origin."""

    monkeypatch.delenv("TEACHING_INTERNAL_BASE_URL", raising=False)
    monkeypatch.delenv("APP_INTERNAL_BASE_URL", raising=False)
    assert resolve_internal_base("TEACHING_INTERNAL_BASE_URL") == ("http://local", "http://local")

    monkeypatch.setenv("APP_INTERNAL_BASE_URL", "http://shared.local/")
    assert resolve_internal_base("TEACHING_INTERNAL_BASE_URL") == ("http://shared.local/", "http://shared.local")

    monkeypatch.setenv("TEACHING_INTERNAL_BASE_URL", "http://teaching.local/")
    assert resolve_internal_base("TEACHING_INTERNAL_BASE_URL") == ("http://teaching.local/", "http://teaching.local")


def test_learning_and_teaching_internal_base_use_their_context_env(monkeypatch) -> None:
    """Learning and teaching callers keep separate override knobs."""

    monkeypatch.setenv("LEARNING_INTERNAL_BASE_URL", "http://learning.local")
    monkeypatch.setenv("TEACHING_INTERNAL_BASE_URL", "http://teaching.local")

    assert learning_internal_base() == ("http://learning.local", "http://learning.local")
    assert teaching_internal_base() == ("http://teaching.local", "http://teaching.local")


@pytest.mark.anyio
async def test_internal_api_client_sets_base_url_and_origin(monkeypatch) -> None:
    """Strict CSRF accepts SSR-internal writes because Origin matches base URL."""

    app = FastAPI()
    monkeypatch.setenv("TEACHING_INTERNAL_BASE_URL", "http://teaching.local/")

    async with internal_api_client(app) as client:
        assert str(client.base_url) == "http://teaching.local/"
        assert client.headers["Origin"] == "http://teaching.local"


def test_main_no_longer_owns_or_imports_internal_api_client_helpers() -> None:
    """The app entry module should not own retired SSR-internal API client hops."""

    main_source = (REPO_ROOT / "backend/web/main.py").read_text(encoding="utf-8")

    for retired_helper in (
        "def _resolve_internal_base",
        "def _learning_internal_base",
        "def _teaching_internal_base",
        "def _internal_api_client",
    ):
        assert retired_helper not in main_source

    assert "from backend.web.internal_api import internal_api_client" not in main_source
    assert "internal_api_client(app)" not in main_source
