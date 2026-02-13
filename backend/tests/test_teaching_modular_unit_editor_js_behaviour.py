"""
Teaching modular editor JS behaviour — parsing persisted edges from SSR template.

Why:
    The modular editor stores persisted edges in
    `<template id="modular-editor-edges-data">...</template>`.
    On reload, JS must read that payload correctly; otherwise teachers see an
    empty graph until they recreate edges manually.

Scope:
    JS-level behaviour test executed in a Node.js VM with a minimal DOM stub.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node not available for JS behaviour tests")


def _run_node(script: str) -> dict:
    proc = subprocess.run(
        [NODE, "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"node script failed: {proc.stderr}"
    out = (proc.stdout or "").strip()
    assert out, "node script did not produce JSON output"
    return json.loads(out)


def _edges_from_boot(*, template_content: str, template_text_content: str = "") -> list[dict]:
    script = f"""
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const src = fs.readFileSync(path.join('backend', 'web', 'static', 'js', 'teaching_modular_unit_editor.js'), 'utf8');

const templateEl = {{
  tagName: 'TEMPLATE',
  textContent: {json.dumps(template_text_content)},
  content: {{ textContent: {json.dumps(template_content)} }}
}};

const graphEl = {{
  addEventListener: () => {{}},
  removeEventListener: () => {{}}
}};

const svgEl = {{
  querySelector: () => null,
  querySelectorAll: () => [],
  insertAdjacentHTML: () => {{}},
  setAttribute: () => {{}},
  appendChild: () => {{}}
}};

const root = {{
  dataset: {{}},
  __modularEditorCtx: null,
  addEventListener: () => {{}},
  getAttribute: (name) => (name === 'data-unit-id' ? 'unit-1' : null),
  querySelector: (selector) => {{
    if (selector === '#modular-editor-edges-data') return templateEl;
    if (selector === '#modular-editor-graph') return graphEl;
    if (selector === '#modular-editor-edges') return svgEl;
    return null;
  }},
  querySelectorAll: () => []
}};

const documentStub = {{
  readyState: 'complete',
  addEventListener: () => {{}},
  querySelector: (selector) => selector === '.modular-editor[data-unit-id]' ? root : null,
  body: {{ addEventListener: () => {{}} }}
}};

const sandbox = {{
  console,
  document: documentStub,
  setTimeout: () => 0,
  clearTimeout: () => {{}},
  requestAnimationFrame: () => 0,
  addEventListener: () => {{}},
  removeEventListener: () => {{}},
  localStorage: {{ getItem: () => null, setItem: () => {{}} }},
  fetch: () => Promise.reject(new Error('unused in this test'))
}};
sandbox.window = sandbox;

vm.runInNewContext(src, sandbox);

const edges = root.__modularEditorCtx && root.__modularEditorCtx.edgeOverlay
  ? root.__modularEditorCtx.edgeOverlay.getEdges()
  : null;

console.log(JSON.stringify({{ edges }}));
    """
    data = _run_node(script)
    edges = data.get("edges")
    assert isinstance(edges, list)
    return edges


def test_modular_editor_reads_edges_from_template_content_on_reload() -> None:
    edges = _edges_from_boot(
        template_content='[{"from":"mod-a","to":"mod-b"}]',
        template_text_content="",
    )
    assert {"from": "mod-a", "to": "mod-b"} in edges


def test_modular_editor_template_parser_returns_empty_list_when_container_is_empty() -> None:
    edges = _edges_from_boot(template_content="", template_text_content="")
    assert edges == []


def test_modular_editor_template_parser_returns_empty_list_for_invalid_json() -> None:
    edges = _edges_from_boot(template_content="{not valid", template_text_content="")
    assert edges == []
