"""
Smoke-test to ensure DSPy is installed in the runtime environment.

Why: The feedback adapter silently falls back to stub responses if importing
`dspy` fails. This import check runs early in CI to surface missing dependency
installs long before the worker code tries to load DSPy at runtime.
"""

from importlib import import_module


def test_dspy_is_importable() -> None:
    """Fail fast when DSPy is missing from the environment."""
    mod = import_module("dspy")
    assert getattr(mod, "__version__", None), "dspy missing __version__"
