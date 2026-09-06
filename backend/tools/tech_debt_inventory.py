"""Validate the debt register without prescribing how much debt may exist."""

from __future__ import annotations

import re
from datetime import date

FIELDS = ("ID", "Bereich", "Risiko", "Grund", "Owner", "Review date", "Exit criterion", "Status", "Nachweis")


def parse_entries(document: str) -> list[dict[str, str]]:
    """Read complete debt records, retaining overdue and completed entries.

    Input is public Markdown, never operational or personal data. Malformed
    records raise ValueError rather than disappearing from the scorecard.
    Completed records need evidence; overdue records remain visible so their
    review can be scheduled without preventing unrelated repairs.
    """
    entries: list[dict[str, str]] = []
    headers: list[str] = []
    seen: set[str] = set()
    for line_number, line in enumerate(document.splitlines(), 1):
        line = line.strip()
        if not line.startswith("|"):
            headers = []
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[0] == "ID":
            headers = cells
            if tuple(headers) != FIELDS:
                raise ValueError(f"line {line_number}: invalid debt table header")
            continue
        if not headers and cells[0].startswith("TD-"):
            raise ValueError(f"line {line_number}: missing debt table header")
        if not headers or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if len(cells) != len(headers):
            raise ValueError(f"line {line_number}: invalid debt table shape")
        row = dict(zip(headers, cells))
        for field in FIELDS[:-1]:
            if not row[field]:
                raise ValueError(f"line {line_number}: missing {field}")
        identifier = row["ID"]
        if not re.fullmatch(r"TD-\d{3,}", identifier):
            raise ValueError(f"line {line_number}: invalid ID")
        if identifier in seen:
            raise ValueError(f"line {line_number}: duplicate ID {identifier}")
        seen.add(identifier)
        review_date = row["Review date"]
        try:
            if date.fromisoformat(review_date).isoformat() != review_date:
                raise ValueError()
        except ValueError as error:
            raise ValueError(f"{identifier}: invalid Review date") from error
        if row["Status"] not in {"offen", "blockiert", "erledigt"}:
            raise ValueError(f"{identifier}: invalid Status")
        if row["Status"] == "erledigt" and not row["Nachweis"]:
            raise ValueError(f"{identifier}: missing Nachweis")
        entries.append(row)
    return entries
