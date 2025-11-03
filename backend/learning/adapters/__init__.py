"""Adapter factory helpers for the learning worker.

Intent:
    Keep runtime adapters discoverable via dotted paths so the worker can load
    them dynamically (mirrors the default environment variables in docker-compose).

Exports:
    The individual modules expose a `build()` function returning an object that
    implements the respective protocol used by the worker.
"""

__all__ = ["stub_feedback", "stub_vision"]
