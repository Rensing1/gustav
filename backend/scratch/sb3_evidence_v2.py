"""
Deterministic SB3 evidence extraction (v2).

Intent:
    Convert Scratch `project.json` into a stable, injection-hardened Markdown
    report that makes program structure *explicit*:
      - scripts (topLevel stacks)
      - control-flow nesting (SUBSTACK / SUBSTACK2)
      - parameter values (inputs/fields)
      - procedures (My Blocks) + clones

Why:
    Opcode counts alone are insufficient for reliable, criteria-oriented
    evaluation (e.g. "set size before each run" requires order/structure).

Security:
    - Deterministic: no LLM calls.
    - Injection-hardened: user-controlled strings are JSON-escaped and truncated.
    - Bounded: hard limits + explicit truncation markers.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable


EVIDENCE_SCHEMA_V2 = "scratch.evidence.v2"

_NUM_RE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
_SUBSTACK_KEYS = ("SUBSTACK", "SUBSTACK2")


@dataclass(frozen=True, slots=True)
class EvidenceV2Limits:
    """Hard limits used while rendering evidence."""

    max_name_chars: int = 80
    max_markdown_chars: int = 200_000
    max_targets: int = 100
    max_scripts_per_target: int = 200
    max_blocks_per_script: int = 1_000
    max_stack_depth: int = 25
    max_expr_depth: int = 6
    reserved_truncation_chars: int = 1_200


def limits_from_env(defaults: EvidenceV2Limits | None = None) -> EvidenceV2Limits:
    """Build limits with optional ENV overrides (prod-compatible)."""
    base = defaults or EvidenceV2Limits()

    def _int(name: str, default: int) -> int:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return int(default)
        try:
            val = int(raw)
        except Exception:
            return int(default)
        return max(1, val)

    return EvidenceV2Limits(
        max_name_chars=_int("SCRATCH_EVIDENCE_MAX_NAME_CHARS", base.max_name_chars),
        max_markdown_chars=_int("SCRATCH_EVIDENCE_MAX_MARKDOWN_CHARS", base.max_markdown_chars),
        max_targets=_int("SCRATCH_EVIDENCE_MAX_TARGETS", base.max_targets),
        max_scripts_per_target=_int("SCRATCH_EVIDENCE_MAX_SCRIPTS_PER_TARGET", base.max_scripts_per_target),
        max_blocks_per_script=_int("SCRATCH_EVIDENCE_MAX_BLOCKS_PER_SCRIPT", base.max_blocks_per_script),
        max_stack_depth=_int("SCRATCH_EVIDENCE_MAX_STACK_DEPTH", base.max_stack_depth),
        max_expr_depth=_int("SCRATCH_EVIDENCE_MAX_EXPR_DEPTH", base.max_expr_depth),
        reserved_truncation_chars=_int("SCRATCH_EVIDENCE_RESERVED_TRUNCATION_CHARS", base.reserved_truncation_chars),
    )


def _json_str(value: object, *, limits: EvidenceV2Limits) -> str:
    raw = str(value or "")
    if len(raw) > limits.max_name_chars:
        raw = raw[: limits.max_name_chars] + "…"
    return json.dumps(raw, ensure_ascii=False)


def _render_literal(value: object, *, limits: EvidenceV2Limits) -> str:
    s = str(value or "")
    if len(s) > limits.max_name_chars:
        s = s[: limits.max_name_chars] + "…"
    if _NUM_RE.fullmatch(s):
        return s
    return json.dumps(s, ensure_ascii=False)


def _sorted_bounded(values: Iterable[str], *, limits: EvidenceV2Limits, max_items: int = 50) -> list[str]:
    unique = sorted({str(v) for v in values if str(v).strip()}, key=lambda x: x.casefold())
    if len(unique) > max_items:
        return unique[:max_items] + ["…"]
    return unique


def _parse_json_string_list(value: object) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            out.append(item)
    return out


def _target_blocks(target: dict[str, Any]) -> dict[str, Any]:
    blocks = target.get("blocks")
    return blocks if isinstance(blocks, dict) else {}


def _parse_primitive(desc: object, *, limits: EvidenceV2Limits) -> str:
    """Render a primitive descriptor (Scratch input encoding) deterministically."""
    if not isinstance(desc, (list, tuple)) or len(desc) < 2:
        return _render_literal(desc, limits=limits)
    type_code = desc[0]
    value = desc[1]
    try:
        code = int(type_code)
    except Exception:
        code = None
    if code == 12 and isinstance(value, str):
        # Variable reference: [12, "name", "id"]
        return f"var:{_json_str(value, limits=limits)}"
    if code == 13 and isinstance(value, str):
        # List reference: [13, "name", "id"]
        return f"list:{_json_str(value, limits=limits)}"
    if code == 11 and isinstance(value, str):
        # Broadcast reference: [11, "name", "id"]
        return f"broadcast:{_json_str(value, limits=limits)}"
    # Fallback: treat as literal string/number.
    return _render_literal(value, limits=limits)


def _parse_input_ref(value: object, *, blocks: dict[str, Any], limits: EvidenceV2Limits, depth: int, visited: set[str]) -> str:
    """Render an input value which may be a block reference or primitive."""
    if isinstance(value, str):
        return _render_expr_from_block(value, blocks=blocks, limits=limits, depth=depth + 1, visited=visited)
    if isinstance(value, (list, tuple)):
        return _parse_primitive(value, limits=limits)
    return _render_literal(value, limits=limits)


def _render_input(value: object, *, blocks: dict[str, Any], limits: EvidenceV2Limits, depth: int, visited: set[str]) -> str:
    """Render a Scratch `inputs` entry value."""
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return _render_literal(value, limits=limits)
    primary = value[1]
    return _parse_input_ref(primary, blocks=blocks, limits=limits, depth=depth, visited=visited)


def _render_menu_shadow(block: dict[str, Any], *, limits: EvidenceV2Limits) -> str | None:
    """Compact rendering for common shadow/menu reporter blocks."""
    opcode = str(block.get("opcode") or "")
    fields = block.get("fields") if isinstance(block.get("fields"), dict) else {}

    def _field(name: str) -> str | None:
        raw = fields.get(name)
        if isinstance(raw, (list, tuple)) and raw:
            return str(raw[0])
        return None

    if opcode == "looks_costume":
        name = _field("COSTUME")
        return f"costume:{_json_str(name, limits=limits)}" if name is not None else None
    if opcode == "sound_sounds_menu":
        name = _field("SOUND_MENU")
        return f"sound:{_json_str(name, limits=limits)}" if name is not None else None
    if opcode == "sensing_keyoptions":
        key = _field("KEY_OPTION")
        return f"key:{_json_str(key, limits=limits)}" if key is not None else None
    if opcode == "sensing_touchingobjectmenu":
        obj = _field("TOUCHINGOBJECTMENU")
        return f"object:{_json_str(obj, limits=limits)}" if obj is not None else None
    if opcode == "control_create_clone_of_menu":
        opt = _field("CLONE_OPTION")
        return f"clone_of:{_json_str(opt, limits=limits)}" if opt is not None else None
    return None


def _render_expr_from_block(block_id: str, *, blocks: dict[str, Any], limits: EvidenceV2Limits, depth: int, visited: set[str]) -> str:
    """Render a reporter/boolean expression from a block id (bounded)."""
    if depth > limits.max_expr_depth:
        return "…"
    if not block_id or block_id in visited:
        return "…"
    block = blocks.get(block_id)
    if not isinstance(block, dict):
        return "…"
    visited.add(block_id)
    try:
        if block.get("shadow") is True:
            compact = _render_menu_shadow(block, limits=limits)
            if compact:
                return compact
        opcode = str(block.get("opcode") or "")
        parts: list[str] = []
        fields = block.get("fields") if isinstance(block.get("fields"), dict) else {}
        for k in sorted(fields.keys(), key=lambda x: str(x).casefold()):
            raw = fields.get(k)
            if isinstance(raw, (list, tuple)) and raw:
                parts.append(f"{k}={_json_str(raw[0], limits=limits)}")
        inputs = block.get("inputs") if isinstance(block.get("inputs"), dict) else {}
        for k in sorted(inputs.keys(), key=lambda x: str(x).casefold()):
            if k in _SUBSTACK_KEYS:
                continue
            parts.append(f"{k}={_render_input(inputs.get(k), blocks=blocks, limits=limits, depth=depth, visited=visited)}")
        joined = ", ".join(parts)
        return f"{opcode}({joined})" if joined else opcode
    finally:
        visited.discard(block_id)


def _render_block_line(
    block: dict[str, Any],
    *,
    blocks: dict[str, Any],
    limits: EvidenceV2Limits,
    indent: int,
    expr_depth: int,
    expr_visited: set[str],
) -> str:
    opcode = str(block.get("opcode") or "")
    parts: list[str] = []

    inputs = block.get("inputs") if isinstance(block.get("inputs"), dict) else {}

    # Procedure blocks: expose proccode for reliable matching.
    if opcode in {"procedures_definition", "procedures_prototype", "procedures_call"}:
        mut = block.get("mutation")
        if isinstance(mut, dict):
            proccode = mut.get("proccode")
            if isinstance(proccode, str) and proccode:
                parts.append(f"proccode={_json_str(proccode, limits=limits)}")
            warp = mut.get("warp")
            if isinstance(warp, str) and warp:
                parts.append(f"warp={_render_literal(warp, limits=limits)}")

            # For call-sites, map argument ids to names (if available).
            if opcode == "procedures_call":
                arg_ids = _parse_json_string_list(mut.get("argumentids"))
                arg_names = _parse_json_string_list(mut.get("argumentnames"))
                if arg_ids and arg_names and len(arg_ids) == len(arg_names):
                    mapped: list[str] = []
                    for aid, aname in zip(arg_ids, arg_names, strict=False):
                        val = inputs.get(aid)
                        expr_val = _render_input(val, blocks=blocks, limits=limits, depth=expr_depth, visited=expr_visited)
                        mapped.append(f"{_json_str(aname, limits=limits)}: {expr_val}")
                    parts.append("args={" + ", ".join(mapped) + "}")

    fields = block.get("fields") if isinstance(block.get("fields"), dict) else {}
    for k in sorted(fields.keys(), key=lambda x: str(x).casefold()):
        raw = fields.get(k)
        if isinstance(raw, (list, tuple)) and raw:
            parts.append(f"{k}={_json_str(raw[0], limits=limits)}")

    # Render generic inputs. For procedures_call we skip arg-id keys if we already rendered `args={...}`.
    skip_input_keys: set[str] = set()
    if opcode == "procedures_call":
        mut = block.get("mutation")
        if isinstance(mut, dict):
            arg_ids = _parse_json_string_list(mut.get("argumentids"))
            skip_input_keys.update(arg_ids)
    for k in sorted(inputs.keys(), key=lambda x: str(x).casefold()):
        if k in _SUBSTACK_KEYS:
            continue
        if k in skip_input_keys:
            continue
        parts.append(f"{k}={_render_input(inputs.get(k), blocks=blocks, limits=limits, depth=expr_depth, visited=expr_visited)}")

    tail = (" " + " ".join(parts)) if parts else ""
    return (" " * indent) + f"- {opcode}{tail}"


def _top_level_blocks(blocks: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for bid, b in blocks.items():
        if not isinstance(bid, str) or not isinstance(b, dict):
            continue
        if b.get("topLevel") is True and (b.get("parent") is None):
            out.append((bid, b))
    return out


def _script_sort_key(item: tuple[str, dict[str, Any]]) -> tuple[str, int, int, str]:
    bid, b = item
    opcode = str(b.get("opcode") or "")
    try:
        x = int(b.get("x") or 0)
    except Exception:
        x = 0
    try:
        y = int(b.get("y") or 0)
    except Exception:
        y = 0
    return (opcode.casefold(), y, x, bid)


def _hat_title(block: dict[str, Any], *, blocks: dict[str, Any], limits: EvidenceV2Limits) -> str:
    opcode = str(block.get("opcode") or "")
    parts: list[str] = [opcode]

    # Enrich a few common hat blocks with their selector fields.
    fields = block.get("fields") if isinstance(block.get("fields"), dict) else {}
    for field_name in ("KEY_OPTION", "BROADCAST_OPTION", "BACKDROP", "COSTUME"):
        raw = fields.get(field_name)
        if isinstance(raw, (list, tuple)) and raw:
            parts.append(f"{field_name}={_json_str(raw[0], limits=limits)}")

    # Procedures: include proccode in the script title.
    if opcode == "procedures_definition":
        cb = (block.get("inputs") or {}).get("custom_block")
        proto_id = cb[1] if isinstance(cb, (list, tuple)) and len(cb) >= 2 and isinstance(cb[1], str) else None
        proto = blocks.get(str(proto_id)) if proto_id else None
        mut = proto.get("mutation") if isinstance(proto, dict) else None
        if isinstance(mut, dict):
            proccode = mut.get("proccode")
            if isinstance(proccode, str) and proccode:
                parts.append(f"proccode={_json_str(proccode, limits=limits)}")
            warp = mut.get("warp")
            if isinstance(warp, str) and warp:
                parts.append(f"warp={_render_literal(warp, limits=limits)}")
            arg_names = _parse_json_string_list(mut.get("argumentnames"))
            if arg_names:
                joined = ", ".join(_json_str(n, limits=limits) for n in arg_names)
                parts.append(f"args=[{joined}]")

    try:
        x = int(block.get("x"))
        y = int(block.get("y"))
        parts.append(f"(x={x},y={y})")
    except Exception:
        pass

    return " ".join(parts)


def build_evidence_markdown_v2(*, project: dict[str, Any], limits: EvidenceV2Limits | None = None) -> str:
    """Build `scratch.evidence.v2` Markdown from Scratch `project.json`."""
    limits = limits or limits_from_env()
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
    stage_present = any(bool(t.get("isStage")) for t in sorted_targets)
    sprites_total = sum(1 for t in sorted_targets if not bool(t.get("isStage")))
    blocks_total = 0
    scripts_total = 0
    for t in sorted_targets:
        b = _target_blocks(t)
        blocks_total += len(b)
        scripts_total += len(_top_level_blocks(b))

    # Writer with a small reserved tail so we can always append truncation info.
    max_chars = int(limits.max_markdown_chars)
    reserve = int(min(limits.reserved_truncation_chars, max_chars // 2))
    lines: list[str] = []
    char_count = 0

    trunc = {
        "truncated": False,
        "reason": "",
        "omitted_targets": 0,
        "omitted_scripts": 0,
        "omitted_blocks": 0,
    }

    def _add(line: str) -> bool:
        nonlocal char_count
        # +1 for newline
        projected = char_count + len(line) + 1
        if trunc["truncated"]:
            return False
        if projected > max_chars - reserve:
            trunc["truncated"] = True
            trunc["reason"] = trunc["reason"] or "max_markdown_chars"
            return False
        lines.append(line)
        char_count = projected
        return True

    # Header + summary
    _add(f"# {EVIDENCE_SCHEMA_V2}")
    _add("")
    _add("## Summary")
    _add(f"- stage_present: {'true' if stage_present else 'false'}")
    _add(f"- targets_total: {len(sorted_targets)}")
    _add(f"- sprites_total: {sprites_total}")
    _add(f"- blocks_total: {blocks_total}")
    _add(f"- top_level_scripts_total: {scripts_total}")
    _add("- truncated: false")  # patched below if needed
    _add("")

    # Targets index
    _add("## Targets")
    for idx, t in enumerate(sorted_targets):
        if idx >= limits.max_targets:
            trunc["truncated"] = True
            trunc["reason"] = trunc["reason"] or "max_targets"
            trunc["omitted_targets"] += max(0, len(sorted_targets) - idx)
            break
        name = _json_str(t.get("name"), limits=limits)
        role = "stage" if bool(t.get("isStage")) else "sprite"
        _add(f"### Target {name} ({role})")

        variables = t.get("variables") if isinstance(t.get("variables"), dict) else {}
        lists = t.get("lists") if isinstance(t.get("lists"), dict) else {}
        broadcasts = t.get("broadcasts") if isinstance(t.get("broadcasts"), dict) else {}
        costumes = t.get("costumes") if isinstance(t.get("costumes"), list) else []
        sounds = t.get("sounds") if isinstance(t.get("sounds"), list) else []

        var_names: list[str] = []
        for v in variables.values():
            if isinstance(v, (list, tuple)) and v:
                var_names.append(str(v[0]))
        list_names: list[str] = []
        for v in lists.values():
            if isinstance(v, (list, tuple)) and v:
                list_names.append(str(v[0]))
        bc_names: list[str] = [str(v) for v in broadcasts.values() if isinstance(v, str)]
        costume_names: list[str] = [str(c.get("name")) for c in costumes if isinstance(c, dict) and c.get("name")]
        sound_names: list[str] = [str(s.get("name")) for s in sounds if isinstance(s, dict) and s.get("name")]

        if var_names:
            joined = ", ".join(_json_str(v, limits=limits) for v in _sorted_bounded(var_names, limits=limits))
            _add(f"- variables: [{joined}]")
        if list_names:
            joined = ", ".join(_json_str(v, limits=limits) for v in _sorted_bounded(list_names, limits=limits))
            _add(f"- lists: [{joined}]")
        if bc_names:
            joined = ", ".join(_json_str(v, limits=limits) for v in _sorted_bounded(bc_names, limits=limits))
            _add(f"- broadcasts: [{joined}]")
        if costume_names:
            joined = ", ".join(_json_str(v, limits=limits) for v in _sorted_bounded(costume_names, limits=limits))
            _add(f"- costumes: [{joined}]")
        if sound_names:
            joined = ", ".join(_json_str(v, limits=limits) for v in _sorted_bounded(sound_names, limits=limits))
            _add(f"- sounds: [{joined}]")
        _add("")

    # Scripts
    _add("## Scripts")
    for idx, t in enumerate(sorted_targets[: limits.max_targets]):
        if trunc["truncated"]:
            break
        blocks = _target_blocks(t)
        name = _json_str(t.get("name"), limits=limits)
        _add(f"### Target {name}")
        scripts = _top_level_blocks(blocks)
        scripts.sort(key=_script_sort_key)
        for sidx, (start_id, hat) in enumerate(scripts):
            if sidx >= limits.max_scripts_per_target:
                trunc["truncated"] = True
                trunc["reason"] = trunc["reason"] or "max_scripts_per_target"
                trunc["omitted_scripts"] += max(0, len(scripts) - sidx)
                break
            _add(f"#### Script {sidx+1}: {_hat_title(hat, blocks=blocks, limits=limits)}")

            def _render_chain(*, start_id: object, indent: int, depth: int, state: dict[str, int], visited: set[str]) -> None:
                if trunc["truncated"]:
                    return
                if depth > limits.max_stack_depth:
                    trunc["truncated"] = True
                    trunc["reason"] = trunc["reason"] or "max_stack_depth"
                    return
                cur = start_id if isinstance(start_id, str) else ""
                while isinstance(cur, str) and cur:
                    if trunc["truncated"]:
                        return
                    if cur in visited:
                        _add((" " * indent) + "- … (cycle)")
                        trunc["truncated"] = True
                        trunc["reason"] = trunc["reason"] or "cycle_detected"
                        return
                    visited.add(cur)
                    b = blocks.get(cur)
                    if not isinstance(b, dict):
                        return
                    state["blocks"] += 1
                    if state["blocks"] > limits.max_blocks_per_script:
                        trunc["truncated"] = True
                        trunc["reason"] = trunc["reason"] or "max_blocks_per_script"
                        trunc["omitted_blocks"] += 1
                        return
                    expr_visited: set[str] = set()
                    _add(
                        _render_block_line(
                            b,
                            blocks=blocks,
                            limits=limits,
                            indent=indent,
                            expr_depth=0,
                            expr_visited=expr_visited,
                        )
                    )
                    inputs = b.get("inputs") if isinstance(b.get("inputs"), dict) else {}
                    for skey in _SUBSTACK_KEYS:
                        sub = inputs.get(skey)
                        sub_id = None
                        if isinstance(sub, (list, tuple)) and len(sub) >= 2 and isinstance(sub[1], str):
                            sub_id = sub[1]
                        if sub_id:
                            _render_chain(start_id=sub_id, indent=indent + 2, depth=depth + 1, state=state, visited=visited)
                    cur = b.get("next")

            state = {"blocks": 0}
            _render_chain(start_id=hat.get("next"), indent=0, depth=0, state=state, visited=set())
            _add("")

    # Patch the summary truncated flag line (keep stable line index)
    if trunc["truncated"]:
        for i, line in enumerate(lines):
            if line.strip() == "- truncated: false":
                lines[i] = "- truncated: true"
                break

        # Append explicit truncation section (best-effort within reserved tail).
        lines.append("## Truncation")
        lines.append("- truncated: true")
        if trunc["reason"]:
            lines.append(f"- reason: {trunc['reason']}")
        lines.append(f"- omitted_targets: {int(trunc['omitted_targets'])}")
        lines.append(f"- omitted_scripts: {int(trunc['omitted_scripts'])}")
        lines.append(f"- omitted_blocks: {int(trunc['omitted_blocks'])}")

    out = "\n".join(lines).rstrip() + "\n"
    if len(out) > max_chars:
        # Final guardrail: ensure bounded output even if truncation footer overflowed.
        out = out[: max_chars - 20].rstrip() + "\n\n[truncated]\n"
    return out
