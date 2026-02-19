"""
Scratch Evidence v2 — deterministic script outlines (RED)

Intent:
    `scratch.evidence.v2` must be rich enough for reliable criteria-based
    evaluation: scripts as sequences (next), control-flow nesting (SUBSTACK),
    parameter values (inputs/fields), plus procedures and clones.
"""

from __future__ import annotations

import pytest


def _min_project(*, sprite_blocks: dict) -> dict:
    return {
        "targets": [
            {
                "isStage": True,
                "name": "Stage",
                "blocks": {},
                "variables": {},
                "lists": {},
                "broadcasts": {},
                "costumes": [{"name": "backdrop1"}],
                "sounds": [],
            },
            {
                "isStage": False,
                "name": "Sprite",
                "blocks": sprite_blocks,
                "variables": {
                    "var-size": ["size", 0],
                    "var-dir": ["dir", 0],
                },
                "lists": {},
                "broadcasts": {},
                "costumes": [{"name": "costume1"}],
                "sounds": [],
            },
        ]
    }


def test_evidence_v2_renders_scripts_and_params() -> None:
    # Minimal script:
    # when flag clicked -> set var size to 200 -> repeat 3 { set size to (var size) }
    blocks = {
        "hat": {"opcode": "event_whenflagclicked", "next": "set", "parent": None, "inputs": {}, "fields": {}, "topLevel": True, "x": 10, "y": 20},
        "set": {
            "opcode": "data_setvariableto",
            "next": "repeat",
            "parent": "hat",
            "inputs": {"VALUE": [1, [10, "200"]]},
            "fields": {"VARIABLE": ["size", "var-size"]},
            "topLevel": False,
        },
        "repeat": {
            "opcode": "control_repeat",
            "next": None,
            "parent": "set",
            "inputs": {"TIMES": [1, [4, "3"]], "SUBSTACK": [2, "inside"]},
            "fields": {},
            "topLevel": False,
        },
        "inside": {
            "opcode": "looks_setsizeto",
            "next": None,
            "parent": "repeat",
            "inputs": {"SIZE": [3, [12, "size", "var-size"], [4, "100"]]},
            "fields": {},
            "topLevel": False,
        },
    }
    project = _min_project(sprite_blocks=blocks)

    from backend.scratch import sb3_evidence_v2 as ev  # type: ignore

    md = ev.build_evidence_markdown_v2(project=project)
    assert md.startswith("# scratch.evidence.v2")
    assert "## Scripts" in md
    assert "event_whenflagclicked" in md
    assert "data_setvariableto" in md
    assert 'VARIABLE="size"' in md
    assert "control_repeat" in md
    assert "TIMES=3" in md
    assert "looks_setsizeto" in md
    assert "SIZE=var:\"size\"" in md or "SIZE=var:'size'" in md or "SIZE=var:\"size\"" in md


def test_evidence_v2_includes_procedures_and_clones() -> None:
    blocks = {
        # Procedure definition
        "proc_def": {
            "opcode": "procedures_definition",
            "next": "proc_body",
            "parent": None,
            "inputs": {"custom_block": [1, "proc_proto"]},
            "fields": {},
            "topLevel": True,
            "x": 0,
            "y": 0,
        },
        "proc_proto": {
            "opcode": "procedures_prototype",
            "next": None,
            "parent": "proc_def",
            "inputs": {},
            "fields": {},
            "shadow": True,
            "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": "berechne",
                "argumentids": "[]",
                "argumentnames": "[]",
                "argumentdefaults": "[]",
                "warp": "false",
            },
        },
        "proc_body": {
            "opcode": "looks_show",
            "next": None,
            "parent": "proc_def",
            "inputs": {},
            "fields": {},
            "topLevel": False,
        },
        # Call site script
        "hat": {"opcode": "event_whenflagclicked", "next": "call", "parent": None, "inputs": {}, "fields": {}, "topLevel": True, "x": 10, "y": 10},
        "call": {
            "opcode": "procedures_call",
            "next": "mkclone",
            "parent": "hat",
            "inputs": {},
            "fields": {},
            "topLevel": False,
            "mutation": {"tagName": "mutation", "children": [], "proccode": "berechne", "argumentids": "[]", "warp": "false"},
        },
        # Clone creation + clone start script
        "mkclone": {
            "opcode": "control_create_clone_of",
            "next": None,
            "parent": "call",
            "inputs": {"CLONE_OPTION": [1, "clonemenu"]},
            "fields": {},
            "topLevel": False,
        },
        "clonemenu": {
            "opcode": "control_create_clone_of_menu",
            "next": None,
            "parent": "mkclone",
            "inputs": {},
            "fields": {"CLONE_OPTION": ["myself", None]},
            "shadow": True,
            "topLevel": False,
        },
        "clone_hat": {"opcode": "control_start_as_clone", "next": "clone_body", "parent": None, "inputs": {}, "fields": {}, "topLevel": True, "x": 50, "y": 50},
        "clone_body": {"opcode": "control_delete_this_clone", "next": None, "parent": "clone_hat", "inputs": {}, "fields": {}, "topLevel": False},
    }
    project = _min_project(sprite_blocks=blocks)

    from backend.scratch import sb3_evidence_v2 as ev  # type: ignore

    md = ev.build_evidence_markdown_v2(project=project)
    assert "procedures_definition" in md
    assert 'proccode="berechne"' in md
    assert "procedures_call" in md
    assert "control_create_clone_of" in md
    assert "control_start_as_clone" in md


def test_evidence_v2_renders_procedure_arguments_and_deep_nesting() -> None:
    blocks = {
        # Procedure definition with args
        "proc_def": {
            "opcode": "procedures_definition",
            "next": None,
            "parent": None,
            "inputs": {"custom_block": [1, "proc_proto"]},
            "fields": {},
            "topLevel": True,
            "x": 0,
            "y": 0,
        },
        "proc_proto": {
            "opcode": "procedures_prototype",
            "next": None,
            "parent": "proc_def",
            "inputs": {},
            "fields": {},
            "shadow": True,
            "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": "calc %n %n",
                "argumentids": "[\"arg1\",\"arg2\"]",
                "argumentnames": "[\"a\",\"b\"]",
                "argumentdefaults": "[\"0\",\"0\"]",
                "warp": "false",
            },
        },
        # Main script calling the procedure with args
        "hat": {
            "opcode": "event_whenflagclicked",
            "next": "call",
            "parent": None,
            "inputs": {},
            "fields": {},
            "topLevel": True,
            "x": 10,
            "y": 10,
        },
        "call": {
            "opcode": "procedures_call",
            "next": "repeat",
            "parent": "hat",
            "inputs": {
                "arg1": [1, [4, "1"]],
                "arg2": [1, [4, "2"]],
            },
            "fields": {},
            "topLevel": False,
            "mutation": {
                "tagName": "mutation",
                "children": [],
                "proccode": "calc %n %n",
                "argumentids": "[\"arg1\",\"arg2\"]",
                "argumentnames": "[\"a\",\"b\"]",
                "warp": "false",
            },
        },
        # Deeply nested control flow: repeat -> if -> forever -> show
        "repeat": {
            "opcode": "control_repeat",
            "next": None,
            "parent": "call",
            "inputs": {"TIMES": [1, [4, "2"]], "SUBSTACK": [2, "if"]},
            "fields": {},
            "topLevel": False,
        },
        "if": {
            "opcode": "control_if",
            "next": None,
            "parent": "repeat",
            "inputs": {"CONDITION": [1, [4, "1"]], "SUBSTACK": [2, "forever"]},
            "fields": {},
            "topLevel": False,
        },
        "forever": {
            "opcode": "control_forever",
            "next": None,
            "parent": "if",
            "inputs": {"SUBSTACK": [2, "show"]},
            "fields": {},
            "topLevel": False,
        },
        "show": {
            "opcode": "looks_show",
            "next": None,
            "parent": "forever",
            "inputs": {},
            "fields": {},
            "topLevel": False,
        },
    }
    project = _min_project(sprite_blocks=blocks)

    from backend.scratch import sb3_evidence_v2 as ev  # type: ignore

    md = ev.build_evidence_markdown_v2(project=project)
    # Procedure heading should mention args
    assert "procedures_definition" in md
    assert 'args=["a", "b"]' in md or 'args=["a","b"]' in md
    # Call should map arg ids to names
    assert "procedures_call" in md
    assert "\"a\"" in md and "\"b\"" in md
    # Deep nesting should be visible (looks_show must appear indented)
    assert "control_repeat" in md and "control_if" in md and "control_forever" in md
    assert "looks_show" in md


def test_evidence_v2_marks_truncation_when_limits_hit() -> None:
    blocks = {
        "hat": {"opcode": "event_whenflagclicked", "next": None, "parent": None, "inputs": {}, "fields": {}, "topLevel": True, "x": 0, "y": 0},
    }
    project = _min_project(sprite_blocks=blocks)

    from backend.scratch import sb3_evidence_v2 as ev  # type: ignore

    md = ev.build_evidence_markdown_v2(project=project, limits=ev.EvidenceV2Limits(max_markdown_chars=200))
    assert "## Truncation" in md
    assert "truncated: true" in md
