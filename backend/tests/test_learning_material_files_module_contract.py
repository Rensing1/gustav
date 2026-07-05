"""Contracts for keeping learner material-file helpers outside the route hotspot."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_learning_material_file_helpers_live_in_focused_module() -> None:
    learning = importlib.import_module("backend.web.routes.learning")
    material_files = importlib.import_module("backend.web.routes.learning_material_files")

    assert learning._resolve_student_material_file_url is material_files.resolve_student_material_file_url
    assert learning._resolve_student_modular_material_file_url is material_files.resolve_student_modular_material_file_url
    assert learning._attach_section_material_files is material_files.attach_section_material_files
    assert learning._attach_modular_material_files is material_files.attach_modular_material_files


def test_learning_route_hotspot_no_longer_defines_material_file_helpers() -> None:
    source = (REPO_ROOT / "backend" / "web" / "routes" / "learning.py").read_text(encoding="utf-8")

    assert "def _resolve_student_material_file_url(" not in source
    assert "def _load_visible_material_file_metadata(" not in source
    assert "def _resolve_student_modular_material_file_url(" not in source
    assert "def _attach_section_material_files(" not in source
    assert "def _attach_modular_material_files(" not in source


def test_focused_material_file_module_keeps_readable_public_helper_names() -> None:
    material_files = importlib.import_module("backend.web.routes.learning_material_files")
    source = inspect.getsource(material_files)

    assert "def attach_section_material_files(" in source
    assert "def attach_modular_material_files(" in source
    assert "def resolve_student_material_file_url(" in source
