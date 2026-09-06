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


def test_inventory_does_not_treat_pip_directives_as_packages() -> None:
    inventory = supply_chain_check.build_inventory()
    python_names = {
        entry["name"] for entry in inventory["entries"] if entry["ecosystem"] == "python"
    }

    assert all(not name.startswith("-") for name in python_names)
    assert "-r" not in python_names


def test_ruff_is_exactly_pinned_for_reproducible_ci() -> None:
    requirements = (ROOT / "backend/requirements-harness.txt").read_text(encoding="utf-8")

    assert "ruff==0.15.20" in requirements
    assert "ruff>=" not in requirements


def test_python_inventory_uses_locked_versions_even_when_environment_differs(tmp_path, monkeypatch):
    backend = tmp_path / "backend"
    (backend / "web").mkdir(parents=True)
    (backend / "requirements-harness.lock").write_text("transitive-example==1.2.3 --hash=sha256:" + "a" * 64 + "\n")
    monkeypatch.setattr(supply_chain_check, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(supply_chain_check.metadata, "version", lambda name: "9.9.9")
    entries, _ = supply_chain_check._python_inventory()
    assert entries[0]["version"] == "1.2.3"


def test_inventory_sources_include_nested_requirement_manifests(tmp_path, monkeypatch):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "requirements-harness.lock").write_text("example==1.2.3\n")
    (backend / "requirements-harness.txt").write_text("-r nested.txt\n")
    nested = backend / "nested.txt"
    nested.write_text("example==1.2.3\n")
    monkeypatch.setattr(supply_chain_check, "REPO_ROOT", tmp_path)
    _, sources = supply_chain_check._python_inventory()
    assert nested in sources
    assert len(sources) == len(set(sources))


def test_runtime_installs_hash_verified_lock_and_preserves_ai_constraints():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "--require-hashes -r requirements.lock" in dockerfile
    assert "-c ../constraints-ai.txt" in (ROOT / "backend/web/requirements.txt").read_text()


def test_harness_lock_includes_installer_dependencies_for_fresh_environments():
    lock = (ROOT / "backend/requirements-harness.lock").read_text()
    assert "\npip==" in lock
    assert "\nsetuptools==" in lock
    assert "# WARNING:" not in lock
