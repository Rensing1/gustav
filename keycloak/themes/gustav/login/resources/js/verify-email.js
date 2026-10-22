/* Scope the deadline to this realm and authentication tab, not to a user.
 * Storage may be unavailable; server enforcement still protects every request.
 */
function cooldownKey(panel) {
  const form = panel.querySelector('[data-verification-resend]');
  if (!form) return null;
  const url = new URL(form.action, location.href);
  const tab = url.searchParams.get('tab_id');
  const client = url.searchParams.get('client_id');
  if (!tab || !client) return null;
  return 'gustav:verify-cooldown:' + JSON.stringify([url.origin, url.pathname, client, tab]);
}

function saveDeadline(panel, deadline) {
  try {
    const key = cooldownKey(panel);
    if (!key) return;
    if (deadline) sessionStorage.setItem(key, String(deadline));
    else sessionStorage.removeItem(key);
  } catch { /* Private browsing or storage policy must not break the form. */ }
}

function restoreCountdown(panel) {
  if (panel.querySelector('[data-verification-error]')) {
    startResendCountdown(panel);
    return;
  }
  try {
    const key = cooldownKey(panel);
    const deadline = key ? Number(sessionStorage.getItem(key)) : 0;
    if (!Number.isSafeInteger(deadline) || deadline <= Date.now()) {
      saveDeadline(panel, null);
      return;
    }
    const error = document.createElement('div');
    error.className = 'kc-message kc-error';
    error.dataset.verificationError = '';
    error.textContent = panel.dataset.cooldownTemplate.replace('{seconds}', String(Math.ceil((deadline - Date.now()) / 1000)));
    panel.querySelector('h1').after(error);
    startResendCountdown(panel, deadline);
  } catch { /* Keep the server-rendered form usable without browser storage. */ }
}

/* Enhance only the exact localized cooldown message returned by Keycloak.
 * A deadline avoids extending the wait when background tabs throttle timers.
 */
function startResendCountdown(panel, restoredDeadline = null) {
  const error = panel.querySelector('[data-verification-error]');
  const button = panel.querySelector('[data-verification-resend] button');
  const template = panel.dataset.cooldownTemplate || '';
  const parts = template.split('{seconds}');
  if (!error || !button || parts.length !== 2) return false;
  const message = error.textContent.trim();
  if (!message.startsWith(parts[0]) || !message.endsWith(parts[1])) return false;
  const value = message.slice(parts[0].length, message.length - parts[1].length);
  if (!/^\d+$/.test(value)) return false;
  const seconds = Number(value);
  if (!Number.isSafeInteger(seconds) || seconds <= 0) return false;
  const deadline = restoredDeadline ?? (Date.now() + seconds * 1000);
  saveDeadline(panel, deadline);
  button.disabled = true;
  // Do not announce a changing number every second to screen readers.
  error.setAttribute('role', 'timer');
  error.setAttribute('aria-live', 'off');
  const update = () => {
    if (!panel.isConnected) { clearInterval(timer); return; }
    const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    if (remaining === 0) {
      clearInterval(timer);
      saveDeadline(panel, null);
      error.remove();
      button.disabled = false;
      return;
    }
    error.textContent = template.replace('{seconds}', String(remaining));
  };
  const timer = setInterval(update, 250);
  update();
  return true;
}

const initialPanel = document.querySelector('[data-verification-wait]');
if (initialPanel) restoreCountdown(initialPanel);

/* Show resend feedback only after Keycloak returns the expected page without errors.
 * The native POST form remains available when JavaScript is disabled.
 */
document.addEventListener('submit', async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.matches('[data-verification-resend]')) return;
  event.preventDefault();
  const panel = form.closest('[data-verification-wait]');
  const button = form.querySelector('button');
  const status = panel.querySelector('[data-resend-status]');
  if (button.disabled) return;
  saveDeadline(panel, null);
  button.disabled = true;
  status.hidden = true;
  status.textContent = '';
  panel.querySelectorAll('[data-verification-error]').forEach(error => error.remove());
  try {
    const response = await fetch(form.action, {
      method: 'POST', credentials: 'same-origin', body: new FormData(form),
    });
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const next = page.querySelector('[data-verification-wait]');
    if (response.ok && next) {
      // Preserve fresh action URLs and any server-provided cooldown message.
      const replacement = document.importNode(next, true);
      panel.replaceWith(replacement);
      if (!replacement.querySelector('[data-verification-error]')) {
        const notice = replacement.querySelector('[data-resend-status]');
        notice.textContent = replacement.dataset.resendSuccess;
        notice.hidden = false;
      }
      if (startResendCountdown(replacement)) {
        const error = replacement.querySelector('[data-verification-error]');
        error.setAttribute('tabindex', '-1');
        error.focus();
      } else {
        replacement.querySelector('button')?.focus();
      }
      return;
    }
    // A mail or session failure may return a separate error page. Do not retry
    // its URL automatically: that could repeat a side effect.
    const error = page.querySelector('[role="alert"], .kc-error');
    status.textContent = error?.textContent?.trim() || panel.dataset.resendFailure;
    status.hidden = false;
  } catch {
    status.textContent = panel.dataset.resendFailure;
    status.hidden = false;
  } finally {
    button.disabled = false;
  }
});
