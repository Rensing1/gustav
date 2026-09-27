"""Focused contracts for the framework-independent Live practice read model."""

from __future__ import annotations

from backend.teaching.live_practice import build_practice_modules, classify_practice_module
from backend.teaching.live_tasks import load_live_tasks


class _Reader:
    def list_sections_for_author(self, unit_id: str, author_id: str):
        assert (unit_id, author_id) == ("unit-1", "teacher-1")
        return [
            {"id": "section-learning", "title": "Lernen", "position": 1, "module_id": "module-learning", "module_kind": "learning"},
            {"id": "section-practice", "title": "Üben", "position": 2, "module_id": "module-practice", "module_kind": "practice"},
        ]

    def list_tasks_for_unit_owned(self, unit_id: str, author_id: str):
        return [
            {"id": "task-practice", "section_id": "section-practice", "position": 1, "kind": "native", "instruction_md": "P"},
            {"id": "task-learning", "section_id": "section-learning", "position": 1, "kind": "native", "instruction_md": "L"},
        ]


def test_live_tasks_expose_module_identity_and_kind_without_reordering() -> None:
    tasks = load_live_tasks(_Reader(), "unit-1", "teacher-1")

    assert [(task["id"], task["module_kind"], task["module_id"]) for task in tasks] == [
        ("task-learning", "learning", "module-learning"),
        ("task-practice", "practice", "module-practice"),
    ]


def test_practice_status_prioritizes_access_due_and_weakest_classification() -> None:
    assert classify_practice_module(access_status="locked", due=3, secure=0, partial=0, insufficient=0, task_count=3) == "locked"
    assert classify_practice_module(access_status="open", due=1, secure=2, partial=0, insufficient=0, task_count=3) == "due"
    assert classify_practice_module(access_status="open", due=0, secure=1, partial=1, insufficient=1, task_count=3) == "insufficient"
    assert classify_practice_module(access_status="open", due=0, secure=2, partial=1, insufficient=0, task_count=3) == "partial"
    assert classify_practice_module(access_status="open", due=0, secure=3, partial=0, insufficient=0, task_count=3) == "secure"


def test_empty_accessible_practice_module_does_not_invent_secure_state() -> None:
    assert classify_practice_module(access_status="open", due=0, secure=0, partial=0, insufficient=0, task_count=0) == "partial"


def test_practice_module_catalog_keeps_empty_modules_in_teaching_order() -> None:
    modules = build_practice_modules(
        sections=[
            {"id": "learning-section", "title": "Lernen", "position": 1, "module_id": "learning", "module_kind": "learning"},
            {"id": "practice-empty", "title": "Leeres Üben", "position": 2, "module_id": "practice-a", "module_kind": "practice"},
            {"id": "practice-full", "title": "Volles Üben", "position": 3, "module_id": "practice-b", "module_kind": "practice"},
        ],
        tasks=[
            {"id": "task-b", "section_id": "practice-full", "module_id": "practice-b", "module_kind": "practice"}
        ],
    )

    assert modules == [
        {"id": "practice-a", "section_id": "practice-empty", "title": "Leeres Üben", "task_ids": []},
        {"id": "practice-b", "section_id": "practice-full", "title": "Volles Üben", "task_ids": ["task-b"]},
    ]
