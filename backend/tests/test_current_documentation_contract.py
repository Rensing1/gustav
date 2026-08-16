"""Contracts that keep GUSTAV's current documentation aligned with 0.0.4."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_project_status_describes_the_completed_frontend_cutover() -> None:
    readme = _read("README.md")

    assert "The former server-rendered product interface has been retired" in readme
    assert "architecture is still being moved" not in readme
    assert "parts of the older web layer remain" not in readme


def test_architecture_document_describes_the_current_runtime() -> None:
    architecture = _read("docs/ARCHITECTURE.md")

    for current_marker in (
        "Version 0.0.4",
        "SvelteKit-Browser-BFF",
        "FastAPI-API-Adapter",
        "architecture-boundary-scan",
        "keine aktiven Legacy-Produktseiten",
    ):
        assert current_marker in architecture

    for stale_marker in (
        "Domain (geplant)",
        "Application / Use Cases (geplant)",
        "Legacy-Webbestand",
        "Migrationspfad zu einer getrennten SPA",
    ):
        assert stale_marker not in architecture


def test_context_and_reference_docs_no_longer_describe_retired_ui() -> None:
    bounded_contexts = _read("docs/bounded_contexts.md")
    teaching = _read("docs/references/teaching.md")
    learning = _read("docs/references/learning.md")
    user_management = _read("docs/references/user_management.md")

    assert "Version 0.0.4" in bounded_contexts
    assert "alpha‑2" not in bounded_contexts
    assert "Kurseinladungen (Course Invitations)" in teaching
    assert "SSR‑UI" not in teaching
    assert "hx-post" not in teaching
    assert "SvelteKit-Lernarbeitsbereich" in learning
    assert "Analyse‑Stub" not in learning
    assert "Persistente Sessions aktivieren" not in user_management
    assert "HTMX:" not in user_management


def test_glossary_and_schema_notes_cover_course_invitations() -> None:
    glossary = _read("docs/glossary.md")
    schema = _read("docs/database_schema.md")

    assert "Kurseinladung" in glossary
    assert "Capability-Token" in glossary
    assert "ausgewählte sicherheitskritische Strukturen" in schema
    assert "course_invitations" in schema
    assert "learning_practice_sessions" in schema


def test_changelog_has_a_004_release_section() -> None:
    changelog = _read("docs/CHANGELOG.md")

    assert "## 0.0.4 — 2026-08-16" in changelog
