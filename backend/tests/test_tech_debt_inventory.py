"""Keep accepted debt visible without weakening the quality of its records."""

from datetime import date

import pytest

from backend.tools.tech_debt_inventory import parse_entries

HEADER = "| ID | Bereich | Risiko | Grund | Owner | Review date | Exit criterion | Status | Nachweis |\n"
ROW = ["TD-001", "Architektur", "Wartbarkeit", "Globale Provider", "Produktverantwortlicher", "2026-10-01", "Isolierte Apps", "offen", ""]


def document(row=None):
    return HEADER + "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n" + "| " + " | ".join(ROW if row is None else row) + " |\n"


def test_complete_open_entry_is_accepted():
    entries = parse_entries(document())
    assert entries[0]["ID"] == "TD-001"
    assert entries[0]["Status"] == "offen"


@pytest.mark.parametrize("column", range(8))
def test_missing_required_value_is_rejected(column):
    row = ROW.copy()
    row[column] = ""
    with pytest.raises(ValueError):
        parse_entries(document(row))


@pytest.mark.parametrize("review_date", ["morgen", "2026-02-30", "20261001"])
def test_invalid_review_date_is_rejected(review_date):
    row = ROW.copy()
    row[5] = review_date
    with pytest.raises(ValueError, match="Review date"):
        parse_entries(document(row))


def test_overdue_entry_stays_visible():
    row = ROW.copy()
    row[5] = date(2020, 1, 1).isoformat()
    assert parse_entries(document(row))[0]["ID"] == "TD-001"


def test_duplicate_id_is_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        parse_entries(document() + document().splitlines()[-1])


def test_closed_entry_requires_evidence():
    row = ROW.copy()
    row[7] = "erledigt"
    with pytest.raises(ValueError, match="Nachweis"):
        parse_entries(document(row))
    row[8] = "Plan mit Testergebnis"
    assert parse_entries(document(row))[0]["Status"] == "erledigt"


def test_unknown_status_is_rejected():
    row = ROW.copy()
    row[7] = "almost done"
    with pytest.raises(ValueError, match="Status"):
        parse_entries(document(row))


def test_invalid_table_shape_is_not_silently_skipped():
    with pytest.raises(ValueError):
        parse_entries(document(ROW[:-2]))


def test_debt_row_without_header_is_not_silently_skipped():
    with pytest.raises(ValueError, match="header"):
        parse_entries(document().splitlines()[-1])


def test_scorecard_counts_open_and_blocked_but_not_completed(tmp_path, monkeypatch):
    from backend.tools import quality_scorecard

    closed = ROW.copy()
    closed[0], closed[7], closed[8] = "TD-002", "erledigt", "Geprüfter Abschluss"
    blocked = ROW.copy()
    blocked[0], blocked[7] = "TD-003", "blockiert"
    inventory = tmp_path / "debt.md"
    inventory.write_text(document() + document(closed).splitlines()[-1] + "\n" + document(blocked).splitlines()[-1])
    monkeypatch.setattr(quality_scorecard, "TECH_DEBT_PATH", inventory)
    assert [row["id"] for row in quality_scorecard._parse_tech_debt()] == ["TD-001", "TD-003"]
