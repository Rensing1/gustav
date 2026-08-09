/**
 * Move keyboard and visual focus to the recovery point of a failed action.
 *
 * Field errors take precedence because correcting the first invalid value is
 * usually the shortest recovery path. The message itself is the fallback for
 * errors that concern a complete upload or server action.
 */
export function focusActionError(message: HTMLElement, invalidField?: HTMLElement | null): void {
  const target = invalidField ?? message;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

  target.focus({ preventScroll: true });
  target.scrollIntoView?.({
    behavior: reducedMotion ? "auto" : "smooth",
    block: "center"
  });
}
