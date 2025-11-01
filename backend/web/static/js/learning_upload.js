// Learning Uploads: toggle fields and client-side upload intents (MVP)
//
// Intent:
//  - Keep SSR-first. JS enhances UX: shows correct fields and, for image/PDF,
//    obtains an upload-intent, uploads the file to the presigned URL, then
//    completes the SSR form submission with hidden fields.
//  - No previews. A success banner is shown by the PRG target page.
//
// Security:
//  - Same-origin requests for the intent API (credentials include session).
//  - Client validations mirror server allowlists but do not replace them.

(function () {
  function onReady(fn) {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      setTimeout(fn, 0);
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  function sha256Hex(buffer) {
    return crypto.subtle.digest('SHA-256', buffer).then(function (hash) {
      const bytes = new Uint8Array(hash);
      return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
    });
  }

  function showFields(form, mode) {
    const text = form.querySelector('.fields-text');
    const img = form.querySelector('.fields-image');
    const pdf = form.querySelector('.fields-file');
    if (text) text.hidden = (mode !== 'text');
    if (img) img.hidden = (mode !== 'image');
    if (pdf) pdf.hidden = (mode !== 'file');
  }

  async function handleSubmitWithUpload(e, form, mode) {
    // If hidden fields already populated, let the submission proceed.
    const storageKeyInput = form.querySelector('input[name="storage_key"]');
    const mimeInput = form.querySelector('input[name="mime_type"]');
    const sizeInput = form.querySelector('input[name="size_bytes"]');
    const shaInput = form.querySelector('input[name="sha256"]');
    if (storageKeyInput && storageKeyInput.value && shaInput && shaInput.value) {
      return true; // allow native submit
    }

    // Pick file input based on mode
    const fileInput = mode === 'image'
      ? form.querySelector('input[name="image_file"]')
      : form.querySelector('input[name="doc_file"]');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
      // No file selected: block submit and focus input
      e.preventDefault();
      if (fileInput) fileInput.focus();
      return false;
    }
    const file = fileInput.files[0];
    const courseId = form.getAttribute('data-course-id');
    const taskId = form.getAttribute('data-task-id');
    if (!courseId || !taskId) return true; // fall back to native submit

    // Validate client-side (non-authoritative)
    const isImage = mode === 'image';
    const allowedImage = ['image/png', 'image/jpeg'];
    const allowedPdf = ['application/pdf'];
    if ((isImage && allowedImage.indexOf(file.type) === -1) || (!isImage && allowedPdf.indexOf(file.type) === -1)) {
      e.preventDefault();
      return false;
    }
    const maxBytes = 10 * 1024 * 1024;
    if (file.size <= 0 || file.size > maxBytes) {
      e.preventDefault();
      return false;
    }

    // Compute sha256
    const buf = await file.arrayBuffer();
    const sha = await sha256Hex(buf);

    // Request upload intent
    const intentResp = await fetch(`/api/learning/courses/${courseId}/tasks/${taskId}/upload-intents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ kind: isImage ? 'image' : 'file', filename: file.name || '', mime_type: file.type, size_bytes: file.size })
    });
    if (!intentResp.ok) {
      e.preventDefault();
      return false;
    }
    const intent = await intentResp.json();
    const url = intent.url;
    const headers = intent.headers || { 'Content-Type': file.type };
    // Upload to storage
    const putResp = await fetch(url, { method: 'PUT', headers: headers, body: file });
    if (!putResp.ok) {
      e.preventDefault();
      return false;
    }
    // Fill hidden fields and proceed with SSR submit
    if (storageKeyInput) storageKeyInput.value = intent.storage_key || '';
    if (mimeInput) mimeInput.value = file.type;
    if (sizeInput) sizeInput.value = String(file.size);
    if (shaInput) shaInput.value = sha;
    return true;
  }

  onReady(function () {
    document.querySelectorAll('form.task-submit-form').forEach(function (form) {
      // Toggle fields on radio change
      const radios = form.querySelectorAll('input[name="mode"]');
      radios.forEach(function (r) {
        r.addEventListener('change', function () {
          showFields(form, r.value);
        });
      });
      // Initialize visibility
      const checked = form.querySelector('input[name="mode"]:checked');
      showFields(form, checked ? checked.value : 'text');

      // Intercept submit for image/file
      form.addEventListener('submit', async function (e) {
        const selected = form.querySelector('input[name="mode"]:checked');
        const mode = selected ? selected.value : 'text';
        if (mode === 'text') return; // let it pass
        const ok = await handleSubmitWithUpload(e, form, mode);
        if (!ok) return; // prevent submit in error cases
      });
    });
  });
})();

