/**
 * H5P Task Review Player (Teacher UI)
 *
 * Why:
 * - In the Teacher Live matrix detail pane we want to show the student's latest
 *   H5P state so the teacher can see the chosen solution and mistakes.
 *
 * How:
 * - Embed Lumi's `<h5p-player>` webcomponent.
 * - Load the player model via `/h5p/player/review` (cookie-auth).
 * - Pass a short-lived encrypted review credential in the Authorization header.
 *
 * Security:
 * - Strict read-only: always requests `read_only_state=true`.
 * - Does not persist attempts or trigger writes from the browser side.
 */

(() => {
  const initAll = (contextEl) => {
    const scope = contextEl || document;
    scope.querySelectorAll('[data-h5p-task-review-player="true"]').forEach((root) => initOne(root));
  };

  const initOne = (root) => {
    if (!root || !(root instanceof Element)) return;
    const state = root.dataset.gustavH5pReviewInit || '';
    if (state === 'ready') return;
    root.dataset.gustavH5pReviewInit = 'ready';
    start(root);
  };

  const start = (root) => {
    const taskId = root.dataset.taskId || '';
    const contentId = root.dataset.contentId || '';
    const reviewToken = root.dataset.reviewToken || '';

    const statusEl = root.querySelector('[data-h5p-status]');
    const setStatus = (msg) => {
      if (statusEl) statusEl.textContent = msg || '';
    };

    const run = async () => {
      if (!contentId) {
        setStatus('Kein H5P-Inhalt verknüpft.');
        return;
      }
      if (!reviewToken) {
        setStatus('H5P-Review ist nicht verfügbar.');
        return;
      }

      setStatus('Lade H5P…');
      const { defineElements } = await import('/h5p/webcomponents/index.js');
      defineElements(['h5p-player']);

      const existing = root.querySelector('#h5pReviewPlayer');
      const player = document.createElement('h5p-player');
      player.id = 'h5pReviewPlayer';
      player.setAttribute('content-id', contentId);
      if (taskId) player.setAttribute('context-id', taskId); // isolate user state per task instance

      player.loadContentCallback = async (contentIdArg, contextIdArg) => {
        const url = new URL('/h5p/player/review', window.location.origin);
        url.searchParams.set('content_id', contentIdArg);
        const stableContextId = taskId || contextIdArg;
        if (stableContextId) url.searchParams.set('context_id', stableContextId);
        url.searchParams.set('read_only_state', 'true');
        const r = await fetch(url.toString(), {
          credentials: 'include',
          headers: { Authorization: `Bearer ${reviewToken}` },
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);
        return data;
      };

      if (existing) existing.replaceWith(player);
      else root.appendChild(player);
      setStatus('Ready.');
    };

    run().catch((e) => setStatus(String(e?.message || e)));
  };

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
