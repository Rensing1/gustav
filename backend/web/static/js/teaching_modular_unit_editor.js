/*
Teacher UI — Modular unit visual editor

Goals:
  - Phases as columns, modules as nodes.
  - Click module -> HTMX loads right-side panel.
  - Drag&drop reorder + cross-phase move (blocked when edge rules would break).
  - Show dependencies (edges) as an SVG overlay.
  - Resizable right panel (persist width in localStorage).
*/

(function () {
  function parseEdges(root) {
    var el = root.querySelector('#modular-editor-edges-data');
    if (!el) return [];
    try {
      var raw = (el.textContent || '').trim();
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function setupPanelResize(root) {
    var splitter = root.querySelector('#modular-editor-splitter');
    var panel = root.querySelector('#modular-editor-panel');
    if (!splitter || !panel) return;

    var storageKey = 'gustav.teaching.modularEditor.panelWidthPx';
    var saved = parseInt(localStorage.getItem(storageKey) || '', 10);
    if (!isNaN(saved) && saved > 200) {
      root.style.setProperty('--modular-editor-panel-width', saved + 'px');
    }

    var startX = 0;
    var startWidth = 0;
    var dragging = false;

    function onMove(ev) {
      if (!dragging) return;
      var dx = ev.clientX - startX;
      var next = clamp(startWidth - dx, 320, Math.floor(window.innerWidth * 0.8));
      root.style.setProperty('--modular-editor-panel-width', next + 'px');
    }

    function onUp() {
      if (!dragging) return;
      dragging = false;
      document.body.style.cursor = '';
      var current = parseInt(getComputedStyle(panel).width || '', 10);
      if (!isNaN(current)) localStorage.setItem(storageKey, String(current));
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    }

    splitter.addEventListener('pointerdown', function (ev) {
      dragging = true;
      startX = ev.clientX;
      startWidth = panel.getBoundingClientRect().width;
      document.body.style.cursor = 'col-resize';
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    });
  }

  function setupEdgesOverlay(root) {
    var graph = root.querySelector('#modular-editor-graph');
    var svg = root.querySelector('#modular-editor-edges');
    if (!graph || !svg) return { draw: function () {} };

    var edges = parseEdges(root);

    function ensureDefs() {
      if (svg.querySelector('defs')) return;
      svg.insertAdjacentHTML(
        'afterbegin',
        '<defs>' +
          '<marker id="modular-editor-arrow" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">' +
            '<polygon points="0 0, 10 3.5, 0 7" />' +
          '</marker>' +
        '</defs>'
      );
    }

    function nodeCenter(moduleId) {
      var node = root.querySelector('[data-module-id="' + moduleId + '"]');
      if (!node) return null;
      var graphRect = graph.getBoundingClientRect();
      var nodeRect = node.getBoundingClientRect();
      var left = nodeRect.left - graphRect.left + graph.scrollLeft;
      var top = nodeRect.top - graphRect.top + graph.scrollTop;
      return {
        x: left + nodeRect.width / 2,
        y: top + nodeRect.height / 2,
        w: nodeRect.width,
        h: nodeRect.height
      };
    }

    function draw() {
      ensureDefs();
      // Match SVG to the scrollable content size so edges align while scrolling.
      svg.setAttribute('width', String(graph.scrollWidth));
      svg.setAttribute('height', String(graph.scrollHeight));
      svg.setAttribute('viewBox', '0 0 ' + graph.scrollWidth + ' ' + graph.scrollHeight);

      // Remove old paths (keep <defs>).
      Array.from(svg.querySelectorAll('path.modular-editor__edge')).forEach(function (p) { p.remove(); });

      edges.forEach(function (e) {
        var fromId = e.from;
        var toId = e.to;
        if (!fromId || !toId) return;
        var a = nodeCenter(fromId);
        var b = nodeCenter(toId);
        if (!a || !b) return;

        // Start at right-center, end at left-center.
        var x1 = a.x + a.w / 2;
        var y1 = a.y;
        var x2 = b.x - b.w / 2;
        var y2 = b.y;
        var c1x = x1 + 60;
        var c1y = y1;
        var c2x = x2 - 60;
        var c2y = y2;
        var d = 'M ' + x1 + ' ' + y1 + ' C ' + c1x + ' ' + c1y + ', ' + c2x + ' ' + c2y + ', ' + x2 + ' ' + y2;

        var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', d);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke', 'rgba(163, 217, 106, 0.65)');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('marker-end', 'url(#modular-editor-arrow)');
        path.setAttribute('class', 'modular-editor__edge');
        svg.appendChild(path);
      });
    }

    // Keep edges aligned on resize and scroll.
    graph.addEventListener('scroll', function () { draw(); });
    window.addEventListener('resize', function () { draw(); });

    return { draw: draw, getEdges: function () { return edges; }, setEdges: function (next) { edges = next || []; } };
  }

  function setupEditorActions(root, edgeOverlay) {
    var unitId = root.getAttribute('data-unit-id') || '';
    if (!unitId) return;
    var statusEl = root.querySelector('#modular-editor-status small');

    function apiFetch(path, body) {
      return fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(body || {})
      });
    }

    // Create phase (reload on success).
    var btnAddPhase = root.querySelector('[data-action="modular-editor-add-phase"]');
    if (btnAddPhase) {
      btnAddPhase.addEventListener('click', function () {
        var title = window.prompt('Titel der Phase:', 'Neue Phase');
        if (!title) return;
        apiFetch('/api/teaching/units/' + unitId + '/phases', { title: title })
          .then(function (r) { if (r.ok) window.location.reload(); else r.text().then(function (t) { window.alert(t || 'Fehler'); }); })
          .catch(function (e) { window.alert('Fehler: ' + e); });
      });
    }

    // Create module in a phase (reload on success).
    Array.from(root.querySelectorAll('[data-action="modular-editor-add-module"]')).forEach(function (btn) {
      btn.addEventListener('click', function () {
        var phaseId = btn.getAttribute('data-phase-id') || '';
        var title = window.prompt('Titel des Moduls:', 'Neues Modul');
        if (!title || !phaseId) return;
        apiFetch('/api/teaching/units/' + unitId + '/modules', { title: title, phase_id: phaseId })
          .then(function (r) { if (r.ok) window.location.reload(); else r.text().then(function (t) { window.alert(t || 'Fehler'); }); })
          .catch(function (e) { window.alert('Fehler: ' + e); });
      });
    });

    // Edge mode: click source then target.
    var edgeModeBtn = root.querySelector('[data-action="modular-editor-edge-mode"]');
    var edgeMode = false;
    var edgeFrom = null;

    function clearEdgeSelection() {
      edgeFrom = null;
      Array.from(root.querySelectorAll('.modular-editor__module-node.is-edge-source')).forEach(function (n) {
        n.classList.remove('is-edge-source');
      });
      if (statusEl && edgeMode) statusEl.textContent = 'Kantenmodus: Quelle wählen…';
    }

    function setEdgeMode(enabled) {
      edgeMode = !!enabled;
      clearEdgeSelection();
      if (edgeModeBtn) edgeModeBtn.setAttribute('aria-pressed', edgeMode ? 'true' : 'false');
      if (statusEl) statusEl.textContent = edgeMode ? 'Kantenmodus: Quelle wählen…' : '';
    }

    if (edgeModeBtn) {
      edgeModeBtn.addEventListener('click', function () {
        setEdgeMode(!edgeMode);
      });
    }

    window.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') clearEdgeSelection();
    });

    // Intercept module clicks in edge mode.
    root.addEventListener('click', function (ev) {
      if (!edgeMode) return;
      var btn = ev.target && ev.target.closest ? ev.target.closest('.modular-editor__module-btn') : null;
      if (!btn) return;
      var node = btn.closest('.modular-editor__module-node');
      if (!node) return;
      var moduleId = node.getAttribute('data-module-id');
      if (!moduleId) return;

      ev.preventDefault();
      ev.stopPropagation();

      if (!edgeFrom) {
        edgeFrom = moduleId;
        node.classList.add('is-edge-source');
        if (statusEl) statusEl.textContent = 'Kantenmodus: Ziel wählen…';
        return;
      }

      var fromId = edgeFrom;
      var toId = moduleId;
      clearEdgeSelection();

      apiFetch('/api/teaching/units/' + unitId + '/modules/edges', { from_module_id: fromId, to_module_id: toId })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (j) { throw j; });
          return r.json();
        })
        .then(function (edge) {
          var next = edgeOverlay.getEdges().slice();
          next.push(edge);
          edgeOverlay.setEdges(next);
          edgeOverlay.draw();
          if (statusEl) statusEl.textContent = 'Kante erstellt.';
        })
        .catch(function (e) {
          var detail = (e && e.detail) ? e.detail : '';
          window.alert(detail === 'edge_constraint_violation' ? 'Ungültige Kante (Regel verletzt).' : 'Kante konnte nicht erstellt werden.');
          if (statusEl) statusEl.textContent = '';
        });
    }, true);

    // Delete edge buttons inside the right-side panel.
    root.addEventListener('click', function (ev) {
      var btn = ev.target && ev.target.closest ? ev.target.closest('[data-action="modular-editor-delete-edge"]') : null;
      if (!btn) return;
      ev.preventDefault();
      var fromId = btn.getAttribute('data-from') || '';
      var toId = btn.getAttribute('data-to') || '';
      if (!fromId || !toId) return;

      fetch('/api/teaching/units/' + unitId + '/modules/edges', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ from_module_id: fromId, to_module_id: toId })
      }).then(function (r) {
        if (!r.ok) throw r;
      }).then(function () {
        // Keep the graph consistent without a full reload.
        var next = edgeOverlay.getEdges().filter(function (e) {
          return !(e && e.from === fromId && e.to === toId);
        });
        edgeOverlay.setEdges(next);
        edgeOverlay.draw();

        // Refresh the panel to update its dependency lists.
        var panelContent = root.querySelector('#modular-editor-panel .modular-editor-panel__content');
        var moduleId = panelContent ? panelContent.getAttribute('data-module-id') : '';
        if (moduleId && typeof htmx !== 'undefined' && htmx.ajax) {
          htmx.ajax('GET', '/units/' + unitId + '/modules/' + moduleId + '/panel', '#modular-editor-panel');
        }
      }).catch(function () {
        window.alert('Kante konnte nicht entfernt werden.');
      });
    });
  }

  function setupDragAndDrop(root, edgeOverlay) {
    if (typeof Sortable === 'undefined') return;
    var lists = Array.from(root.querySelectorAll('.modular-editor__module-list'));
    if (!lists.length) return;

    function moduleIds(listEl) {
      return Array.from(listEl.querySelectorAll('.modular-editor__module-node'))
        .map(function (n) { return n.getAttribute('data-module-id'); })
        .filter(Boolean);
    }

    lists.forEach(function (listEl) {
      try {
        new Sortable(listEl, {
          group: 'modular-editor-modules',
          animation: 150,
          handle: '.modular-editor__drag-handle',
          draggable: '.modular-editor__module-node',
          onEnd: function (evt) {
            var unitId = listEl.getAttribute('data-unit-id') || '';
            var phaseId = evt.to && evt.to.getAttribute ? (evt.to.getAttribute('data-phase-id') || '') : '';
            if (!unitId || !phaseId) return;

            var ids = moduleIds(evt.to);
            fetch('/api/teaching/units/' + unitId + '/phases/' + phaseId + '/modules/reorder', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'same-origin',
              body: JSON.stringify({ module_ids: ids })
            }).then(function (r) {
              if (!r.ok) return r.json().then(function (j) { throw j; });
              return r.json();
            }).then(function () {
              // Redraw edges since node positions may have changed.
              edgeOverlay.draw();
            }).catch(function (e) {
              var detail = (e && e.detail) ? e.detail : '';
              window.alert(detail === 'edge_constraint_violation' ? 'Verschieben blockiert: Abhängigkeiten zuerst entfernen.' : 'Verschieben fehlgeschlagen.');
              window.location.reload();
            });
          }
        });
      } catch (e) {
        // Keep UI usable even when Sortable fails to init.
      }
    });
  }

  function init(root) {
    if (root.dataset.modularEditorReady === 'true') return;
    root.dataset.modularEditorReady = 'true';
    setupPanelResize(root);
    var edgeOverlay = setupEdgesOverlay(root);
    setupEditorActions(root, edgeOverlay);
    setupDragAndDrop(root, edgeOverlay);
    edgeOverlay.draw();

    // Redraw after HTMX swaps (e.g., panel content load).
    document.body && document.body.addEventListener('htmx:afterSwap', function () { edgeOverlay.draw(); });
  }

  function boot() {
    var root = document.querySelector('.modular-editor[data-unit-id]');
    if (root) init(root);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // When the app navigates via HTMX (main content swaps), the editor markup
  // can appear after the initial page load. Ensure the editor initializes.
  document.body && document.body.addEventListener && document.body.addEventListener('htmx:load', function (evt) {
    var scope = (evt && evt.detail && evt.detail.elt) ? evt.detail.elt : document;
    try {
      var root = scope.querySelector ? scope.querySelector('.modular-editor[data-unit-id]') : null;
      if (root) init(root);
    } catch (e) {
      // no-op
    }
  });
})();
