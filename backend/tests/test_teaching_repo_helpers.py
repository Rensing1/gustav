"""DB test prerequisites must expose stale wiring instead of hiding contracts."""

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.teaching.repo_db import DBTeachingRepo
from backend.tests.utils import teaching as helpers


def test_helper_resolves_the_current_module_each_time_without_repair(monkeypatch):
    calls = []
    monkeypatch.setattr(helpers, "require_db_or_skip", lambda: calls.append("db"))
    first, second = object.__new__(DBTeachingRepo), object.__new__(DBTeachingRepo)
    for repo in (first, second, first):

        def get_repo():
            assert calls[-1] == "db"
            calls.append("repo")
            return repo

        current = SimpleNamespace(_get_repo=get_repo)
        monkeypatch.setitem(sys.modules, "backend.web.routes.teaching", current)
        assert helpers.require_teaching_db_repo() is repo
        assert vars(current) == {"_get_repo": get_repo}
    assert calls == ["db", "repo"] * 3


def test_wrong_adapter_with_available_db_is_failure_not_skip(monkeypatch):
    monkeypatch.setattr(helpers, "require_db_or_skip", lambda: None)
    monkeypatch.setitem(
        sys.modules, "backend.web.routes.teaching", SimpleNamespace(_get_repo=lambda: object())
    )
    with pytest.raises(AssertionError, match="current Teaching repository"):
        helpers.require_teaching_db_repo()


@pytest.mark.parametrize("error", [pytest.skip.Exception, pytest.fail.Exception])
def test_db_prerequisite_decision_precedes_repository_access(monkeypatch, error):
    def unavailable():
        raise error("DB prerequisite")

    monkeypatch.setattr(helpers, "require_db_or_skip", unavailable)
    monkeypatch.setitem(
        sys.modules,
        "backend.web.routes.teaching",
        SimpleNamespace(_get_repo=lambda: pytest.fail("DB prerequisite was bypassed")),
    )
    with pytest.raises(error, match="DB prerequisite"):
        helpers.require_teaching_db_repo()


@pytest.mark.parametrize(
    "filename,count",
    [
        ("test_teaching_courses_api.py", 5),
        ("test_teaching_materials_markdown_api.py", 6),
        ("test_teaching_members_semantics.py", 12),
        ("test_teaching_modular_unit_editor_crud_api_contract.py", 6),
        ("test_teaching_modular_unit_graph_api_contract.py", 7),
        ("test_teaching_module_section_releases_api.py", 1),
        ("test_teaching_module_sections_list_api.py", 2),
        ("test_teaching_module_sections_releases_headers.py", 1),
        ("test_teaching_section_visibility_api.py", 3),
    ],
)
def test_reactivated_contracts_use_current_db_prerequisite(filename, count):
    source = Path(__file__).with_name(filename).read_text()
    tree = ast.parse(source)
    assert "DB-backed TeachingRepo required" not in source
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "require_teaching_db_repo"
    ]
    assert len(calls) == count
