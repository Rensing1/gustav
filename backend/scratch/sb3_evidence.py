"""
Deterministic SB3 evidence extraction.

Intent:
    Convert Scratch `project.json` into a compact, stable Markdown report that
    downstream LLMs can use as `student_text_md` for criteria-based feedback.

Design:
    - Deterministic (no LLM calls)
    - Bounded output size (safe for prompts and storage)
    - Injection-hardened: user-controlled strings are escaped and truncated
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


EVIDENCE_SCHEMA = "scratch.evidence.v1"


@dataclass(frozen=True, slots=True)
class EvidenceLimits:
    max_name_chars: int = 80
    max_list_items: int = 50
    max_markdown_chars: int = 65_536
    max_top_opcodes: int = 40


def _json_str(value: object, *, limits: EvidenceLimits) -> str:
    """Return a JSON-escaped string literal (bounded)."""
    raw = str(value or "")
    if len(raw) > limits.max_name_chars:
        raw = raw[: limits.max_name_chars] + "…"
    # JSON encoding avoids accidental Markdown injection.
    return json.dumps(raw, ensure_ascii=False)


def _sorted_bounded(values: Iterable[str], *, limits: EvidenceLimits) -> list[str]:
    unique = sorted({str(v) for v in values if str(v).strip()})
    if len(unique) > limits.max_list_items:
        return unique[: limits.max_list_items] + ["…"]
    return unique


def _target_blocks(target: dict[str, Any]) -> dict[str, Any]:
    blocks = target.get("blocks")
    return blocks if isinstance(blocks, dict) else {}


def _count_opcodes(blocks: dict[str, Any]) -> Counter[str]:
    c: Counter[str] = Counter()
    for block in blocks.values():
        if not isinstance(block, dict):
            continue
        opcode = block.get("opcode")
        if isinstance(opcode, str) and opcode:
            c[opcode] += 1
    return c


def _count_top_level_stacks(blocks: dict[str, Any]) -> int:
    total = 0
    for block in blocks.values():
        if not isinstance(block, dict):
            continue
        if block.get("topLevel") is True:
            total += 1
    return total


def build_evidence_markdown(*, project: dict[str, Any], limits: EvidenceLimits | None = None) -> str:
    """Build a bounded Markdown evidence report from Scratch `project.json`."""
    limits = limits or EvidenceLimits()
    targets = project.get("targets")
    if not isinstance(targets, list):
        targets = []

    # Stage first, then sprites by name (stable ordering)
    def _t_key(t: object) -> tuple[int, str]:
        if not isinstance(t, dict):
            return (1, "")
        is_stage = bool(t.get("isStage"))
        name = str(t.get("name") or "")
        return (0 if is_stage else 1, name.casefold())

    sorted_targets = [t for t in sorted(targets, key=_t_key) if isinstance(t, dict)]

    blocks_total = 0
    stacks_total = 0
    global_opcodes: Counter[str] = Counter()
    stage_present = any(bool(t.get("isStage")) for t in sorted_targets)
    sprites_total = sum(1 for t in sorted_targets if not bool(t.get("isStage")))

    per_target: list[dict[str, Any]] = []
    for t in sorted_targets:
        blocks = _target_blocks(t)
        opcodes = _count_opcodes(blocks)
        top_level = _count_top_level_stacks(blocks)
        blocks_total += len(blocks)
        stacks_total += top_level
        global_opcodes.update(opcodes)

        variables = t.get("variables")
        lists = t.get("lists")
        broadcasts = t.get("broadcasts")
        var_names: list[str] = []
        list_names: list[str] = []
        broadcast_names: list[str] = []
        if isinstance(variables, dict):
            for v in variables.values():
                if isinstance(v, (list, tuple)) and v:
                    var_names.append(str(v[0]))
        if isinstance(lists, dict):
            for v in lists.values():
                if isinstance(v, (list, tuple)) and v:
                    list_names.append(str(v[0]))
        if isinstance(broadcasts, dict):
            for v in broadcasts.values():
                if isinstance(v, str):
                    broadcast_names.append(v)

        per_target.append(
            {
                "is_stage": bool(t.get("isStage")),
                "name": str(t.get("name") or ""),
                "blocks_total": len(blocks),
                "top_level_stacks": top_level,
                "opcodes": opcodes,
                "variables": _sorted_bounded(var_names, limits=limits),
                "lists": _sorted_bounded(list_names, limits=limits),
                "broadcasts": _sorted_bounded(broadcast_names, limits=limits),
            }
        )

    top_opcodes = global_opcodes.most_common(limits.max_top_opcodes)

    lines: list[str] = []
    lines.append(f"# {EVIDENCE_SCHEMA}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- stage_present: {'true' if stage_present else 'false'}")
    lines.append(f"- targets_total: {len(sorted_targets)}")
    lines.append(f"- sprites_total: {sprites_total}")
    lines.append(f"- blocks_total: {blocks_total}")
    lines.append(f"- top_level_stacks_total: {stacks_total}")
    if top_opcodes:
        joined = ", ".join(f"{name}={count}" for name, count in top_opcodes)
        lines.append(f"- opcodes_top: {joined}")
    lines.append("")
    lines.append("## Targets")

    for t in per_target:
        name = _json_str(t["name"], limits=limits)
        role = "stage" if t["is_stage"] else "sprite"
        lines.append(f"### Target {name} ({role})")
        lines.append(f"- blocks_total: {int(t['blocks_total'])}")
        lines.append(f"- top_level_stacks: {int(t['top_level_stacks'])}")
        if t["variables"]:
            vars_joined = ", ".join(_json_str(v, limits=limits) for v in t["variables"])
            lines.append(f"- variables: [{vars_joined}]")
        if t["lists"]:
            lists_joined = ", ".join(_json_str(v, limits=limits) for v in t["lists"])
            lines.append(f"- lists: [{lists_joined}]")
        if t["broadcasts"]:
            bc_joined = ", ".join(_json_str(v, limits=limits) for v in t["broadcasts"])
            lines.append(f"- broadcasts: [{bc_joined}]")

        opcodes: Counter[str] = t["opcodes"]
        notable = {k: int(v) for k, v in sorted(opcodes.items()) if k.startswith(("event_", "control_", "looks_", "motion_", "operator_", "data_"))}
        if notable:
            # Keep this section stable and readable; counts help rubric matching.
            sample = list(notable.items())[: limits.max_top_opcodes]
            joined = ", ".join(f"{k}={v}" for k, v in sample)
            lines.append(f"- notable_opcodes: {joined}")
        lines.append("")

    out = "\n".join(lines).strip() + "\n"
    if len(out) > limits.max_markdown_chars:
        out = out[: limits.max_markdown_chars - 50].rstrip() + "\n\n[truncated]\n"
    return out

