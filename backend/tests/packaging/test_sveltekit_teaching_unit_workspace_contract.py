"""Packaging contract for the SvelteKit teacher unit workspace and node editor."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_teacher_unit_workspace_loader_uses_graph_workspace_view() -> None:
    loader = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "[unitId]" / "+page.server.ts"
    src = loader.read_text(encoding="utf-8")

    assert "/api/teaching/views/units/" in src
    assert "/workspace" in src
    assert "section_id" in src
    assert "module_id" in src
    assert "createEdge" in src
    assert "deleteEdge" in src


def test_teacher_unit_workspace_page_renders_graph_workspace() -> None:
    page = REPO_ROOT / "frontend" / "src" / "routes" / "teaching" / "units" / "[unitId]" / "+page.svelte"
    src = page.read_text(encoding="utf-8")

    assert "@xyflow/svelte" in src
    assert "SvelteFlow" in src
    assert "teacher-flow-page-tools" in src
    assert "teacher-flow-quickedit" in src
    assert "GraphUnitNode" in src
    assert "GraphPhaseBand" in src
    assert "editor_href" in src or "/nodes/" in src


def test_teacher_unit_node_editor_route_exists() -> None:
    loader = (
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "units"
        / "[unitId]"
        / "nodes"
        / "[nodeId]"
        / "+page.server.ts"
    )
    page = (
        REPO_ROOT
        / "frontend"
        / "src"
        / "routes"
        / "teaching"
        / "units"
        / "[unitId]"
        / "nodes"
        / "[nodeId]"
        / "+page.svelte"
    )

    assert loader.exists()
    assert page.exists()

    loader_src = loader.read_text(encoding="utf-8")
    page_src = page.read_text(encoding="utf-8")

    assert "/api/teaching/views/units/" in loader_src
    assert "/editor" in loader_src
    assert "Material" in page_src
    assert "Aufgaben" in page_src
