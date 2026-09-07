"""Shared include-query parsing for section and module resource selection."""


def parse_include(
    value: str | None, *, default_materials: bool = False, default_tasks: bool = False
) -> tuple[bool, bool]:
    """Keep established defaults, whitespace/duplicate handling and strict empty-token errors."""
    if value is None:
        return default_materials, default_tasks
    raw = value.strip()
    if not raw:
        raise ValueError("invalid_include")
    tokens = [token.strip() for token in raw.split(",")]
    if any(not token or token not in {"materials", "tasks"} for token in tokens):
        raise ValueError("invalid_include")
    return "materials" in tokens, "tasks" in tokens
