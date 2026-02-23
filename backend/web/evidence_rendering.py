"""
SSR Evidence Rendering Helpers.

Intent:
    Keep `backend/web/main.py` focused on routing/HTML composition while
    centralizing evidence-specific rendering rules in one place.

Design:
    - Deterministic: no LLM calls, no network.
    - Fail-open: do not hide user-authored text just because it starts with an
      evidence marker (defense-in-depth against false positives).
    - Scoped CSS: wrap evidence HTML in marker-specific container classes so
      CSS can style evidence without affecting regular student text.
"""

from __future__ import annotations

import json

from components.markdown import render_markdown_safe


def _is_scratch_evidence_markdown(text: str) -> bool:
    return bool((text or "").lstrip().startswith("# scratch.evidence."))


def _is_makecode_evidence_v1_markdown(text: str) -> bool:
    return bool((text or "").lstrip().startswith("# makecode.evidence.v1"))


def _code_fence_for_text(text: str) -> str:
    """Return a backtick fence that cannot be closed by the given text."""
    max_run = 0
    run = 0
    for ch in text or "":
        if ch == "`":
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return "`" * max(3, max_run + 1)


def _extract_makecode_files_from_evidence_v1(evidence_md: str) -> dict[str, str]:
    """Extract MakeCode file contents from `makecode.evidence.v1` Markdown.

    Notes:
        We intentionally parse only the tiny subset of Markdown we generate in
        `backend/makecode/hex_evidence_v1.py`:
        - headings: `### file: <json-string>`
        - fenced blocks: ```lang ... ```

        This keeps SSR deterministic and avoids adding a full Markdown AST
        dependency just for evidence selection.
    """
    if not _is_makecode_evidence_v1_markdown(evidence_md):
        return {}

    lines = str(evidence_md or "").splitlines()
    out: dict[str, str] = {}

    def _parse_fence(line: str) -> str | None:
        s = (line or "").strip()
        if not s.startswith("`"):
            return None
        n = 0
        for ch in s:
            if ch == "`":
                n += 1
            else:
                break
        return ("`" * n) if n >= 3 else None

    i = 0
    while i < len(lines):
        line = (lines[i] or "").strip()
        if not line.startswith("### file:"):
            i += 1
            continue
        raw_name = line[len("### file:") :].strip()
        try:
            name = json.loads(raw_name)
        except Exception:
            i += 1
            continue
        if not isinstance(name, str) or not name:
            i += 1
            continue

        # Find the next fenced block for this file.
        j = i + 1
        fence = None
        while j < len(lines):
            fence = _parse_fence(lines[j])
            if fence:
                break
            # Next file section starts before a fence: abort.
            if (lines[j] or "").strip().startswith("### file:"):
                fence = None
                break
            j += 1
        if not fence:
            i += 1
            continue

        # Capture until the closing fence.
        k = j + 1
        buf: list[str] = []
        while k < len(lines):
            if (lines[k] or "").strip() == fence:
                break
            buf.append(lines[k])
            k += 1
        if k >= len(lines):
            i = k
            continue
        out[name] = "\n".join(buf).rstrip()
        i = k + 1
    return out


def _compact_makecode_evidence_v1_for_display(evidence_md: str) -> str:
    """Return compact Markdown for UI from a full MakeCode evidence report."""
    files = _extract_makecode_files_from_evidence_v1(evidence_md)
    if not files:
        # Not a valid evidence payload (or not parseable): fail open so we don't
        # accidentally hide user-authored text that happens to start with the marker.
        return ""

    chosen_name = "main.py" if "main.py" in files else ("main.ts" if "main.ts" in files else "")
    if not chosen_name:
        return (
            "Kein `main.py` oder `main.ts` gefunden.\n\n"
            "Bitte im MakeCode-Editor auf Python umstellen und erneut als `.hex` herunterladen.\n"
        )
    body = files.get(chosen_name, "") or ""
    lang = "python" if chosen_name.endswith(".py") else "typescript"
    fence = _code_fence_for_text(body)
    return f"## {chosen_name}\n\n{fence}{lang}\n{body.rstrip()}\n{fence}\n"


def render_submission_text_html(*, text_src: str) -> str:
    """Render submission text/evidence Markdown to safe HTML with scoped wrappers."""
    raw = str(text_src or "")

    if _is_makecode_evidence_v1_markdown(raw):
        compact_md = _compact_makecode_evidence_v1_for_display(raw)
        if compact_md.strip():
            html = render_markdown_safe(compact_md)
            return f'<div class="makecode-evidence">{html}</div>' if html else ""

    html = render_markdown_safe(raw)
    if html and _is_scratch_evidence_markdown(raw):
        html = f'<div class="scratch-evidence">{html}</div>'
    return html


__all__ = ["render_submission_text_html"]

