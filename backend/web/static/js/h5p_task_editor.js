/**
 * H5P Task Editor (Teacher UI)
 *
 * Why:
 * - For `Task.kind="h5p"` we embed Lumi's `<h5p-editor>` webcomponent directly
 *   into the normal GUSTAV task detail page (no iframe, no separate editor page).
 *
 * How:
 * - Load webcomponents from `/h5p/webcomponents/*` (served by the h5p service via proxy).
 * - Use `/h5p/editor/model` to fetch the editor "model" (H5PIntegration + scripts/styles).
 * - Use `/h5p/contents` to create/update content and receive an opaque `content_id`.
 * - Patch the GUSTAV task (`/api/teaching/.../tasks/{task_id}`) to store that `content_id`.
 */

(() => {
  /**
   * Initialize all embedded H5P editors in a given DOM subtree.
   *
   * Notes about robustness:
   * - GUSTAV uses HTMX navigation in parts of the UI (hx-push-url). That means
   *   pages can be swapped into `#main-content` without a full page reload.
   * - The Lumi `<h5p-editor>` component appends its template in `connectedCallback()`
   *   without checking for previous runs. If an element instance ever gets
   *   reconnected, this can lead to duplicated UI.
   *
   * Strategy:
   * - For every editor container we replace any existing `<h5p-editor>` node with
   *   a fresh one and then wire callbacks. This avoids stale component state.
   */

  const initAll = (contextEl) => {
    const scope = contextEl || document;
    scope.querySelectorAll('[data-h5p-task-editor="true"]').forEach((root) => {
      initOne(root);
    });
  };

  const initOne = (root) => {
    if (!root || !(root instanceof Element)) return;

    // Avoid double-binding if this module is executed again (e.g. via HTMX script processing).
    const state = root.dataset.gustavH5pEditorInit || '';
    if (state === 'ready' || state === 'pending') return;

    // On the task-create page the H5P block is present but hidden until the
    // teacher selects "H5P". We defer initialization in that case to avoid
    // loading large webcomponent bundles unnecessarily.
    const kindSelect = document.getElementById('task_kind');
    const hiddenAncestor = root.closest('[hidden]');
    if (hiddenAncestor && kindSelect && (kindSelect.value || 'native') !== 'h5p') {
      root.dataset.gustavH5pEditorInit = 'pending';
      kindSelect.addEventListener('change', () => {
        if ((kindSelect.value || 'native') === 'h5p') {
          // Ensure we only ever start once.
          if (root.dataset.gustavH5pEditorInit === 'ready') return;
          root.dataset.gustavH5pEditorInit = 'ready';
          start(root);
        }
      }, { once: true });
      return;
    }

    root.dataset.gustavH5pEditorInit = 'ready';
    start(root);
  };

  const start = (root) => {
    const unitId = root.dataset.unitId || '';
    const sectionId = root.dataset.sectionId || '';
    const taskId = root.dataset.taskId || '';
    const initialContentId = root.dataset.contentId || '';

    const statusEl = root.querySelector('#h5pStatus');
    const contentIdInput = root.querySelector('#h5pContentId');
    const btnNew = root.querySelector('#h5pNew');
    const btnLoad = root.querySelector('#h5pLoad');
    const btnSave = root.querySelector('#h5pSave');

    const hiddenContentIdInput =
      root.querySelector('input[name="h5p_content_id"]') ||
      root.closest('form')?.querySelector('input[name="h5p_content_id"]') ||
      null;

    const setStatus = (msg) => {
      if (!statusEl) return;
      statusEl.textContent = msg || '';
    };

    const setHiddenContentId = (cid) => {
      if (!hiddenContentIdInput) return;
      hiddenContentIdInput.value = cid || '';
    };

    const ensureNoDuplicateTemplates = (editorEl) => {
      if (!editorEl) return;
      const roots = editorEl.querySelectorAll('.h5p-editor-component-root');
      if (roots.length <= 1) return;
      // Keep the first root: the component uses `querySelector(...)` internally and
      // will operate on the first match.
      for (let i = 1; i < roots.length; i++) {
        roots[i].remove();
      }
    };

    const patchTaskContentId = async (contentId) => {
      if (!unitId || !sectionId || !taskId) return;
      const url = `/api/teaching/units/${encodeURIComponent(unitId)}/sections/${encodeURIComponent(sectionId)}/tasks/${encodeURIComponent(taskId)}`;
      const r = await fetch(url, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ h5p: { content_id: contentId, display_options: {} } }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data?.detail || data?.error || `HTTP ${r.status}`);
      }
    };

    const run = async () => {
      if (!contentIdInput || !btnNew || !btnLoad || !btnSave) {
        setStatus('Editor UI is incomplete (missing DOM elements).');
        return;
      }

      setStatus('Loading H5P webcomponents…');
      const { defineElements } = await import('/h5p/webcomponents/index.js');
      defineElements(['h5p-editor']);

      const loadContentCallback = async (contentId) => {
        const url = new URL('/h5p/editor/model', window.location.origin);
        if (contentId && contentId !== 'new') url.searchParams.set('content_id', contentId);
        const r = await fetch(url.toString(), { credentials: 'include' });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);
        return data;
      };

      const saveContentCallback = async (contentId, requestBody) => {
        const isUpdate = Boolean(contentId && contentId !== 'new');
        const url = isUpdate ? `/h5p/contents/${encodeURIComponent(contentId)}` : '/h5p/contents';
        const method = isUpdate ? 'PATCH' : 'POST';
        const r = await fetch(url, {
          method,
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);
        return { contentId: data.content_id, metadata: data.metadata };
      };

      let editor = null;
      const installEditor = (cid) => {
        const existing = root.querySelector('#h5pEditor');
        const newEl = document.createElement('h5p-editor');
        newEl.id = 'h5pEditor';
        newEl.setAttribute('content-id', cid || 'new');
        if (existing) {
          existing.replaceWith(newEl);
        } else {
          root.appendChild(newEl);
        }

        // Wire callbacks *after* the element is connected so the component can render safely.
        newEl.loadContentCallback = loadContentCallback;
        newEl.saveContentCallback = saveContentCallback;
        newEl.addEventListener('editorloaded', (ev) => {
          ensureNoDuplicateTemplates(newEl);
          setStatus(`Editor loaded (${ev?.detail?.ubername || 'unknown library'}).`);
        });

        editor = newEl;
        ensureNoDuplicateTemplates(editor);
      };

      const startContentId = initialContentId || 'new';
      contentIdInput.value = initialContentId || '';
      setHiddenContentId(initialContentId || '');
      installEditor(startContentId);

      btnNew.addEventListener('click', () => {
        contentIdInput.value = '';
        setHiddenContentId('');
        installEditor('new');
        setStatus('Creating new content…');
      });

      btnLoad.addEventListener('click', () => {
        const cid = (contentIdInput.value || '').trim();
        if (!cid) {
          setStatus('Bitte zuerst eine Content ID eingeben.');
          return;
        }
        setHiddenContentId(cid);
        installEditor(cid);
        setStatus(`Loading content ${cid}…`);
      });

      btnSave.addEventListener('click', async () => {
        try {
          if (!editor) {
            setStatus('Editor not ready.');
            return;
          }
          setStatus('Saving…');
          const saved = await editor.save();
          if (saved?.contentId) {
            contentIdInput.value = saved.contentId;
            setHiddenContentId(saved.contentId);
            if (taskId) await patchTaskContentId(saved.contentId);
            setStatus(`Saved. Content ID: ${saved.contentId}`);
          } else {
            setStatus('Saved.');
          }
        } catch (e) {
          setStatus(String(e?.message || e));
        }
      });

      setStatus('Ready.');
    };

    run().catch((e) => {
      setStatus('Init failed: ' + String(e?.message || e));
    });
  };

  // Initial page load (full navigation).
  initAll(document);

  // HTMX swaps: init in the swapped subtree.
  document.body?.addEventListener('htmx:afterSwap', (ev) => {
    const target = ev?.detail?.target;
    initAll(target || document);
  });

  // HTMX history restore (back/forward).
  document.body?.addEventListener('htmx:restored', () => {
    initAll(document);
  });
})();
