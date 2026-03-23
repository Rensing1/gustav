"""Architecture documentation contract for the SvelteKit refactor."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_architecture_docs_adopt_sveltekit_and_diagnostics() -> None:
    architecture_path = REPO_ROOT / "docs" / "ARCHITECTURE.md"
    bounded_contexts_path = REPO_ROOT / "docs" / "bounded_contexts.md"
    readme_path = REPO_ROOT / "README.md"

    architecture = architecture_path.read_text(encoding="utf-8")
    bounded_contexts = bounded_contexts_path.read_text(encoding="utf-8")
    readme = readme_path.read_text(encoding="utf-8")

    assert "SvelteKit" in architecture
    assert "`diagnostics`" in architecture
    assert "`analytics`" not in bounded_contexts
    assert "`diagnostics`" in bounded_contexts
    assert "SvelteKit" in readme
