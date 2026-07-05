"""Submission file helpers for Teaching routes.

Why:
    The Teaching route module owns the HTTP endpoint, but download filename
    sanitizing, URL construction, and bounded byte fetching are reusable helper
    concerns. Keeping them here makes the route hotspot smaller without changing
    the public response contract.
"""

from __future__ import annotations

import httpx


def safe_download_filename(filename: str | None, fallback: str) -> str:
    """Return a safe quoted-header filename for a downloaded submission file."""

    raw = str(filename or "").strip()
    candidate = raw or fallback
    cleaned = "".join(ch for ch in candidate if ch not in {'"', "\r", "\n"})
    return cleaned or fallback


async def download_bytes_with_limit(
    *,
    url: str,
    max_bytes: int,
    headers: dict[str, str] | None = None,
) -> bytes | None:
    """Fetch a private file download into memory with a hard size limit."""

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                code = int(getattr(resp, "status_code", 500))
                if 300 <= code < 400 or code >= 400:
                    return None
                out = bytearray()
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    out.extend(chunk)
                    if len(out) > int(max_bytes):
                        return None
                return bytes(out)
    except Exception:
        return None


def teaching_submission_file_href(
    *,
    course_id: str,
    unit_id: str,
    task_id: str,
    student_sub: str,
    disposition: str,
) -> str:
    """Build the owner-facing Teaching submission file endpoint URL."""

    return (
        f"/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest/file"
        f"?disposition={disposition}"
    )
