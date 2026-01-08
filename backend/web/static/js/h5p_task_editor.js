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
  const root = document.querySelector('[data-h5p-task-editor="true"]');
  if (!root) return;

  const unitId = root.dataset.unitId || '';
  const sectionId = root.dataset.sectionId || '';
  const taskId = root.dataset.taskId || '';
  const initialContentId = root.dataset.contentId || '';

  const statusEl = document.getElementById('h5pStatus');
  const contentIdInput = document.getElementById('h5pContentId');
  const btnNew = document.getElementById('h5pNew');
  const btnLoad = document.getElementById('h5pLoad');
  const btnSave = document.getElementById('h5pSave');
  const editor = document.getElementById('h5pEditor');

  const setStatus = (msg) => {
    if (!statusEl) return;
    statusEl.textContent = msg || '';
  };

  const setEditorContentId = (cid) => {
    if (!editor) return;
    // Known Lumi pitfall: switching from "new" → existing sometimes needs a forced re-render.
    editor.contentId = undefined;
    editor.contentId = cid;
  };

  async function patchTaskContentId(contentId) {
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
  }

  async function init() {
    if (!editor || !contentIdInput || !btnNew || !btnLoad || !btnSave) {
      setStatus('Editor UI is incomplete (missing DOM elements).');
      return;
    }

    setStatus('Loading H5P webcomponents…');
    const { defineElements } = await import('/h5p/webcomponents/index.js');
    defineElements(['h5p-editor']);

    editor.loadContentCallback = async (contentId) => {
      const url = new URL('/h5p/editor/model', window.location.origin);
      if (contentId && contentId !== 'new') url.searchParams.set('content_id', contentId);
      const r = await fetch(url.toString(), { credentials: 'include' });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);
      return data;
    };

    editor.saveContentCallback = async (contentId, requestBody) => {
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

    btnNew.addEventListener('click', () => {
      contentIdInput.value = '';
      setEditorContentId('new');
      setStatus('Creating new content…');
    });

    btnLoad.addEventListener('click', () => {
      const cid = (contentIdInput.value || '').trim();
      if (!cid) {
        setStatus('Bitte zuerst eine Content ID eingeben.');
        return;
      }
      setEditorContentId(cid);
      setStatus(`Loading content ${cid}…`);
    });

    btnSave.addEventListener('click', async () => {
      try {
        setStatus('Saving…');
        const saved = await editor.save();
        if (saved?.contentId) {
          contentIdInput.value = saved.contentId;
          await patchTaskContentId(saved.contentId);
          setStatus(`Saved. Content ID: ${saved.contentId}`);
        } else {
          setStatus('Saved.');
        }
      } catch (e) {
        setStatus(String(e?.message || e));
      }
    });

    editor.addEventListener('editorloaded', (ev) => {
      setStatus(`Editor loaded (${ev?.detail?.ubername || 'unknown library'}).`);
    });

    if (initialContentId) {
      contentIdInput.value = initialContentId;
      setEditorContentId(initialContentId);
    }

    setStatus('Ready.');
  }

  init().catch((e) => {
    setStatus('Init failed: ' + String(e?.message || e));
  });
})();
