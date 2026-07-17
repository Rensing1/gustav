"""Supply-chain contracts for dependencies executed by the harness itself."""

from __future__ import annotations

from pathlib import Path

from backend.tools import supply_chain_check


ROOT = Path(__file__).resolve().parents[2]


def test_inventory_includes_recursive_harness_requirements() -> None:
    inventory = supply_chain_check.build_inventory()

    assert "backend/web/requirements.txt" in inventory["sources"]
    assert "backend/requirements-harness.txt" in inventory["sources"]
    ruff = [entry for entry in inventory["entries"] if entry["ecosystem"] == "python" and entry["name"] == "ruff"]
    assert len(ruff) == 1
    assert ruff[0]["version"] == "0.15.20"


def test_ruff_is_exactly_pinned_for_reproducible_ci() -> None:
    requirements = (ROOT / "backend/requirements-harness.txt").read_text(encoding="utf-8")

    assert "ruff==0.15.20" in requirements
    assert "ruff>=" not in requirements
