/*
 Minimal Sortable integration for GUSTAV
 - Attaches SortableJS to containers marked with hx-ext="sortable"
 - On drag end, posts ordered child ids as application/x-www-form-urlencoded
 - Expects child elements to have stable ids (e.g., section_<uuid>)
*/
(function () {
  function initSortables(root) {
    if (typeof Sortable === 'undefined') return;
    var scope = root || document;
    var nodes = scope.querySelectorAll('[hx-ext~="sortable"]');
    nodes.forEach(function (el) {
      if (el.dataset.sortableReady === 'true') return;
      try {
        new Sortable(el, {
          animation: 150,
          // Allow dragging anywhere in the item for better UX; ignore clicks on actionable elements
          filter: 'button, a, form, input, textarea, select',
          preventOnFilter: false,
          dragoverBubble: true,
          onEnd: function () {
            var url = el.getAttribute('data-reorder-url');
            if (!url) return;
            var ids = Array.from(el.children)
              .map(function (c) { return c.id; })
              .filter(Boolean);
            var body = ids.map(function (id) { return 'id=' + encodeURIComponent(id); }).join('&');
            var headers = {
              'Content-Type': 'application/x-www-form-urlencoded',
              'HX-Request': 'true'
            };
            var csrf = el.dataset.csrfToken || null;
            if (!csrf) {
              var hidden = el.querySelector('input[name="csrf_token"]');
              if (hidden && hidden.value) csrf = hidden.value;
            }
            if (csrf) headers['X-CSRF-Token'] = csrf;
            fetch(url, {
              method: 'POST',
              headers: headers,
              body: body,
              credentials: 'same-origin'
            }).then(function (r) {
              if (!r.ok) {
                r.clone().text().then(function (payload) {
                  var message = 'unknown_error';
                  if (payload) {
                    try {
                      var data = JSON.parse(payload);
                      if (data && typeof data === 'object') {
                        message = data.detail || data.error || payload;
                      } else {
                        message = payload;
                      }
                    } catch (e) {
                      message = payload;
                    }
                  }
                  console.warn('Reorder request failed', r.status, message);
                  if (typeof window !== 'undefined') {
                    window.alert('Reorder failed (' + r.status + '): ' + message);
                  }
                }).catch(function () {
                  console.warn('Reorder request failed', r.status);
                });
              }
            }).catch(function (e) {
              console.warn('Reorder request error', e);
              if (typeof window !== 'undefined') {
                window.alert('Reorder failed: ' + e);
              }
            });
          }
        });
        el.dataset.sortableReady = 'true';
      } catch (e) {
        // no-op; keep UI usable even if Sortable fails
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initSortables(document); });
  } else {
    initSortables(document);
  }

  // Re-init on HTMX swaps
  document.body && document.body.addEventListener && document.body.addEventListener('htmx:afterSwap', function (evt) {
    initSortables(evt && (evt.detail && evt.detail.elt) ? evt.detail.elt : document);
  });
  document.body && document.body.addEventListener && document.body.addEventListener('htmx:oobAfterSwap', function (evt) {
    initSortables(evt && (evt.detail && evt.detail.elt) ? evt.detail.elt : document);
  });
  document.body && document.body.addEventListener && document.body.addEventListener('htmx:afterSettle', function (evt) {
    initSortables(evt && (evt.detail && evt.detail.elt) ? evt.detail.elt : document);
  });
  document.body && document.body.addEventListener && document.body.addEventListener('htmx:load', function (evt) {
    // Fired for new content; ensure local subtree initializes
    initSortables(evt && evt.detail && evt.detail.elt ? evt.detail.elt : document);
  });
})();
