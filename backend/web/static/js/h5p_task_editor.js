/**
 * H5P Task Editor (Teacher UI)
 *
 * Why:
 * - For `Task.kind="h5p"` we embed Lumi's `<h5p-editor>` webcomponent directly
 *   into the normal GUSTAV task detail page (no iframe, no separate editor page).
 *
 * How:
 * - Load webcomponents from `/h5p/webcomponents/*` (served by the h5p service via proxy).
 * - Use task-centric Teaching endpoints under
 *   `/api/teaching/.../tasks/{task_id}/h5p/*` for model, save, import, export
 *   and reset.
 * - Keep the raw H5P `content_id` internal; the task remains the visible unit
 *   of authoring in the UI.
 */

/**
 * H5P Editor theming note (important):
 * - Lumi's `<h5p-editor>` renders the actual editor UI inside an iframe.
 * - CSS from the parent document does not apply inside the iframe.
 * - Therefore we inject our theme stylesheet into the iframe and copy the
 *   required GUSTAV design tokens (CSS variables) into the iframe root.
 */

  const H5P_THEME_CSS_HREF = '/h5p/theme/h5p-gustav.css';

  const readThemeTokensFromDocument = () => {
    const src = getComputedStyle(document.documentElement);
    const out = new Map();
    // Copy all CSS custom properties (design tokens) so the iframe can use the
    // exact same token set as the GUSTAV page (colors, spacing, typography, ...).
    for (let i = 0; i < src.length; i++) {
      const name = src[i];
      if (!name || !name.startsWith('--')) continue;
      const val = (src.getPropertyValue(name) || '').trim();
      if (val) out.set(name, val);
    }
    return out;
  };

  const ensureThemeStylesheetInIframe = (iframeDoc) => {
    const head = iframeDoc.head || iframeDoc.getElementsByTagName('head')[0] || null;
    if (!head) return;

    const selector = 'link[data-gustav-h5p-theme="true"]';
    const existing = head.querySelector(selector);
    if (existing) {
      // Move to the end of <head> to keep it last (override order matters).
      existing.setAttribute('href', H5P_THEME_CSS_HREF);
      head.appendChild(existing);
      return;
    }

    const link = iframeDoc.createElement('link');
    link.setAttribute('rel', 'stylesheet');
    link.setAttribute('href', H5P_THEME_CSS_HREF);
    link.setAttribute('data-gustav-h5p-theme', 'true');
    head.appendChild(link);
  };

  const applyThemeTokensToIframe = (iframeDoc) => {
    const root = iframeDoc.documentElement;
    if (!root) return;
    const tokens = readThemeTokensFromDocument();
    for (const [name, val] of tokens.entries()) {
      root.style.setProperty(name, val);
    }
  };

  const applyIframeBaseLayoutPatches = (iframeDoc) => {
    // Upstream editor CSS constrains the iframe document to max-width: 960px,
    // which feels "foreign" inside the GUSTAV card layout. We remove those
    // constraints and let the parent container control sizing.
    try {
      const html = iframeDoc.documentElement;
      const body = iframeDoc.body;
      if (html) {
        html.style.maxWidth = 'none';
        html.style.background = 'transparent';
        html.style.margin = '0';
        html.style.padding = '0';
      }
      if (body) {
        body.style.maxWidth = 'none';
        body.style.width = '100%';
        body.style.background = 'transparent';
        body.style.margin = '0';
        body.style.padding = '0';
      }
    } catch {
      // Best-effort only.
    }
  };

  const ensureThemeStylesheetStaysLastInIframeHead = (iframeEl, iframeDoc) => {
    const head = iframeDoc.head || iframeDoc.getElementsByTagName('head')[0] || null;
    if (!head) return;

    // The H5P editor appends additional styles dynamically while the user interacts.
    // To keep our theme overrides effective, we force our theme <link> to be the
    // last node in <head> whenever <head> changes.
    const currentHead = iframeEl.__gustavH5pThemeHead || null;
    if (currentHead === head && iframeEl.__gustavH5pThemeHeadObserver) return;

    try {
      iframeEl.__gustavH5pThemeHeadObserver?.disconnect?.();
    } catch {
      // Best-effort only.
    }

    const obs = new MutationObserver(() => {
      const link = head.querySelector('link[data-gustav-h5p-theme="true"]');
      if (!link) return;
      if (head.lastElementChild !== link) head.appendChild(link);
    });
    obs.observe(head, { childList: true });

    iframeEl.__gustavH5pThemeHead = head;
    iframeEl.__gustavH5pThemeHeadObserver = obs;
  };

  const applyThemeToEditorIframe = (editorEl) => {
    if (!editorEl || !(editorEl instanceof Element)) return false;
    const iframe = editorEl.querySelector('.h5p-editor-iframe');
    if (!iframe) return false;

    let iframeDoc = null;
    try {
      iframeDoc = iframe.contentDocument;
    } catch {
      return false;
    }
    if (!iframeDoc) return false;

    applyIframeBaseLayoutPatches(iframeDoc);
    applyThemeTokensToIframe(iframeDoc);
    ensureThemeStylesheetInIframe(iframeDoc);
    ensureThemeStylesheetStaysLastInIframeHead(iframe, iframeDoc);

    // Re-apply when the iframe reloads (some editor actions can trigger this).
    try {
      if (!iframe.dataset.gustavH5pThemeHook) {
        iframe.dataset.gustavH5pThemeHook = '1';
        iframe.addEventListener('load', () => {
          // The iframe can navigate and create a *new* document. Therefore we
          // always resolve `contentDocument` again instead of reusing a stale
          // reference captured at init time.
          applyThemeToEditorIframeWithRetry(editorEl);
        });
      }
    } catch {
      // Ignore: theming should never break the editor.
    }

    return true;
  };

  const applyThemeToEditorIframeWithRetry = (editorEl, remaining = 15) => {
    if (applyThemeToEditorIframe(editorEl)) return;
    if (remaining <= 0) return;
    setTimeout(() => applyThemeToEditorIframeWithRetry(editorEl, remaining - 1), 100);
  };

  const applyThemeToAllH5PEditors = () => {
    document.querySelectorAll('[data-h5p-task-editor="true"]').forEach((root) => {
      const editorEl = root.querySelector('h5p-editor');
      if (!editorEl) return;
      applyThemeToEditorIframeWithRetry(editorEl);
    });
  };

  const ensureThemeObserverInstalled = () => {
    if (globalThis.__gustav_h5p_editor_theme_observer_installed) return;
    globalThis.__gustav_h5p_editor_theme_observer_installed = true;
    const obs = new MutationObserver(() => {
      applyThemeToAllH5PEditors();
    });
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  };

  ensureThemeObserverInstalled();

  const EXPIRED_SESSION_MESSAGE =
    'Deine Sitzung ist abgelaufen. Bitte lade die Seite neu und melde dich bei Bedarf erneut an.';
  const activeMounts = new WeakMap();

  const toDisplayMessage = (error) => {
    const raw = error instanceof Error ? error.message : String(error || '');
    if (raw === 'unauthenticated') return EXPIRED_SESSION_MESSAGE;
    return raw || 'H5P konnte nicht geladen werden.';
  };

  const addListener = (target, type, handler, cleanupFns, options) => {
    if (!target || typeof target.addEventListener !== 'function') return;
    target.addEventListener(type, handler, options);
    cleanupFns.push(() => {
      try {
        target.removeEventListener(type, handler, options);
      } catch {
        // Best-effort only.
      }
    });
  };

  const createMount = (root) => {
    if (!root || !(root instanceof Element)) {
      throw new Error('Der H5P-Editor konnte nicht initialisiert werden.');
    }

    root.dataset.gustavH5pEditorInit = 'ready';
    const cleanupFns = [];
    let disposed = false;
    let editor = null;

    const statusEl = root.querySelector('[data-role="h5p-status"]');
    const btnImport = root.querySelector('[data-role="h5p-import"]');
    const btnExport = root.querySelector('[data-role="h5p-export"]');
    const btnReset = root.querySelector('[data-role="h5p-reset"]');
    const btnSave = root.querySelector('[data-role="h5p-save"]');
    const importFileInput = root.querySelector('[data-role="h5p-import-file"]');
    const editorHost = root.querySelector('[data-role="h5p-editor-host"]');

    const unitId = root.dataset.unitId || '';
    const sectionId = root.dataset.sectionId || '';
    const taskId = root.dataset.taskId || '';
    const initialContentId = root.dataset.contentId || '';
    const taskH5PBaseUrl =
      root.dataset.taskH5pBaseUrl ||
      `/api/teaching/units/${encodeURIComponent(unitId)}/sections/${encodeURIComponent(sectionId)}/tasks/${encodeURIComponent(taskId)}/h5p`;

    const hiddenContentIdInput =
      root.querySelector('input[name="h5p_content_id"]') ||
      root.closest('form')?.querySelector('input[name="h5p_content_id"]') ||
      null;

    const setStatus = (msg) => {
      if (disposed) return;
      const message = msg || '';
      root.dispatchEvent(new CustomEvent('gustav:h5p-status', { detail: { message } }));
      if (statusEl) statusEl.textContent = message;
    };

    const setHiddenContentId = (cid) => {
      if (!hiddenContentIdInput) return;
      hiddenContentIdInput.value = cid || '';
    };

    const ensureNoDuplicateTemplates = (editorEl) => {
      if (!editorEl) return;
      const roots = editorEl.querySelectorAll('.h5p-editor-component-root');
      if (roots.length <= 1) return;
      for (let i = 1; i < roots.length; i++) {
        roots[i].remove();
      }
    };

    const installEditor = (cid, loadContentCallback, saveContentCallback) => {
      if (disposed || !editorHost) return;
      const newEl = document.createElement('h5p-editor');
      newEl.setAttribute('content-id', cid || 'new');
      editorHost.replaceChildren(newEl);

      newEl.loadContentCallback = loadContentCallback;
      newEl.saveContentCallback = saveContentCallback;
      addListener(
        newEl,
        'editorloaded',
        (ev) => {
          ensureNoDuplicateTemplates(newEl);
          applyThemeToEditorIframeWithRetry(newEl);
          setStatus(`Editor geladen (${ev?.detail?.ubername || 'unbekannte Bibliothek'}).`);
        },
        cleanupFns
      );

      editor = newEl;
      ensureNoDuplicateTemplates(editor);
    };

    const run = async () => {
      if (!btnImport || !btnExport || !btnReset || !btnSave || !importFileInput || !editorHost) {
        setStatus('Die H5P-Editor-Oberfläche ist unvollständig.');
        return;
      }

      setStatus('Lade H5P-Webcomponents …');
      const { defineElements } = await import('/h5p/webcomponents/index.js');
      if (disposed) return;
      defineElements(['h5p-editor']);

      let activeContentId = initialContentId || '';

      const loadContentCallback = async () => {
        const url = new URL(`${taskH5PBaseUrl}/editor-model`, window.location.origin);
        const r = await fetch(url.toString(), { credentials: 'include' });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);
        return data;
      };

      const saveContentCallback = async (_contentId, requestBody) => {
        const r = await fetch(`${taskH5PBaseUrl}/save`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.error || `HTTP ${r.status}`);
        if (data?.content_id) {
          activeContentId = data.content_id;
          setHiddenContentId(activeContentId);
        }
        return { contentId: data.content_id, metadata: data.metadata };
      };

      setHiddenContentId(initialContentId || '');
      installEditor(initialContentId || 'new', loadContentCallback, saveContentCallback);

      addListener(
        btnImport,
        'click',
        (ev) => {
          ev.preventDefault();
          importFileInput.click();
        },
        cleanupFns
      );

      addListener(
        importFileInput,
        'change',
        async () => {
          const file = importFileInput.files?.[0];
          if (!file) return;
          const formData = new FormData();
          formData.set('file', file, file.name || 'content.h5p');
          try {
            setStatus('Importiere H5P-Paket …');
            const r = await fetch(`${taskH5PBaseUrl}/import`, {
              method: 'POST',
              credentials: 'include',
              body: formData,
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data?.detail || data?.error || `HTTP ${r.status}`);
            activeContentId = data?.h5p?.content_id || '';
            setHiddenContentId(activeContentId);
            installEditor(activeContentId || 'new', loadContentCallback, saveContentCallback);
            setStatus('H5P-Paket importiert.');
          } catch (e) {
            setStatus(toDisplayMessage(e));
          } finally {
            importFileInput.value = '';
          }
        },
        cleanupFns
      );

      addListener(
        btnExport,
        'click',
        async (ev) => {
          ev.preventDefault();
          if (!activeContentId) {
            setStatus('Noch kein H5P-Inhalt zum Export vorhanden.');
            return;
          }
          try {
            setStatus('Exportiere H5P-Paket …');
            const r = await fetch(`${taskH5PBaseUrl}/export`, { credentials: 'include' });
            if (!r.ok) {
              const data = await r.json().catch(() => ({}));
              throw new Error(data?.detail || data?.error || `HTTP ${r.status}`);
            }
            const blob = await r.blob();
            const href = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = href;
            a.download = `task-${taskId || 'h5p'}.h5p`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(href);
            setStatus('Export abgeschlossen.');
          } catch (e) {
            setStatus(toDisplayMessage(e));
          }
        },
        cleanupFns
      );

      addListener(
        btnReset,
        'click',
        async (ev) => {
          ev.preventDefault();
          try {
            setStatus('Setze verknüpften H5P-Inhalt zurück …');
            const r = await fetch(`${taskH5PBaseUrl}/reset`, {
              method: 'POST',
              credentials: 'include',
            });
            const data = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(data?.detail || data?.error || `HTTP ${r.status}`);
            activeContentId = '';
            setHiddenContentId('');
            installEditor('new', loadContentCallback, saveContentCallback);
            setStatus('Die Aufgabe ist wieder auf einen leeren H5P-Entwurf gesetzt.');
          } catch (e) {
            setStatus(toDisplayMessage(e));
          }
        },
        cleanupFns
      );

      addListener(
        btnSave,
        'click',
        async (ev) => {
          ev.preventDefault();
          try {
            if (!editor) {
              setStatus('Der Editor ist noch nicht bereit.');
              return;
            }
            setStatus('Speichere H5P-Inhalt …');
            const saved = await editor.save();
            if (saved?.contentId) {
              activeContentId = saved.contentId;
              setHiddenContentId(saved.contentId);
              setStatus('H5P-Inhalt gespeichert.');
            } else {
              setStatus('Gespeichert.');
            }
          } catch (e) {
            setStatus(toDisplayMessage(e));
          }
        },
        cleanupFns
      );

      setStatus('Bereit.');
    };

    const whenReady = run().catch((error) => {
      setStatus(toDisplayMessage(error));
      throw error;
    });

    return {
      whenReady,
      destroy() {
        if (disposed) return;
        disposed = true;
        editor = null;
        for (const cleanup of cleanupFns.splice(0).reverse()) {
          try {
            cleanup();
          } catch {
            // Best-effort only.
          }
        }
        editorHost?.replaceChildren();
        delete root.dataset.gustavH5pEditorInit;
      },
    };
  };

  const autoMountAll = (contextEl) => {
    const scope = contextEl || document;
    scope.querySelectorAll('[data-h5p-task-editor="true"]').forEach((root) => {
      if (root.dataset.gustavH5pAutoMounted === 'true') return;
      root.dataset.gustavH5pAutoMounted = 'true';
      mountH5PTaskEditor(root);
    });
  };

  export const mountH5PTaskEditor = (root) => {
    if (!root || !(root instanceof Element)) {
      throw new Error('Der H5P-Editor konnte nicht initialisiert werden.');
    }

    const previous = activeMounts.get(root);
    previous?.destroy?.();

    const mount = createMount(root);
    activeMounts.set(root, mount);

    return {
      whenReady: mount.whenReady,
      destroy() {
        if (activeMounts.get(root) === mount) {
          activeMounts.delete(root);
        }
        mount.destroy();
      },
    };
  };

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => autoMountAll(document), { once: true });
} else {
  autoMountAll(document);
}
