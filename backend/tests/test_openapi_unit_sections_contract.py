"""
Contract test: OpenAPI must declare full error responses for unit sections.

Why:
- Prevents regressions in the YAML where responses are misplaced or missing.
- Keeps API Contract-First discipline verifiable without extra deps.

Checks:
- Under path /api/learning/courses/{course_id}/units/{unit_id}/sections (GET),
  responses include 200, 400, 401, 403, 404.
"""
from __future__ import annotations

import pathlib


def _extract_section(lines: list[str], start_marker: str) -> list[str] | None:
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip("\n").endswith(start_marker))
    except StopIteration:
        return None
    # Collect until next top-level path (starts with two spaces then a slash)
    collected: list[str] = []
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.startswith("  /") and not line.startswith("   "):
            break
        collected.append(line)
    return collected


def test_openapi_unit_sections_has_error_responses():
    yml = pathlib.Path("api/openapi.yml").read_text(encoding="utf-8").splitlines()
    section = _extract_section(yml, "/api/learning/courses/{course_id}/units/{unit_id}/sections:")
    assert section is not None, "Unit sections path not found in openapi.yml"
    # Find GET block within section
    try:
        get_index = next(i for i, line in enumerate(section) if line.strip() == "get:")
    except StopIteration:
        raise AssertionError("GET operation not found for unit sections path")
    # From get_index forward, responses should include these status codes
    tail = section[get_index:]
    text = "\n".join(tail)
    for code in ("'200':", "'400':", "'401':", "'403':", "'404':"):
        assert code in text, f"Missing response {code} for unit sections"

