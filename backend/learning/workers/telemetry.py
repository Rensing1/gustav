"""
In-memory telemetry helpers for the learning worker.

Intent:
    Keep instrumentation simple (KISS) while providing introspection hooks for
    unit tests and local debugging. Production deployments scrape these values
    via the Prometheus exporter in the web layer; this module merely tracks the
    counters and gauges until they are exposed.
"""
from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple

LabelKey = Tuple[Tuple[str, str], ...]
_counters: Dict[str, Dict[LabelKey, int]] = defaultdict(dict)
_gauges: Dict[str, Dict[LabelKey, float]] = defaultdict(dict)
_lock = Lock()


def _label_key(labels: dict[str, str] | None) -> LabelKey:
    if not labels:
        return tuple()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def increment_counter(name: str, *, amount: int = 1, **labels: str) -> None:
    """Increase a named counter by `amount` (defaults to 1)."""
    if amount == 0:
        return
    key = _label_key(labels)
    with _lock:
        current = _counters[name].get(key, 0)
        _counters[name][key] = current + amount


def set_gauge(name: str, value: float, **labels: str) -> None:
    """Set an absolute value for a gauge."""
    key = _label_key(labels)
    with _lock:
        _gauges[name][key] = float(value)


def adjust_gauge(name: str, delta: float, **labels: str) -> None:
    """Adjust a gauge by `delta`, clamping the stored value to zero or above."""
    key = _label_key(labels)
    with _lock:
        current = _gauges[name].get(key, 0.0)
        new_value = current + float(delta)
        if new_value <= 0.0:
            _gauges[name][key] = 0.0
        else:
            _gauges[name][key] = new_value


def counter_snapshot(name: str) -> dict[LabelKey, int]:
    """Return a shallow copy of the stored counter values."""
    with _lock:
        return dict(_counters.get(name, {}))


def gauge_snapshot(name: str) -> dict[LabelKey, float]:
    """Return a shallow copy of the stored gauge values."""
    with _lock:
        return dict(_gauges.get(name, {}))


def reset_for_tests() -> None:
    """Clear all counters and gauges. Intended for pytest fixtures."""
    with _lock:
        _counters.clear()
        _gauges.clear()
