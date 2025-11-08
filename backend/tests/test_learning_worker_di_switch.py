"""
Integration tests for DI switching of adapters in the worker entrypoint.

Intent:
    Verify that environment-based selection picks the correct adapter modules.
    - Default → stub adapters.
    - AI_BACKEND=local → local adapters (alias for convenience).

We patch `import_module` and `run_forever` to avoid network and infinite loops.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from backend.learning.workers import process_learning_submission_jobs as worker


@pytest.mark.parametrize(
    "env,expected",
    [
        ({}, ("backend.learning.adapters.stub_vision", "backend.learning.adapters.stub_feedback")),
        (
            {"AI_BACKEND": "local"},
            ("backend.learning.adapters.local_vision", "backend.learning.adapters.local_feedback"),
        ),
    ],
)
def test_worker_main_selects_adapters_via_env(monkeypatch: pytest.MonkeyPatch, env: dict, expected: tuple[str, str]) -> None:
    # Ensure a clean env and apply test overrides.
    for key in [
        "LEARNING_VISION_ADAPTER",
        "LEARNING_FEEDBACK_ADAPTER",
        "AI_BACKEND",
    ]:
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    seen = {"paths": []}

    def _fake_import_module(path: str):  # type: ignore[override]
        seen["paths"].append(path)
        # Return a module-like object with build() that creates a simple adapter.
        if path.endswith("vision"):
            return SimpleNamespace(build=lambda: SimpleNamespace(extract=lambda **kwargs: None))  # type: ignore
        return SimpleNamespace(build=lambda: SimpleNamespace(analyze=lambda **kwargs: None))  # type: ignore

    monkeypatch.setattr(worker, "import_module", _fake_import_module)
    monkeypatch.setattr(worker, "run_forever", lambda **_: None)

    # main() should import the chosen modules and return without looping forever.
    worker.main()

    assert tuple(seen["paths"]) == expected

