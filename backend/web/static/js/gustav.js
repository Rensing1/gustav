/**
 * GUSTAV JavaScript Module
 * Minimal client-side functionality for the GUSTAV learning platform
 *
 * Features:
 * - Theme management (Everforest Light & Dark)
 * - HTMX event handling
 * - Error/success notifications
 * - Keyboard shortcuts
 */

class Gustav {
  constructor() {
    // Available themes
    this.themes = [
      'rose-pine-dawn',
      'everforest-dark-hard'
    ];
    this.sidebarPreviousFocus = null;
    this.sidebarTooltipEl = null;
    this.sidebarTooltipResizeHandler = null;
    this.sidebarPointerTracking = false;
    this.sidebarPointerStartX = 0;
    this.sidebarPointerStartY = 0;
    this.sidebarPointerDeltaX = 0;
    this.sidebarPointerDeltaY = 0;

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.init());
    } else {
      this.init();
    }
  }

  /**
   * Initialize all modules
   */
  init() {
    this.initTheme();
    this.initHTMX();
    this.initKeyboardShortcuts();
    this.restoreSidebarState(); // Restore sidebar collapsed/expanded state
    this.initSidebarDelegation();
    this.initSidebarAccessibility(); // Ensure keyboard navigation stays usable
    this.initSidebarGestures();
    this.initSidebarTooltips();
    this.initLearningTaskForms(); // Progressive enhancement for student task forms
    this.initMaterialCreateForms(); // Toggle + upload-intent flow for teacher materials
  }

  /**
   * Validate file against allowed MIME and max size.
   */
  validateFile(file, allowedMime, maxBytes) {
    if (allowedMime && allowedMime.length) {
      const ok = allowedMime.indexOf(file.type) !== -1;
      if (!ok) throw new Error('mime_not_allowed');
    }
    if (maxBytes > 0 && (file.size <= 0 || file.size > maxBytes)) {
      throw new Error('size_exceeded');
    }
  }

  /**
   * Generic intent + PUT upload helper. Returns { intent, sha, mime, size }.
   */
  async requestIntentAndUpload(intentUrl, file, payload) {
    const intentResp = await fetch(intentUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!intentResp.ok) {
      throw new Error(`intent_failed_${intentResp.status}`);
    }
    const intent = await intentResp.json();
    const uploadUrl = intent.url || intent.upload_url;
    const uploadHeaders = intent.headers || intent.upload_headers || { 'Content-Type': file.type || 'application/octet-stream' };
    if (!uploadUrl) {
      throw new Error('upload_url_missing');
    }

    const putResp = await fetch(uploadUrl, {
      method: 'PUT',
      headers: uploadHeaders,
      body: file
    });
    if (!putResp.ok) {
      throw new Error(`upload_failed_${putResp.status}`);
    }

    let sha = '';
    try {
      const putJson = await putResp.json();
      sha = putJson.sha256 || '';
    } catch (_) {
      sha = '';
    }
    if (!sha) {
      sha = await this.hashFileSha256(file);
    }
    return { intent, sha, mime: file.type || 'application/octet-stream', size: file.size };
  }

  /**
   * Theme Management
   */
  initTheme() {
    // Load saved theme or use system preference
    const savedTheme = localStorage.getItem('gustav-theme');

    if (savedTheme && this.themes.includes(savedTheme)) {
      this.setTheme(savedTheme);
    } else {
      // Detect system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      this.setTheme(prefersDark ? 'everforest-dark-hard' : 'rose-pine-dawn');
    }

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)')
      .addEventListener('change', (e) => {
        if (!localStorage.getItem('gustav-theme')) {
          this.setTheme(e.matches ? 'everforest-dark-hard' : 'rose-pine-dawn');
        }
      });
  }

  /**
   * Progressive enhancement for Learning task submit forms (text/upload).
   *
   * - Toggles fields when switching mode (text vs. upload)
   * - Handles client-side upload flow (upload-intent → PUT to stub → fill hidden fields)
   */
  initLearningTaskForms() {
    const forms = document.querySelectorAll('form.task-submit-form');
    if (!forms.length) return;

    forms.forEach((form) => {
      // Toggle fields when user changes mode
      form.addEventListener('change', (e) => {
        const modeInput = form.querySelector('input[name="mode"]:checked');
        const mode = modeInput ? modeInput.value : (form.dataset.mode || 'text');
        form.dataset.mode = mode;
        const textFields = form.querySelector('.fields-text');
        const uploadFields = form.querySelector('.fields-upload');
        if (textFields && uploadFields) {
          if (mode === 'upload' || mode === 'image' || mode === 'file') {
            textFields.hidden = true;
            uploadFields.hidden = false;
          } else {
            textFields.hidden = false;
            uploadFields.hidden = true;
          }
        }
      });

      // Handle file selection → request upload-intent → PUT bytes → fill hidden fields
      const fileInput = form.querySelector('input[type="file"][name="upload_file"]');
      if (!fileInput) return;

      fileInput.addEventListener('change', async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;
        try {
          await this.prepareLearningUpload(form, file);
          this.showNotification('Upload vorbereitet. Jetzt „Abgeben“ klicken.', 'info', 2500);
        } catch (err) {
          console.error('Upload prepare failed', err);
          this.showNotification('Upload fehlgeschlagen. Bitte erneut versuchen.', 'error');
          // Clear hidden fields to avoid submitting invalid payload
          ['storage_key','mime_type','size_bytes','sha256'].forEach((name) => {
            const el = form.querySelector(`input[name="${name}"]`);
            if (el) el.value = '';
          });
        }
      });
    });
  }

  /**
   * Progressive enhancement for teacher material create (Text | Datei).
   * - Toggles visibility between the two forms.
   * - Prepares upload-intent + PUT for file mode, then submits finalize form.
   */
  initMaterialCreateForms() {
    const container = document.querySelector('[data-material-create]');
    if (!container) return;

    const radios = container.querySelectorAll('input[name="material_mode"]');
    const forms = container.querySelectorAll('.material-form');
    const showMode = (mode) => {
      container.dataset.mode = mode;
      forms.forEach((f) => {
        const isMatch = (f.dataset.mode || '') === mode;
        f.hidden = !isMatch;
      });
    };
    radios.forEach((r) =>
      r.addEventListener('change', () => {
        showMode(r.value);
      })
    );
    showMode('text');

    const fileForm = container.querySelector('form.material-form--file');
    if (!fileForm) return;
    const submitBtn = fileForm.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = false; // JS enabled → allow submit
    const fileInput = fileForm.querySelector('input[name="upload_file"]');
    const intentInput = fileForm.querySelector('input[name="intent_id"]');
    const shaInput = fileForm.querySelector('input[name="sha256"]');
    fileForm.dataset.fileDirty = fileForm.dataset.fileDirty || '1';

    const clearPrepared = () => {
      fileForm.dataset.fileDirty = '1';
      if (intentInput) intentInput.value = '';
      if (shaInput) shaInput.value = '';
    };
    if (fileInput) {
      fileInput.addEventListener('change', clearPrepared);
    }

    fileForm.addEventListener('submit', async (e) => {
      // If already prepared and file unchanged, allow normal submit (HTMX catches if present)
      if (fileForm.dataset.fileDirty !== '1' && intentInput?.value && shaInput?.value) {
        return;
      }
      e.preventDefault();
      if (!fileInput || !fileInput.files || !fileInput.files.length) {
        this.showNotification('Bitte eine Datei auswählen.', 'error');
        if (fileInput) fileInput.focus();
        return;
      }
      try {
        await this.prepareMaterialUpload(fileForm, fileInput.files[0]);
        fileForm.dataset.fileDirty = '0';
        // trigger a fresh submit so HTMX/native can proceed with filled hidden fields
        fileForm.requestSubmit();
      } catch (err) {
        console.error('material upload failed', err);
        this.showNotification('Upload fehlgeschlagen. Bitte erneut versuchen.', 'error');
        clearPrepared();
      }
    });
  }

  /**
   * Upload-intent + PUT for teacher materials (file-mode).
   */
  async prepareMaterialUpload(form, file) {
    const intentUrl = form.dataset.intentUrl;
    if (!intentUrl) throw new Error('missing_intent_url');

    const allowedMime = (form.dataset.allowedMime || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const maxBytes = parseInt(form.dataset.maxBytes || '0', 10);
    this.validateFile(file, allowedMime, maxBytes);

    const { intent, sha } = await this.requestIntentAndUpload(intentUrl, file, {
      filename: file.name || 'upload.bin',
      mime_type: file.type || 'application/octet-stream',
      size_bytes: file.size
    });
    const set = (name, value) => {
      const el = form.querySelector(`input[name="${name}"]`);
      if (el) el.value = value;
    };
    set('intent_id', intent.intent_id || '');
    set('sha256', sha);
    return intent;
  }

  /**
   * Persist which submission the learner has opened while HTMX polls history fragments.
   *
   * hx-on calls this whenever a <details> toggles. We update data-open-attempt-id
   * and hx-vals so the next poll request keeps the same attempt expanded.
   */
  handleHistoryToggle(event, wrapper) {
    if (!wrapper || !wrapper.classList || !wrapper.classList.contains('task-panel__history')) {
      return;
    }
    const details = event.target && event.target.closest
      ? event.target.closest('details.task-panel__history-entry')
      : null;
    if (!details) return;

    const historyEl = wrapper;
    let openId = '';

    if (details.open) {
      openId = details.dataset.submissionId || '';
    } else {
      const stillOpen = historyEl.querySelector('details.task-panel__history-entry[open]');
      openId = stillOpen ? (stillOpen.dataset.submissionId || '') : '';
    }

    historyEl.dataset.openAttemptId = openId;
    try {
      historyEl.setAttribute('hx-vals', JSON.stringify({ open_attempt_id: openId }));
    } catch (err) {
      console.warn('Failed to persist open attempt id', err);
    }
  }

  /**
   * Execute the client-side upload prepare flow for learning submissions.
   * 1) POST upload-intent → get storage_key + PUT URL
   * 2) PUT file to returned URL
   * 3) Fill hidden fields for final submission
    */
  async prepareLearningUpload(form, file) {
    const courseId = form.dataset.courseId;
    const taskId = form.dataset.taskId;
    if (!courseId || !taskId) throw new Error('missing form dataset');

    const mime = file.type;
    const size = file.size;
    const filename = file.name || 'upload.bin';
    const kind = mime === 'application/pdf' ? 'file' : (mime.startsWith('image/') ? 'image' : 'file');

    // Client-side checks mirror server (non-authoritative)
    this.validateFile(file, ['image/png', 'image/jpeg', 'application/pdf'], 10 * 1024 * 1024);

    const { intent, sha, size: sizeBytes } = await this.requestIntentAndUpload(
      `/api/learning/courses/${courseId}/tasks/${taskId}/upload-intents`,
      file,
      { kind, filename, mime_type: mime, size_bytes: size }
    );
    const sha256 = sha;

    // Fill hidden fields — used by the final POST /submissions
    const set = (name, value) => {
      const el = form.querySelector(`input[name="${name}"]`);
      if (el) el.value = value;
    };
    set('storage_key', intent.storage_key || '');
    set('mime_type', mime);
    set('size_bytes', String(sizeBytes));
    set('sha256', sha256);
  }

  /**
   * Compute SHA-256 digest for a File using Web Crypto.
   */
  async hashFileSha256(file) {
    const cryptoObj = window.crypto || window.msCrypto;
    if (!cryptoObj || !cryptoObj.subtle) {
      throw new Error('Secure hashing not supported in this browser');
    }
    const buffer = await file.arrayBuffer();
    const hashBuffer = await cryptoObj.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Sidebar event delegation
   */
  initSidebarDelegation() {
    document.addEventListener('click', (event) => {
      const toggleTrigger = event.target.closest('[data-action="sidebar-toggle"]');
      if (toggleTrigger) {
        event.preventDefault();
        this.toggleSidebar();
        return;
      }

      const closeTrigger = event.target.closest('[data-action="sidebar-close"]');
      if (closeTrigger) {
        event.preventDefault();
        this.closeSidebar();
        return;
      }

      const sidebarLink = event.target.closest('.sidebar-link');
      if (sidebarLink && this.shouldAutoCloseSidebar()) {
        // Allow HTMX to process the navigation, then close the sidebar.
        requestAnimationFrame(() => this.closeSidebar());
      }
    });

    document.addEventListener('keydown', (event) => {
      if (!this.shouldAutoCloseSidebar()) return;
      if (event.key !== 'Enter' && event.key !== ' ') return;

      const sidebarLink = event.target.closest && event.target.closest('.sidebar-link');
      if (!sidebarLink) return;

      // Do not prevent default to keep activation logic intact.
      requestAnimationFrame(() => this.closeSidebar());
    });
  }

  /**
   * Set active theme
   */
  setTheme(themeName) {
    if (!this.themes.includes(themeName)) return;

    document.documentElement.setAttribute('data-theme', themeName);
    localStorage.setItem('gustav-theme', themeName);

    // Update theme toggle button if exists
    const btn = document.querySelector('[data-theme-toggle]');
    if (btn) {
      btn.setAttribute('data-current-theme', themeName);
      btn.title = `Current theme: ${themeName}`;
    }
  }

  /**
   * Toggle between themes
   */
  toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'rose-pine-dawn';
    const currentIndex = this.themes.indexOf(current);
    const nextIndex = (currentIndex + 1) % this.themes.length;
    this.setTheme(this.themes[nextIndex]);

    // Show notification
    this.showNotification(`Theme changed to ${this.themes[nextIndex]}`, 'info');
  }

  /**
   * Cycle through themes with preview
   */
  cycleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'rose-pine-dawn';
    const currentIndex = this.themes.indexOf(current);
    const nextIndex = (currentIndex + 1) % this.themes.length;

    // Preview next theme
    document.documentElement.setAttribute('data-theme', this.themes[nextIndex]);

    // Show theme name
    this.showNotification(this.themes[nextIndex], 'info', 1000);

    // Save after delay
    setTimeout(() => {
      localStorage.setItem('gustav-theme', this.themes[nextIndex]);
    }, 100);
  }

  /**
   * HTMX Event Handlers
   */
  initHTMX() {
    // Listen for HTMX events
    document.body.addEventListener('htmx:afterSwap', (evt) => {
      // Re-initialize components after HTMX swap
      this.hideSidebarTooltip();
      this.initTheme();

      // Restore sidebar state after navigation
      // The sidebar persists but main-content gets replaced
      // Note: With OOB swaps, the sidebar element might be replaced AFTER this event
      // We still restore here for non-OOB swaps, and add specific OOB handlers below.
      this.restoreSidebarState();
      this.initSidebarAccessibility();
      this.initSidebarGestures();
    });

    // Ensure sidebar state restoration after OOB sidebar replacement
    document.body.addEventListener('htmx:oobAfterSwap', (evt) => {
      // Run on next frame to ensure DOM is updated
      requestAnimationFrame(() => {
        this.hideSidebarTooltip();
        this.restoreSidebarState();
        this.initSidebarAccessibility();
        this.initSidebarGestures();
      });
    });

    // After all swaps settle, re-apply state as a safety net
    document.body.addEventListener('htmx:afterSettle', () => {
      this.hideSidebarTooltip();
      this.restoreSidebarState();
      this.initSidebarAccessibility();
      this.initSidebarGestures();
    });

    document.body.addEventListener('htmx:sendError', (evt) => {
      this.showNotification('Network error. Please try again.', 'error');
    });

    document.body.addEventListener('htmx:responseError', (evt) => {
      const status = evt.detail.xhr.status;
      const message = status === 404 ? 'Resource not found' :
                      status === 403 ? 'Access denied' :
                      status === 500 ? 'Server error' :
                      'Request failed';
      this.showNotification(message, 'error');
    });

    // Custom HTMX events from server
    document.body.addEventListener('htmx:showMessage', (evt) => {
      this.showNotification(evt.detail.message, evt.detail.type || 'info');
    });
    // Also support plain 'showMessage' events (e.g., via HX-Trigger)
    document.body.addEventListener('showMessage', (evt) => {
      const detail = evt.detail || {};
      this.showNotification(detail.message || 'Aktion ausgeführt', detail.type || 'info');
    });
  }

  /**
   * Show notification banner
   */
  showNotification(message, type = 'info', duration = 3000) {
    // Remove existing notifications
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification alert alert-${type}`;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      min-width: 250px;
      animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;

    // Add to page
    document.body.appendChild(notification);

    // Auto-remove after duration
    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, duration);
  }

  /**
   * Keyboard shortcuts
   */
  initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Alt+T: Toggle theme
      if (e.altKey && e.key === 't') {
        e.preventDefault();
        this.cycleTheme();
      }

      // Alt+H: Go home
      if (e.altKey && e.key === 'h') {
        e.preventDefault();
        window.location.href = '/';
      }

      // Escape: Close modals/dialogs
      if (e.key === 'Escape') {
        const modal = document.querySelector('.modal.active');
        if (modal) {
          modal.classList.remove('active');
        }
      }
    });
  }

  /**
   * Toggle sidebar open/closed
   */
  toggleSidebar() {
    this.hideSidebarTooltip();
    // Select by ID to avoid ambiguous matches after client-side navigation
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const overlay = document.querySelector('.sidebar-overlay');
    const isMobile = window.innerWidth < 768;

    // Guard against missing elements
    if (!sidebar) return;

    if (isMobile) {
      // Mobile: slide in/out with overlay
      const isOpen = sidebar.classList.contains('open');

      if (isOpen) {
        this.closeSidebar();
      } else {
        sidebar.classList.add('open');
        if (overlay) overlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
        this.activateSidebarFocusTrap(sidebar);
      }
    } else {
      // Desktop: collapse/expand
      const isCollapsed = sidebar.classList.contains('collapsed');

      if (isCollapsed) {
        sidebar.classList.remove('collapsed');
        if (mainContent) mainContent.classList.remove('sidebar-collapsed');
        localStorage.setItem('gustav-sidebar', 'expanded');
      } else {
        sidebar.classList.add('collapsed');
        if (mainContent) mainContent.classList.add('sidebar-collapsed');
        localStorage.setItem('gustav-sidebar', 'collapsed');
      }
    }

  }

  /**
   * Close sidebar (mobile only)
   */
  closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    const overlay = document.querySelector('.sidebar-overlay');

    sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
    document.body.style.overflow = ''; // Restore scrolling
    this.deactivateSidebarFocusTrap(sidebar);
    this.hideSidebarTooltip();
  }

  /**
   * Restore sidebar state from localStorage
   */
  restoreSidebarState() {
    // Use IDs for stable targeting even if fragments are swapped
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const savedState = localStorage.getItem('gustav-sidebar');
    const isMobile = window.innerWidth < 768;

    // Only restore state on desktop and if sidebar exists
    if (!sidebar || isMobile) return;

    if (savedState === 'collapsed') {
      sidebar.classList.add('collapsed');
      if (mainContent) mainContent.classList.add('sidebar-collapsed');
    } else {
      // Ensure expanded state clears collapse-related classes
      sidebar.classList.remove('collapsed');
      if (mainContent) mainContent.classList.remove('sidebar-collapsed');
    }

  }

  /**
   * Sidebar accessibility helpers (keyboard + focus management)
   */
  initSidebarAccessibility() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    this.setupSidebarArrowNavigation(sidebar);
    this.updateSidebarTabIndexes(sidebar);
  }

  /**
   * Provide Arrow-Key navigation for the sidebar links.
   */
  setupSidebarArrowNavigation(sidebar) {
    if (!sidebar || sidebar.dataset.arrowNavReady === 'true') return;

    const itemsContainer = sidebar.querySelector('.sidebar-items');
    if (!itemsContainer) return;

    itemsContainer.addEventListener('keydown', (event) => {
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
        return;
      }

      const links = this.getVisibleSidebarLinks(sidebar);
      if (!links.length) return;

      event.preventDefault();

      const current = document.activeElement;
      let currentIndex = links.indexOf(current);
      if (currentIndex === -1) {
        currentIndex = 0;
      }

      const direction = (event.key === 'ArrowUp' || event.key === 'ArrowLeft') ? -1 : 1;
      const nextIndex = (currentIndex + direction + links.length) % links.length;
      const targetLink = links[nextIndex];

      this.setSidebarTabIndexes(sidebar, targetLink);
      targetLink.focus();
    });

    itemsContainer.addEventListener('focusin', (event) => {
      if (!event.target.classList.contains('sidebar-link')) return;
      this.setSidebarTabIndexes(sidebar, event.target);
    });

    sidebar.dataset.arrowNavReady = 'true';
  }

  /**
   * Ensure only the active sidebar link is reachable via Tab.
   */
  updateSidebarTabIndexes(sidebar) {
    const links = this.getVisibleSidebarLinks(sidebar);
    if (!links.length) return;

    const focused = links.find((link) => link === document.activeElement);
    if (focused) {
      this.setSidebarTabIndexes(sidebar, focused);
      return;
    }

    const active = links.find((link) => link.classList.contains('active'));
    this.setSidebarTabIndexes(sidebar, active || links[0]);
  }

  /**
   * Apply roving tabindex pattern to sidebar links.
   */
  setSidebarTabIndexes(sidebar, activeLink) {
    const links = this.getVisibleSidebarLinks(sidebar);
    if (!links.length) return;

    const target = links.includes(activeLink) ? activeLink : links[0];

    links.forEach((link) => {
      link.tabIndex = link === target ? 0 : -1;
    });
  }

  /**
   * Return all visible sidebar links.
   */
  getVisibleSidebarLinks(sidebar) {
    if (!sidebar) return [];

    return Array.from(sidebar.querySelectorAll('.sidebar-link')).filter((link) => {
      if (link.getAttribute('aria-hidden') === 'true') return false;
      return link.offsetParent !== null;
    });
  }

  /**
   * Trap focus inside the mobile sidebar and close on Escape.
   */
  activateSidebarFocusTrap(sidebar) {
    if (!sidebar || sidebar.dataset.focusTrap === 'active') return;

    this.sidebarPreviousFocus = document.activeElement;

    const handleKeydown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        this.closeSidebar();
        return;
      }

      if (event.key !== 'Tab') return;

      const links = this.getVisibleSidebarLinks(sidebar);
      if (!links.length) return;

      event.preventDefault();

      const current = document.activeElement;
      let currentIndex = links.indexOf(current);
      if (currentIndex === -1) {
        currentIndex = 0;
      }

      const direction = event.shiftKey ? -1 : 1;
      const nextIndex = (currentIndex + direction + links.length) % links.length;
      const targetLink = links[nextIndex];

      this.setSidebarTabIndexes(sidebar, targetLink);
      targetLink.focus();
    };

    sidebar.addEventListener('keydown', handleKeydown);
    sidebar.dataset.focusTrap = 'active';
    sidebar._focusTrapHandler = handleKeydown;

    this.updateSidebarTabIndexes(sidebar);
    const links = this.getVisibleSidebarLinks(sidebar);
    if (links.length) {
      this.setSidebarTabIndexes(sidebar, links[0]);
      links[0].focus();
    }
  }

  /**
   * Remove focus trap and restore previous focus target.
   */
  deactivateSidebarFocusTrap(sidebar) {
    if (!sidebar || sidebar.dataset.focusTrap !== 'active') return;

    const handler = sidebar._focusTrapHandler;
    if (handler) {
      sidebar.removeEventListener('keydown', handler);
      delete sidebar._focusTrapHandler;
    }

    delete sidebar.dataset.focusTrap;

    this.updateSidebarTabIndexes(sidebar);

    if (this.sidebarPreviousFocus && document.contains(this.sidebarPreviousFocus)) {
      this.sidebarPreviousFocus.focus();
    }

    this.sidebarPreviousFocus = null;
  }

  /**
   * Determine whether the sidebar should auto-close (mobile + open).
   */
  shouldAutoCloseSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return false;
    const isMobile = window.innerWidth < 768;
    return isMobile && sidebar.classList.contains('open');
  }

  /**
   * Gesture handling for mobile sidebar (swipe to close).
   */
  initSidebarGestures() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar || sidebar.dataset.gestureReady === 'true') return;

    const overlay = document.querySelector('.sidebar-overlay');
    const gestureTargets = [sidebar, overlay].filter(Boolean);
    if (!gestureTargets.length) return;

    const handlePointerDown = (event) => {
      if (!this.shouldAutoCloseSidebar()) return;

      this.sidebarPointerTracking = true;
      this.sidebarPointerStartX = event.clientX;
      this.sidebarPointerStartY = event.clientY;
      this.sidebarPointerDeltaX = 0;
      this.sidebarPointerDeltaY = 0;
    };

    const handlePointerMove = (event) => {
      if (!this.sidebarPointerTracking) return;
      this.sidebarPointerDeltaX = event.clientX - this.sidebarPointerStartX;
      this.sidebarPointerDeltaY = event.clientY - this.sidebarPointerStartY;
    };

    const endTracking = () => {
      if (!this.sidebarPointerTracking) return;

      const horizontalThreshold = 80;
      const verticalTolerance = 60;

      if (Math.abs(this.sidebarPointerDeltaY) < verticalTolerance &&
          this.sidebarPointerDeltaX < -horizontalThreshold) {
        this.closeSidebar();
      }

      this.sidebarPointerTracking = false;
      this.sidebarPointerDeltaX = 0;
      this.sidebarPointerDeltaY = 0;
    };

    gestureTargets.forEach((target) => {
      target.addEventListener('pointerdown', handlePointerDown);
      target.addEventListener('pointermove', handlePointerMove);
      target.addEventListener('pointerup', endTracking);
      target.addEventListener('pointercancel', endTracking);
      target.addEventListener('pointerleave', endTracking);
    });

    sidebar.dataset.gestureReady = 'true';
  }

  /**
   * Tooltips for collapsed sidebar icons (desktop).
   */
  initSidebarTooltips() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar || sidebar.dataset.tooltipReady === 'true') return;

    const links = sidebar.querySelectorAll('.sidebar-link');

    links.forEach((link) => {
      if (link.dataset.tooltipBound === 'true') return;

      const show = () => {
        if (!this.isSidebarCollapsed(sidebar)) {
          this.hideSidebarTooltip();
          return;
        }
        this.showSidebarTooltip(link);
      };

      const hide = () => this.hideSidebarTooltip();

      link.addEventListener('focus', show);
      link.addEventListener('blur', hide);
      link.addEventListener('mouseenter', show);
      link.addEventListener('mouseleave', hide);

      link.dataset.tooltipBound = 'true';
    });

    if (!this.sidebarTooltipResizeHandler) {
      this.sidebarTooltipResizeHandler = () => this.hideSidebarTooltip();
      window.addEventListener('resize', this.sidebarTooltipResizeHandler);
    }

    sidebar.dataset.tooltipReady = 'true';
  }

  /**
   * Render tooltip next to the collapsed sidebar.
   */
  showSidebarTooltip(link) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar || !this.isSidebarCollapsed(sidebar)) return;

    const label = link.getAttribute('data-tooltip') || link.getAttribute('aria-label') || link.textContent.trim();
    if (!label) return;

    if (!this.sidebarTooltipEl) {
      const tooltip = document.createElement('div');
      tooltip.className = 'sidebar-tooltip';
      tooltip.setAttribute('role', 'tooltip');
      tooltip.hidden = true;
      document.body.appendChild(tooltip);
      this.sidebarTooltipEl = tooltip;
    }

    const tooltip = this.sidebarTooltipEl;
    tooltip.textContent = label;
    tooltip.hidden = false;
    tooltip.setAttribute('data-visible', 'true');

    const linkRect = link.getBoundingClientRect();

    const top = linkRect.top + linkRect.height / 2 + window.scrollY;
    const left = linkRect.right + 12 + window.scrollX;

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
  }

  /**
   * Hide tooltip (called on blur, resize, expand).
   */
  hideSidebarTooltip() {
    if (!this.sidebarTooltipEl) return;

    this.sidebarTooltipEl.removeAttribute('data-visible');
    this.sidebarTooltipEl.hidden = true;
  }

  /**
   * Utility: check for collapsed desktop sidebar.
   */
  isSidebarCollapsed(sidebar) {
    if (!sidebar) return false;
    const isMobile = window.innerWidth < 768;
    return !isMobile && sidebar.classList.contains('collapsed');
  }

  /**
   * Utility: Format dates
   */
  formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('de-DE', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  /**
   * Utility: Debounce function
   */
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
}

// CSS for animations (injected once)
if (!document.querySelector('#gustav-animations')) {
  const style = document.createElement('style');
  style.id = 'gustav-animations';
  style.textContent = `
    @keyframes slideIn {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }

    @keyframes slideOut {
      from {
        transform: translateX(0);
        opacity: 1;
      }
      to {
        transform: translateX(100%);
        opacity: 0;
      }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}

// Initialize GUSTAV
const gustav = new Gustav();

// Expose to global scope for HTML onclick handlers
window.gustav = gustav;
