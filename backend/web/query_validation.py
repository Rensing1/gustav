"""Strict query validation shared by private read-model routes.

Why:
    FastAPI normally converts annotated integers before a route runs. These
    private APIs need every malformed pagination value to use GUSTAV's stable
    `400 invalid_pagination` response instead of a framework-generated `422`.
"""

from __future__ import annotations


def parse_bounded_pagination(
    limit_raw: object,
    offset_raw: object,
    *,
    default_limit: int,
    maximum_limit: int,
) -> tuple[int, int] | None:
    """Return validated limit/offset values or `None` for any invalid input."""

    try:
        limit = int(limit_raw if limit_raw is not None else default_limit)
        offset = int(offset_raw if offset_raw is not None else 0)
    except (TypeError, ValueError):
        return None
    if limit < 1 or limit > maximum_limit or offset < 0:
        return None
    return limit, offset
