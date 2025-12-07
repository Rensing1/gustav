"""
Teaching Live UI behaviour — JS-level smoke tests

These tests execute the compiled `gustav.js` in a Node.js VM context with a
minimal DOM stub. They focus on two critical pieces of behaviour that are
hard to validate from pure SSR HTML tests:

- Tab switching logic in `initTeachingLiveTabs` (CSP-safe, no inline script).
- Polling cursor propagation in `initTeachingLivePolling` (status bar +
  `hx-vals` cursor propagation based on the HX-Trigger event).

If Node.js is not available in the environment, the tests are skipped.
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
    """Execute a small Node.js script and parse its JSON stdout payload."""
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


def test_teaching_live_tabs_toggle_panels():
    """Tabs should switch active state and panel visibility on click."""
    script = r"""
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const src = fs.readFileSync(path.join('backend','web','static','js','gustav.js'), 'utf8');

// Minimal sandbox with document/window stubs so the Gustav constructor
// does not attempt to fully initialise the UI.
const sandbox = {
  console,
  setTimeout: (fn, ms) => 0,
  clearTimeout: () => {},
};

sandbox.document = {
  readyState: 'loading',
  addEventListener: () => {},
};
sandbox.window = sandbox;

vm.runInNewContext(src, sandbox);
const gustav = sandbox.window.gustav;

function makeClassList(initialActive) {
  const classes = new Set(initialActive ? ['active'] : []);
  return {
    _set: classes,
    toggle(name, on) {
      if (on) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
    },
    contains(name) {
      return classes.has(name);
    }
  };
}

let card = null;

function makeButton(id, key, isActive) {
  const attrs = { 'data-view-tab': key, 'aria-selected': isActive ? 'true' : 'false' };
  return {
    id,
    _tabKey: key,
    classList: makeClassList(isActive),
    attributes: attrs,
    getAttribute(name) {
      if (name === 'data-view-tab') return this._tabKey;
      return this.attributes[name];
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    closest(selector) {
      if (selector === '[data-view-tab]') return this;
      if (selector === '.card') return card;
      return null;
    }
  };
}

function makePanel(key, visible) {
  return {
    _panelKey: key,
    hidden: !visible,
    getAttribute(name) {
      if (name === 'data-panel') return this._panelKey;
      return null;
    }
  };
}

const btnAnalysis = makeButton('btn-analysis', 'analysis', true);
const btnFeedback = makeButton('btn-feedback', 'feedback', false);
const panelAnalysis = makePanel('analysis', true);
const panelFeedback = makePanel('feedback', false);

card = {
  querySelectorAll(selector) {
    if (selector === '[data-view-tab]') return [btnAnalysis, btnFeedback];
    if (selector === '[data-panel]') return [panelAnalysis, panelFeedback];
    return [];
  }
};

let clickHandler = null;
const container = {
  _tabsDelegationReady: false,
  addEventListener(type, handler) {
    if (type === 'click') {
      clickHandler = handler;
    }
  },
  contains(node) {
    return node === btnAnalysis || node === btnFeedback;
  }
};

const scope = {
  querySelector(selector) {
    if (selector === '#live-detail') return container;
    return null;
  }
};

gustav.initTeachingLiveTabs(scope);

// Simulate a click on the "feedback" tab button.
if (clickHandler) {
  clickHandler({ target: btnFeedback });
}

const result = {
  buttons: [
    {
      id: btnAnalysis.id,
      active: btnAnalysis.classList.contains('active'),
      ariaSelected: btnAnalysis.attributes['aria-selected']
    },
    {
      id: btnFeedback.id,
      active: btnFeedback.classList.contains('active'),
      ariaSelected: btnFeedback.attributes['aria-selected']
    }
  ],
  panels: {
    analysisHidden: panelAnalysis.hidden,
    feedbackHidden: panelFeedback.hidden
  }
};

console.log(JSON.stringify(result));
    """
    data = _run_node(script)
    buttons = {b["id"]: b for b in data["buttons"]}
    # After clicking "feedback": it should be active and its panel visible,
    # while "analysis" is inactive and its panel hidden.
    assert buttons["btn-analysis"]["active"] is False
    assert buttons["btn-analysis"]["ariaSelected"] == "false"
    assert buttons["btn-feedback"]["active"] is True
    assert buttons["btn-feedback"]["ariaSelected"] == "true"
    assert data["panels"]["analysisHidden"] is True
    assert data["panels"]["feedbackHidden"] is False


def test_teaching_live_polling_advances_cursor_and_hx_vals():
    """Polling should seed and advance the cursor in hx-vals + status bar."""
    script = r"""
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const src = fs.readFileSync(path.join('backend','web','static','js','gustav.js'), 'utf8');

const sandbox = {
  console,
  setTimeout: (fn, ms) => 0,
  clearTimeout: () => {},
};

// Ensure constructor does not auto-init the full UI.
sandbox.document = {
  readyState: 'loading',
  addEventListener: () => {},
};
sandbox.window = sandbox;
sandbox.document.body = { addEventListener: () => {} };

vm.runInNewContext(src, sandbox);
const gustav = sandbox.window.gustav;

// DOM stubs for status + section
const initialCursor = '2025-01-02T03:04:05.000000+00:00';
const nextCursor = '2025-01-02T03:05:06.000000+00:00';

const statusEl = {
  attrs: { 'data-updated-since': initialCursor },
  textContent: 'Letzte Aktualisierung: jetzt',
  setAttribute(name, value) { this.attrs[name] = value; },
  getAttribute(name) { return this.attrs[name]; },
  classList: { add: () => {} }
};

const sectionEl = {
  attrs: {},
  setAttribute(name, value) { this.attrs[name] = value; },
  getAttribute(name) { return this.attrs[name]; }
};

let liveCursorHandler = null;

sandbox.document.getElementById = (id) => {
  if (id === 'live-status') return statusEl;
  if (id === 'live-section') return sectionEl;
  return null;
};

sandbox.document.body.addEventListener = (eventName, handler) => {
  if (eventName === 'liveCursorUpdated') {
    liveCursorHandler = handler;
  }
};

// Seed hx-vals and attach listener
gustav.initTeachingLivePolling();

// Simulate HX-Trigger event from the server
if (liveCursorHandler) {
  liveCursorHandler({ detail: { cursor: nextCursor } });
}

const result = {
  initialCursor,
  nextCursor,
  statusCursor: statusEl.attrs['data-updated-since'],
  statusText: statusEl.textContent,
  hxVals: sectionEl.attrs['hx-vals'] || null
};

console.log(JSON.stringify(result));
    """
    data = _run_node(script)
    assert data["statusCursor"] == data["nextCursor"]
    # Status text should keep the German prefix, time part depends on locale.
    assert data["statusText"].startswith("Letzte Aktualisierung:")
    assert data["hxVals"], "hx-vals should be set on the live section"
    hx_vals = json.loads(data["hxVals"])
    assert hx_vals["updated_since"] == data["nextCursor"]


def test_teaching_live_status_updates_on_htmx_error():
    """Live status text should change when HTMX errors relate to the live delta route."""
    script = r"""
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const src = fs.readFileSync(path.join('backend','web','static','js','gustav.js'), 'utf8');

const sandbox = {
  console,
  setTimeout: (fn, ms) => 0,
  clearTimeout: () => {},
};

sandbox.document = {
  readyState: 'loading',
  addEventListener: () => {},
};
sandbox.window = sandbox;
sandbox.document.body = { addEventListener: () => {} };

const statusEl = {
  textContent: 'Letzte Aktualisierung: 12:00:00',
  classList: { added: [], add(name) { this.added.push(name); } }
};

sandbox.document.getElementById = (id) => {
  if (id === 'live-status') return statusEl;
  return null;
};

vm.runInNewContext(src, sandbox);
const gustav = sandbox.window.gustav;

// Simulate an HTMX responseError event coming from the live delta route.
const evt = {
  detail: {
    elt: { closest: (sel) => (sel === '#live-section' ? {} : null) },
    pathInfo: { requestPath: '/teaching/courses/1/units/1/live/matrix/delta' }
  }
};

gustav.updateLiveStatusForError(evt, 'Live-Ansicht: Verbindung unterbrochen.');

const result = {
  text: statusEl.textContent,
  classes: statusEl.classList.added
};

console.log(JSON.stringify(result));
    """
    data = _run_node(script)
    assert data["text"] == "Live-Ansicht: Verbindung unterbrochen."
    assert "text-danger" in data["classes"]


def test_teaching_live_status_clears_error_on_success():
    """Live status should clear error styling when a valid cursor update arrives."""
    script = r"""
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const src = fs.readFileSync(path.join('backend','web','static','js','gustav.js'), 'utf8');

const sandbox = {
  console,
  setTimeout: (fn, ms) => 0,
  clearTimeout: () => {},
};

sandbox.document = {
  readyState: 'loading',
  addEventListener: () => {},
};
sandbox.window = sandbox;
sandbox.document.body = { addEventListener: () => {} };

const statusEl = {
  attrs: { 'data-updated-since': '2025-01-02T03:04:05.000000+00:00' },
  textContent: 'Live-Ansicht: Verbindung unterbrochen.',
  classList: {
    classes: new Set(['text-danger']),
    add(name) { this.classes.add(name); },
    remove(name) { this.classes.delete(name); },
    has(name) { return this.classes.has(name); }
  },
  setAttribute(name, value) { this.attrs[name] = value; },
  getAttribute(name) { return this.attrs[name]; }
};

const sectionEl = {
  attrs: {},
  setAttribute(name, value) { this.attrs[name] = value; },
  getAttribute(name) { return this.attrs[name]; }
};

sandbox.document.getElementById = (id) => {
  if (id === 'live-status') return statusEl;
  if (id === 'live-section') return sectionEl;
  return null;
};

vm.runInNewContext(src, sandbox);
const gustav = sandbox.window.gustav;

// Initial polling binds the event listener and normalises the label.
gustav.initTeachingLivePolling();

// Simulate a successful cursor update after an earlier error.
const evt = { detail: { cursor: '2025-01-02T03:05:06.000000+00:00' } };
gustav.updateLiveStatusTimestamp(statusEl, evt.detail.cursor);

const result = {
  text: statusEl.textContent,
  hasDanger: statusEl.classList.has('text-danger')
};

console.log(JSON.stringify(result));
    """
    data = _run_node(script)
    assert data["text"].startswith("Letzte Aktualisierung:")
    assert data["hasDanger"] is False
