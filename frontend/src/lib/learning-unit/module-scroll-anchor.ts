/** Keep a restored module aligned while preceding materials acquire their final height.
 * Stop immediately on user intent so late content never fights manual navigation.
 * The caller owns cleanup when the workspace changes or unmounts.
 */
export function anchorRestoredModule(target: HTMLElement): () => void {
  let frame = 0;
  let stopped = false;
  const align = () => {
    frame = 0;
    if (stopped || !target.isConnected) return;
    const header = document.querySelector(".global-header");
    const top = (header?.getBoundingClientRect().height ?? 64) + 16;
    const delta = target.getBoundingClientRect().top - top;
    if (Math.abs(delta) > 1) window.scrollBy({ top: delta, behavior: "instant" });
  };
  const schedule = () => {
    if (!stopped && !frame) frame = requestAnimationFrame(align);
  };
  const observer = new ResizeObserver(schedule);
  const stop = () => {
    stopped = true;
    cancelAnimationFrame(frame);
    observer.disconnect();
    for (const event of ["wheel", "touchstart", "pointerdown", "keydown"] as const) {
      window.removeEventListener(event, stop, true);
    }
  };
  // Observe every preceding module as well as their common content container.
  const content = target.closest(".learner-orientation__content");
  if (content) {
    observer.observe(content);
    for (const child of content.children) observer.observe(child);
  }
  for (const event of ["wheel", "touchstart", "pointerdown", "keydown"] as const) {
    window.addEventListener(event, stop, { capture: true, passive: true });
  }
  schedule();
  return stop;
}
