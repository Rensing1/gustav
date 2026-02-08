/*
Teacher UI — Modular unit visual editor

Goals:
  - Phases as bands (stacked vertically), modules as nodes.
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

  function getCsrfToken(root) {
    return (root && root.dataset && root.dataset.csrfToken) ? root.dataset.csrfToken : '';
  }

  function setupPanelResize(root) {
    if (root.dataset.modularEditorPanelResizeReady === 'true') return;
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

    root.dataset.modularEditorPanelResizeReady = 'true';
  }

  function setupEdgesOverlay(root) {
    var graph = root.querySelector('#modular-editor-graph');
    var svg = root.querySelector('#modular-editor-edges');
    if (!graph || !svg) return null;

    var edges = parseEdges(root);
    var drawScheduled = false;

    function ensureDefs() {
      if (svg.querySelector('defs')) return;
      // Student-like arrow marker (inherits stroke color via `context-stroke`).
      svg.insertAdjacentHTML(
        'afterbegin',
        '<defs>' +
          '<marker id="modular-editor-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse">' +
            '<path d="M 0 0 L 10 5 L 0 10 z" class="modular-editor__edge-arrow" />' +
          '</marker>' +
        '</defs>'
      );
    }

    function laneOffset(laneIndex, gap) {
      var idx = Number(laneIndex || 0);
      var g = Number(gap || 0);
      if (!(idx > 0) || !(g > 0)) return 0;
      var n = Math.floor((idx + 1) / 2);
      return (idx % 2 ? 1 : -1) * n * g;
    }

    function intersectRectBoundary(center, toward, halfW, halfH) {
      var cx = Number(center.x || 0);
      var cy = Number(center.y || 0);
      var dx = Number(toward.x || 0) - cx;
      var dy = Number(toward.y || 0) - cy;
      if (!(halfW > 0) || !(halfH > 0)) return { x: cx, y: cy };
      if (!(dx || dy)) return { x: cx, y: cy };
      var tx = dx === 0 ? Infinity : (halfW / Math.abs(dx));
      var ty = dy === 0 ? Infinity : (halfH / Math.abs(dy));
      var t = Math.min(tx, ty);
      return { x: cx + dx * t, y: cy + dy * t };
    }

    function edgeEndpoints(a, b) {
      var c1 = { x: a.x, y: a.y };
      var c2 = { x: b.x, y: b.y };
      var p1 = intersectRectBoundary(c1, c2, a.w / 2, a.h / 2);
      var p2 = intersectRectBoundary(c2, c1, b.w / 2, b.h / 2);
      return { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y };
    }

    function nodeInfo(moduleId) {
      var node = root.querySelector('[data-module-id="' + moduleId + '"]');
      if (!node) return null;
      var graphRect = graph.getBoundingClientRect();
      var nodeRect = node.getBoundingClientRect();
      var left = nodeRect.left - graphRect.left + graph.scrollLeft;
      var top = nodeRect.top - graphRect.top + graph.scrollTop;
      var phaseEl = node.closest ? node.closest('.modular-editor__phase') : null;
      var phaseId = phaseEl && phaseEl.getAttribute ? (phaseEl.getAttribute('data-phase-id') || '') : '';
      return {
        x: left + nodeRect.width / 2,
        y: top + nodeRect.height / 2,
        w: nodeRect.width,
        h: nodeRect.height,
        phaseId: phaseId
      };
    }

    function scheduleDraw() {
      if (drawScheduled) return;
      drawScheduled = true;
      window.requestAnimationFrame(function () {
        drawScheduled = false;
        drawNow();
      });
    }

    function drawNow() {
      ensureDefs();
      // Match SVG to the scrollable content size so edges align while scrolling.
      svg.setAttribute('width', String(graph.scrollWidth));
      svg.setAttribute('height', String(graph.scrollHeight));
      svg.setAttribute('viewBox', '0 0 ' + graph.scrollWidth + ' ' + graph.scrollHeight);

      // Remove old edge elements (keep <defs>).
      Array.from(svg.querySelectorAll('.modular-editor__edge')).forEach(function (p) { p.remove(); });

      var expanded = [];
      var cache = {};

      function getNode(mid) {
        if (cache[mid]) return cache[mid];
        var info = nodeInfo(mid);
        cache[mid] = info;
        return info;
      }

      edges.forEach(function (e) {
        var fromId = e.from;
        var toId = e.to;
        if (!fromId || !toId) return;
        var a = getNode(fromId);
        var b = getNode(toId);
        if (!a || !b) return;
        var samePhase = !!(a.phaseId && b.phaseId && a.phaseId === b.phaseId);
        expanded.push({ from: String(fromId), to: String(toId), a: a, b: b, samePhase: samePhase });
      });

      // Group edges so lane offsets stay local (more predictable).
      var groups = {};
      expanded.forEach(function (ed) {
        var key = ed.samePhase
          ? ('same:' + String(ed.a.phaseId || ''))
          : ('cross:' + String(ed.a.phaseId || '') + '>' + String(ed.b.phaseId || ''));
        if (!groups[key]) groups[key] = [];
        groups[key].push(ed);
      });

      function cmp(a, b) {
        return a < b ? -1 : (a > b ? 1 : 0);
      }

      var LANE_GAP = 18;

      Object.keys(groups).forEach(function (key) {
        var list = groups[key] || [];
        list.sort(function (e1, e2) {
          var c = cmp(e1.a.y, e2.a.y);
          if (c) return c;
          c = cmp(e1.a.x, e2.a.x);
          if (c) return c;
          c = cmp(e1.b.y, e2.b.y);
          if (c) return c;
          c = cmp(e1.b.x, e2.b.x);
          if (c) return c;
          c = String(e1.from).localeCompare(String(e2.from));
          if (c) return c;
          return String(e1.to).localeCompare(String(e2.to));
        });

        list.forEach(function (ed, idx) {
          var off = laneOffset(idx, LANE_GAP);
          var offsetX = ed.samePhase ? 0 : off;
          var offsetY = ed.samePhase ? off : 0;

          var ep = edgeEndpoints(ed.a, ed.b);
          var x1 = ep.x1;
          var y1 = ep.y1;
          var x2 = ep.x2;
          var y2 = ep.y2;

          var dx = x2 - x1;
          var dy = y2 - y1;
          var adx = Math.abs(dx);
          var ady = Math.abs(dy);

          // Student-like smooth cubic curves (with lane offsets on control points).
          var d = 'M ' + x1 + ' ' + y1 + ' L ' + x2 + ' ' + y2;
          if (adx > 8 || ady > 8) {
            if (ady >= adx) {
              var signY = dy === 0 ? 1 : (dy > 0 ? 1 : -1);
              var cY = clamp(ady * 0.55, 36, 160) * signY;
              var cx1 = x1 + offsetX;
              var cx2 = x2 + offsetX;
              d = 'M ' + x1 + ' ' + y1 + ' C ' + cx1 + ' ' + (y1 + cY) + ' ' + cx2 + ' ' + (y2 - cY) + ' ' + x2 + ' ' + y2;
            } else {
              var signX = dx === 0 ? 1 : (dx > 0 ? 1 : -1);
              var cX = clamp(adx * 0.55, 36, 160) * signX;
              var cy1 = y1 + offsetY;
              var cy2 = y2 + offsetY;
              d = 'M ' + x1 + ' ' + y1 + ' C ' + (x1 + cX) + ' ' + cy1 + ' ' + (x2 - cX) + ' ' + cy2 + ' ' + x2 + ' ' + y2;
            }
          }

          var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('d', d);
          path.setAttribute('marker-end', 'url(#modular-editor-arrow)');
          path.setAttribute('class', 'modular-editor__edge');
          path.setAttribute('data-from', ed.from);
          path.setAttribute('data-to', ed.to);
          svg.appendChild(path);
        });
      });
    }

    // Keep edges aligned on resize and scroll (throttled).
    function onScroll() { scheduleDraw(); }
    function onResize() { scheduleDraw(); }
    graph.addEventListener('scroll', onScroll);
    window.addEventListener('resize', onResize);

    function destroy() {
      graph.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onResize);
    }

    return {
      draw: scheduleDraw,
      destroy: destroy,
      getEdges: function () { return edges; },
      setEdges: function (next) { edges = next || []; }
    };
  }


  function destroySortables(instances) {
    (instances || []).forEach(function (s) {
      try {
        if (s && typeof s.destroy === 'function') s.destroy();
      } catch (e) {
        // no-op
      }
    });
  }

  function revertSortableMove(evt) {
    try {
      if (!evt || !evt.item || !evt.from) return;
      var from = evt.from;
      var item = evt.item;
      var idx = (typeof evt.oldIndex === 'number') ? evt.oldIndex : null;
      // Remove from current parent first so `oldIndex` refers to the list
      // without the moved element (important for same-list moves).
      if (item.parentNode) item.parentNode.removeChild(item);
      var children = from.children || [];
      if (idx === null) {
        from.appendChild(item);
        return;
      }
      if (idx >= children.length) {
        from.appendChild(item);
        return;
      }
      from.insertBefore(item, children[idx]);
    } catch (e) {
      // no-op
    }
  }


  function flashAttention(el) {
    if (!el || !el.classList) return;
    var cls = 'is-attention';
    // Restart animation even if the class was already present.
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
    window.setTimeout(function () { el.classList.remove(cls); }, 950);
  }

  function setStatus(ctx, message, kind, ttlMs) {
    if (!ctx || !ctx.statusEl || !ctx.statusContainer) return;

    var msg = message || '';
    ctx.statusEl.textContent = msg;

    ctx.statusContainer.classList.remove('is-info', 'is-success', 'is-error');
    if (msg) ctx.statusContainer.classList.add('is-' + (kind || 'info'));

    if (ctx.statusTimer) {
      window.clearTimeout(ctx.statusTimer);
      ctx.statusTimer = null;
    }
    if (msg && typeof ttlMs === 'number' && ttlMs > 0) {
      ctx.statusTimer = window.setTimeout(function () {
        setStatus(ctx, '', 'info');
      }, ttlMs);
    }
  }

  function setupEditorActions(root, ctx) {
    if (root.dataset.modularEditorActionsReady === 'true') return;
    var unitId = root.getAttribute('data-unit-id') || '';
    if (!unitId) return;
    ctx.unitId = unitId;
    ctx.statusContainer = root.querySelector('#modular-editor-status');
    ctx.statusEl = ctx.statusContainer ? ctx.statusContainer.querySelector('small') : null;
    ctx.edgeModeBtn = root.querySelector('[data-action="modular-editor-edge-mode"]');

    function apiJson(method, path, body) {
      var headers = { 'Content-Type': 'application/json' };
      if (ctx.csrfToken) headers['X-CSRF-Token'] = ctx.csrfToken;
      return fetch(path, {
        method: method,
        headers: headers,
        credentials: 'same-origin',
        body: body ? JSON.stringify(body) : undefined
      });
    }

    function apiPost(path, body) { return apiJson('POST', path, body); }

    function clearEdgeSelection() {
      ctx.edgeFrom = null;
      Array.from(root.querySelectorAll('.modular-editor__module-node.is-edge-source')).forEach(function (n) {
        n.classList.remove('is-edge-source');
      });
      if (ctx.edgeMode) setStatus(ctx, 'Kantenmodus: Quelle wählen…', 'info');
    }

    function setEdgeMode(enabled) {
      ctx.edgeMode = !!enabled;
      clearEdgeSelection();
      if (ctx.edgeModeBtn) ctx.edgeModeBtn.setAttribute('aria-pressed', ctx.edgeMode ? 'true' : 'false');
      setStatus(ctx, ctx.edgeMode ? 'Kantenmodus: Quelle wählen…' : '', 'info');
    }

    if (ctx.edgeModeBtn) {
      ctx.edgeModeBtn.addEventListener('click', function () {
        setEdgeMode(!ctx.edgeMode);
      });
    }

    // Intercept module clicks in edge mode.
    root.addEventListener('click', function (ev) {
      if (!ctx.edgeMode) return;
      var node = ev.target && ev.target.closest ? ev.target.closest('.modular-editor__module-node') : null;
      if (!node) return;
      // Ignore actions/drag handle — edge mode should not interfere with CRUD or dragging.
      if (ev.target.closest && ev.target.closest('[data-action^="modular-editor-rename-"]')) return;
      if (ev.target.closest && ev.target.closest('[data-action^="modular-editor-delete-"]')) return;
      if (ev.target.closest && ev.target.closest('.modular-editor__drag-handle')) return;
      if (ev.target.closest && ev.target.closest('.modular-editor__node-inline')) return;
      if (ev.target.closest && ev.target.closest('.modular-editor__phase-inline')) return;
      var moduleId = node.getAttribute('data-module-id');
      if (!moduleId) return;

      ev.preventDefault();
      ev.stopPropagation();

      if (!ctx.edgeFrom) {
        ctx.edgeFrom = moduleId;
        node.classList.add('is-edge-source');
        setStatus(ctx, 'Kantenmodus: Ziel wählen…', 'info');
        return;
      }

      var fromId = ctx.edgeFrom;
      var toId = moduleId;
      clearEdgeSelection();

      apiPost('/api/teaching/units/' + unitId + '/modules/edges', { from_module_id: fromId, to_module_id: toId })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (j) { throw j; });
          return r.json();
        })
        .then(function (edge) {
          if (!ctx.edgeOverlay) return;
          var next = ctx.edgeOverlay.getEdges().slice();
          next.push(edge);
          ctx.edgeOverlay.setEdges(next);
          ctx.edgeOverlay.draw();
          setStatus(ctx, 'Kante erstellt.', 'success', 2500);
        })
        .catch(function (e) {
          var detail = (e && e.detail) ? e.detail : '';
          var msg = detail === 'edge_constraint_violation'
            ? 'Ungültige Kante (Regel verletzt).'
            : 'Kante konnte nicht erstellt werden.';
          setStatus(ctx, msg, 'error', 6000);
          flashAttention(root.querySelector('[data-module-id="' + fromId + '"]'));
          flashAttention(root.querySelector('[data-module-id="' + toId + '"]'));
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

      apiJson('DELETE', '/api/teaching/units/' + unitId + '/modules/edges', { from_module_id: fromId, to_module_id: toId })
      .then(function (r) {
        if (!r.ok) throw r;
      }).then(function () {
        // Keep the graph consistent without a full reload.
        if (!ctx.edgeOverlay) return;
        var next = ctx.edgeOverlay.getEdges().filter(function (e) {
          return !(e && e.from === fromId && e.to === toId);
        });
        ctx.edgeOverlay.setEdges(next);
        ctx.edgeOverlay.draw();

        // Refresh the panel to update its dependency lists.
        var panelContent = root.querySelector('#modular-editor-panel .modular-editor-panel__content');
        var moduleId = panelContent ? panelContent.getAttribute('data-module-id') : '';
        if (moduleId && typeof htmx !== 'undefined' && htmx.ajax) {
          htmx.ajax('GET', '/units/' + unitId + '/modules/' + moduleId + '/panel', '#modular-editor-panel');
        }
      }).catch(function () {
        setStatus(ctx, 'Kante konnte nicht entfernt werden.', 'error', 6000);
        flashAttention(root.querySelector('[data-module-id="' + fromId + '"]'));
        flashAttention(root.querySelector('[data-module-id="' + toId + '"]'));
      });
    });

    window.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') clearEdgeSelection();
    });

    root.dataset.modularEditorActionsReady = 'true';
  }

  function setupPhaseDragAndDrop(root, ctx) {
    if (typeof Sortable === 'undefined') return null;
    var phasesEl = root.querySelector('#modular-editor-phases');
    if (!phasesEl) return null;

    function phaseIds() {
      return Array.from(phasesEl.querySelectorAll('.modular-editor__phase'))
        .map(function (p) { return p.getAttribute('data-phase-id'); })
        .filter(Boolean);
    }

    try {
      return new Sortable(phasesEl, {
        animation: 150,
        direction: 'vertical',
        draggable: '.modular-editor__phase',
        handle: '.modular-editor__phase-drag-handle',
        filter: 'button, a, form, input, textarea, select',
        preventOnFilter: false,
        onEnd: function (evt) {
          var unitId = ctx.unitId || root.getAttribute('data-unit-id') || '';
          if (!unitId) return;

          var ids = phaseIds();
          var headers = { 'Content-Type': 'application/json' };
          if (ctx.csrfToken) headers['X-CSRF-Token'] = ctx.csrfToken;
          fetch('/api/teaching/units/' + unitId + '/phases/reorder', {
            method: 'POST',
            headers: headers,
            credentials: 'same-origin',
            body: JSON.stringify({ phase_ids: ids })
          }).then(function (r) {
            if (!r.ok) return r.json().then(function (j) { throw j; });
            return r.json();
          }).then(function () {
            setStatus(ctx, 'Phasen gespeichert.', 'success', 2000);
            if (ctx.edgeOverlay) ctx.edgeOverlay.draw();
          }).catch(function (e) {
            revertSortableMove(evt);
            var detail = (e && e.detail) ? e.detail : '';
            var msg = detail === 'edge_constraint_violation'
              ? 'Verschieben blockiert: Abhängigkeiten zuerst entfernen.'
              : 'Verschieben fehlgeschlagen.';
            setStatus(ctx, msg, 'error', 6000);
            flashAttention(evt && evt.item ? evt.item : null);
            if (ctx.edgeOverlay) ctx.edgeOverlay.draw();
          });
        }
      });
    } catch (e) {
      return null;
    }
  }

  function setupDragAndDrop(root, ctx) {
    if (typeof Sortable === 'undefined') return;
    var lists = Array.from(root.querySelectorAll('.modular-editor__module-list'));
    if (!lists.length) return;
    var out = [];

    function moduleIds(listEl) {
      return Array.from(listEl.querySelectorAll('.modular-editor__module-node'))
        .map(function (n) { return n.getAttribute('data-module-id'); })
        .filter(Boolean);
    }

    lists.forEach(function (listEl) {
      try {
        out.push(new Sortable(listEl, {
          group: 'modular-editor-modules',
          animation: 150,
          direction: 'horizontal',
          handle: '.modular-editor__drag-handle',
          draggable: '.modular-editor__module-node',
          onEnd: function (evt) {
            var unitId = listEl.getAttribute('data-unit-id') || '';
            var phaseId = evt.to && evt.to.getAttribute ? (evt.to.getAttribute('data-phase-id') || '') : '';
            if (!unitId || !phaseId) return;

            var ids = moduleIds(evt.to);
            var headers = { 'Content-Type': 'application/json' };
            if (ctx.csrfToken) headers['X-CSRF-Token'] = ctx.csrfToken;
            fetch('/api/teaching/units/' + unitId + '/phases/' + phaseId + '/modules/reorder', {
              method: 'POST',
              headers: headers,
              credentials: 'same-origin',
              body: JSON.stringify({ module_ids: ids })
            }).then(function (r) {
              if (!r.ok) return r.json().then(function (j) { throw j; });
              return r.json();
            }).then(function () {
              // Redraw edges since node positions may have changed.
              if (ctx.edgeOverlay) ctx.edgeOverlay.draw();
              setStatus(ctx, '', 'info');
            }).catch(function (e) {
              revertSortableMove(evt);
              var detail = (e && e.detail) ? e.detail : '';
              var msg = detail === 'edge_constraint_violation'
                ? 'Verschieben blockiert: Abhängigkeiten zuerst entfernen.'
                : 'Verschieben fehlgeschlagen.';
              setStatus(ctx, msg, 'error', 6000);
              flashAttention(evt && evt.item ? evt.item : null);
              flashAttention(evt && evt.to && evt.to.closest ? evt.to.closest('.modular-editor__phase') : null);
              if (ctx.edgeOverlay) ctx.edgeOverlay.draw();
            });
          }
        }));
      } catch (e) {
        // Keep UI usable even when Sortable fails to init.
      }
    });

    ctx.sortables = out;
  }

  function refreshGraphBindings(root, ctx) {
    if (ctx.phaseSortable && typeof ctx.phaseSortable.destroy === 'function') ctx.phaseSortable.destroy();
    ctx.phaseSortable = null;
    if (ctx.edgeOverlay && typeof ctx.edgeOverlay.destroy === 'function') ctx.edgeOverlay.destroy();
    destroySortables(ctx.sortables);
    ctx.sortables = [];
    ctx.csrfToken = getCsrfToken(root);
    ctx.edgeOverlay = setupEdgesOverlay(root);
    ctx.phaseSortable = setupPhaseDragAndDrop(root, ctx);
    setupDragAndDrop(root, ctx);
    // If the graph was replaced, any in-progress edge selection is invalid.
    ctx.edgeFrom = null;
    Array.from(root.querySelectorAll('.modular-editor__module-node.is-edge-source')).forEach(function (n) {
      n.classList.remove('is-edge-source');
    });
    if (ctx.edgeMode) setStatus(ctx, 'Kantenmodus: Quelle wählen…', 'info');
    if (ctx.edgeOverlay) {
      window.requestAnimationFrame(function () { ctx.edgeOverlay.draw(); });
    }
  }

  function boot() {
    var root = document.querySelector('.modular-editor[data-unit-id]');
    if (!root) return;
    var ctx = root.__modularEditorCtx || { edgeMode: false, edgeFrom: null, edgeOverlay: null, sortables: [], phaseSortable: null, csrfToken: '' };
    root.__modularEditorCtx = ctx;
    ctx.csrfToken = getCsrfToken(root);
    setupPanelResize(root);
    setupEditorActions(root, ctx);
    if (!ctx.edgeOverlay) {
      refreshGraphBindings(root, ctx);
    } else {
      window.requestAnimationFrame(function () { ctx.edgeOverlay.draw(); });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // When the app navigates via HTMX (main content swaps), the editor markup can
  // appear after the initial page load. Ensure the editor initializes.
  document.body && document.body.addEventListener && document.body.addEventListener('htmx:load', function () {
    boot();
  });

  // When HTMX replaces the graph container out-of-band, our edge overlay and
  // Sortable instances must be re-initialized to point at the new DOM nodes.
  function onHtmxSwap(evt) {
    var root = document.querySelector('.modular-editor[data-unit-id]');
    if (!root || !root.__modularEditorCtx) return;
    var ctx = root.__modularEditorCtx;
    var elt = evt && evt.detail && evt.detail.elt ? evt.detail.elt : null;
    if (elt && elt.id === 'modular-editor-graph') {
      refreshGraphBindings(root, ctx);
      return;
    }
    // For non-graph swaps (e.g., right panel), just redraw edges because the
    // canvas layout may have shifted.
    if (ctx.edgeOverlay) window.requestAnimationFrame(function () { ctx.edgeOverlay.draw(); });
  }

  document.body && document.body.addEventListener && document.body.addEventListener('htmx:afterSwap', onHtmxSwap);
  document.body && document.body.addEventListener && document.body.addEventListener('htmx:oobAfterSwap', onHtmxSwap);
})();
