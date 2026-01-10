/**
 * H5P Task Player (Student UI)
 *
 * Why:
 * - For `Task.kind="h5p"` students should solve the task directly inside the
 *   GUSTAV page (no iframe, no separate H5P page).
 * - We persist scored attempts so teachers can track progress:
 *   - attempted = at least one attempt exists
 *   - correct_completed = full score (raw == max)
 *
 * How (MVP):
 * - Embed Lumi's `<h5p-player>` webcomponent.
 * - Fetch the player model from `/h5p/player/model` (cookie-auth; fail-closed).
 * - Listen to `xAPI` events and POST scored attempts to
 *   `/api/learning/courses/{course_id}/tasks/{task_id}/submissions` with `kind=h5p`.
 *
 * Security:
 * - Uses same-origin `fetch(..., credentials: 'include')` for both model load and submission.
 * - The H5P service validates the `gustav_session` cookie and (for students)
 *   checks that the `content_id` belongs to a released H5P task in the given course.
 */

(() => {
  const initAll = (contextEl) => {
    const scope = contextEl || document;
    scope.querySelectorAll('[data-h5p-task-player="true"]').forEach((root) => initOne(root));
  };

  const initOne = (root) => {
    if (!root || !(root instanceof Element)) return;
    const state = root.dataset.gustavH5pPlayerInit || '';
    if (state === 'ready') return;
    root.dataset.gustavH5pPlayerInit = 'ready';
    start(root);
  };

  const start = (root) => {
    const courseId = root.dataset.courseId || '';
    const taskId = root.dataset.taskId || '';
    const contentId = root.dataset.contentId || '';

    const statusEl = root.querySelector('[data-h5p-status]');
    const setStatus = (msg) => {
      if (statusEl) statusEl.textContent = msg || '';
    };

    const submittedStatementIds = new Set();

    const extractScore = (statement) => {
      const score = statement?.result?.score;
      if (!score) return null;
      const raw = Number(score.raw);
      const max = Number(score.max);
      if (!Number.isFinite(raw) || !Number.isFinite(max)) return null;
      const rawInt = Math.max(0, Math.trunc(raw));
      const maxInt = Math.max(0, Math.trunc(max));
      if (rawInt > maxInt) return null;
      return { raw: rawInt, max: maxInt };
    };

    const shouldPersistAttempt = (statement) => {
      const verbId = String(statement?.verb?.id || '');
      const completion = statement?.result?.completion;
      const success = statement?.result?.success;
      return (
        verbId.endsWith('/answered') ||
        verbId.endsWith('/completed') ||
        completion === true ||
        success === true
      );
    };

    const submitAttempt = async ({ statementId, scoreRaw, scoreMax }) => {
      if (!courseId || !taskId) return;
      if (!statementId) return;
      const rawKey = String(statementId);
      const safeKey = /^[A-Za-z0-9_-]{1,64}$/.test(rawKey)
        ? rawKey
        : (globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `h5p_${Date.now()}`);
      if (submittedStatementIds.has(safeKey)) return;
      submittedStatementIds.add(safeKey);

      const url = `/api/learning/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}/submissions`;
      const r = await fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': safeKey,
        },
        body: JSON.stringify({ kind: 'h5p', score_raw: scoreRaw, score_max: scoreMax }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        // Do not remove from set: we want to avoid infinite retry storms.
        throw new Error(data?.detail || data?.error || `HTTP ${r.status}`);
      }
      return data;
    };

    const run = async () => {
      if (!contentId) {
        setStatus('Kein H5P-Inhalt verknüpft.');
        return;
      }

      setStatus('Lade H5P…');
      const { defineElements } = await import('/h5p/webcomponents/index.js');
      defineElements(['h5p-player']);

      const installPlayer = (cid) => {
        const existing = root.querySelector('#h5pPlayer');
        const newEl = document.createElement('h5p-player');
        newEl.id = 'h5pPlayer';
        newEl.setAttribute('content-id', cid);
        if (taskId) newEl.setAttribute('context-id', taskId); // isolate user state per task
        if (existing) existing.replaceWith(newEl);
        else root.appendChild(newEl);

        newEl.loadContentCallback = async (contentIdArg, contextId, asUserId, readOnlyState) => {
          const url = new URL('/h5p/player/model', window.location.origin);
          url.searchParams.set('content_id', contentIdArg);
          if (courseId) url.searchParams.set('course_id', courseId);
          // IMPORTANT:
          // We must always send a stable task context to the H5P service.
          // The service uses `context_id` (== task_id in GUSTAV) to attach
          // course/task metadata to the `setFinished` endpoint, so it can
          // persist a `learning_submissions(kind='h5p')` row server-side.
          //
          // In some embed modes the webcomponent may not pass `contextId`
          // reliably, therefore we fall back to the known `taskId`.
          const stableContextId = taskId || contextId;
          if (stableContextId) url.searchParams.set('context_id', stableContextId);
          if (asUserId) url.searchParams.set('as_user_id', asUserId);
          if (readOnlyState) url.searchParams.set('read_only_state', 'true');
          const r = await fetch(url.toString(), { credentials: 'include' });
          const data = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);
          return data;
        };

        newEl.addEventListener('xAPI', async (ev) => {
          try {
            const statement = ev?.detail?.statement;
            if (!statement) return;
            if (!shouldPersistAttempt(statement)) return;
            const score = extractScore(statement);
            if (!score) return;
            const statementId = String(statement.id || '');
            await submitAttempt({ statementId, scoreRaw: score.raw, scoreMax: score.max });
            setStatus(`Gespeichert (${score.raw}/${score.max}).`);
          } catch (e) {
            // Keep UI usable even when persistence fails (network/CSRF/etc).
            setStatus(String(e?.message || e));
          }
        });
      };

      installPlayer(contentId);
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
