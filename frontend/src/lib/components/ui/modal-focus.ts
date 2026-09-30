/**
 * Isolate siblings along the modal's ancestor path, even without inert.
 * Pass the modal's outer wrapper (including its backdrop). The returned cleanup
 * restores each previous attribute and inline style; no permissions change.
 */
export function isolateModalBackground(node: HTMLElement): () => void {
  const saved: Array<{
    element: HTMLElement;
    ariaHidden: string | null;
    pointerEvents: string;
    priority: string;
    inert: boolean;
  }> = [];
  let current = node;
  while (current.parentElement) {
    const parent = current.parentElement;
    for (const sibling of parent.children) {
      if (sibling === current || !(sibling instanceof HTMLElement)) continue;
      saved.push({
        element: sibling,
        ariaHidden: sibling.getAttribute("aria-hidden"),
        pointerEvents: sibling.style.getPropertyValue("pointer-events"),
        priority: sibling.style.getPropertyPriority("pointer-events"),
        inert: sibling.inert === true
      });
      sibling.setAttribute("aria-hidden", "true");
      sibling.style.setProperty("pointer-events", "none", "important");
      if ("inert" in sibling) sibling.inert = true;
    }
    if (parent === document.body) break;
    current = parent;
  }
  return () => {
    for (const { element, ariaHidden, pointerEvents, priority, inert } of saved) {
      if (ariaHidden === null) element.removeAttribute("aria-hidden");
      else element.setAttribute("aria-hidden", ariaHidden);
      if (pointerEvents) element.style.setProperty("pointer-events", pointerEvents, priority);
      else element.style.removeProperty("pointer-events");
      if ("inert" in element) element.inert = inert;
    }
  };
}

/**
 * Keep keyboard focus in the topmost modal and return it to its live opener.
 * This presentation-only action does not submit forms or change permissions.
 */
export function modalFocus(node: HTMLElement, onClose: () => void) {
  const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  let close = onClose;
  let active = true;
  let restoreBackground = () => {};
  node.tabIndex = -1;

  function isTopmost(): boolean {
    return Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]'))
      .filter((dialog) => !dialog.closest('[aria-hidden="true"]')).at(-1) === node;
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
    if (active && isTopmost()) {
      focusInitial();
      // Backdrop dismissal belongs to the modal, not to the page background.
      restoreBackground = isolateModalBackground(node.closest<HTMLElement>(".dialog-backdrop, .workspace-modal") ?? node);
    }
  });
  function focusInitial() {
    (node.querySelector<HTMLElement>('[data-modal-initial]') ?? focusable()[0] ?? node).focus();
  }
  function handleFocus(event: FocusEvent) {
    if (active && isTopmost() && !node.contains(event.target as Node)) focusInitial();
  }
  node.addEventListener("keydown", handleKeydown);
  window.addEventListener("keydown", handleKeydown);
  document.addEventListener("focusin", handleFocus);
  return {
    update(nextClose: () => void) { close = nextClose; },
    destroy() {
      active = false;
      node.removeEventListener("keydown", handleKeydown);
      window.removeEventListener("keydown", handleKeydown);
      document.removeEventListener("focusin", handleFocus);
      restoreBackground();
      if (opener?.isConnected) opener.focus();
    }
  };
}
