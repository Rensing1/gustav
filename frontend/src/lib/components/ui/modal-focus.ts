/**
 * Keep keyboard focus in the topmost modal and return it to its live opener.
 * This presentation-only action does not submit forms or change permissions.
 */
export function modalFocus(node: HTMLElement, onClose: () => void) {
  const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  let close = onClose;
  let active = true;
  node.tabIndex = -1;

  function isTopmost(): boolean {
    return Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')).at(-1) === node;
  }

  function focusable(): HTMLElement[] {
    return Array.from(node.querySelectorAll<HTMLElement>('a[href], button, input:not([type="hidden"]), select, textarea, summary, [tabindex]'))
      .filter((element) => !element.matches(':disabled, [tabindex="-1"]')
        && !element.closest('[hidden], [inert]')
        && !(element.closest('details:not([open])') && element.tagName !== "SUMMARY")
        && getComputedStyle(element).display !== "none" && getComputedStyle(element).visibility !== "hidden");
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.defaultPrevented || !isTopmost()) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
    } else if (event.key === "Tab") {
      const elements = focusable();
      const first = elements[0] ?? node;
      const last = elements.at(-1) ?? node;
      if (!node.contains(document.activeElement) || (event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      }
    }
  }

  queueMicrotask(() => {
    if (active && isTopmost()) (node.querySelector<HTMLElement>('[data-modal-initial]') ?? focusable()[0] ?? node).focus();
  });
  node.addEventListener("keydown", handleKeydown);
  window.addEventListener("keydown", handleKeydown);
  return {
    update(nextClose: () => void) { close = nextClose; },
    destroy() {
      active = false;
      node.removeEventListener("keydown", handleKeydown);
      window.removeEventListener("keydown", handleKeydown);
      if (opener?.isConnected) opener.focus();
    }
  };
}
