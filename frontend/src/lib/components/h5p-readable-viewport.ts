/** Derive real canvas width without changing H5P's em-based answer geometry. */
export function readableRenderWidth(currentWidth: number, fontSizes: number[], availableWidth: number): number {
  const sizes = fontSizes.filter((size) => Number.isFinite(size) && size > 0);
  const scale = sizes.length ? 16 / Math.min(...sizes) : 1;
  return Math.ceil(Math.max(availableWidth, currentWidth * scale));
}

/** Reveal the focused answer inside its own scroll region, never pan the page. */
export function keepFocusVisible(region: HTMLElement, target: HTMLElement): void {
  const area = region.getBoundingClientRect(), item = target.getBoundingClientRect();
  const margin = 8;
  if (item.right > area.right - margin) region.scrollLeft += item.right - area.right + margin;
  else if (item.left < area.left + margin) region.scrollLeft += item.left - area.left - margin;
  if (item.bottom > area.bottom - margin) region.scrollTop += item.bottom - area.bottom + margin;
  else if (item.top < area.top + margin) region.scrollTop += item.top - area.top - margin;
}

/** Presentation-only controls. H5P remains the owner of dragging and scoring. */
export function createReadableViewport(stage: HTMLElement, region: HTMLElement, resize: () => void) {
  let mode: "readable" | "overview" | "zoom" = "readable";
  let readableWidth = region.clientWidth;
  let frame = 0;
  let destroyed = false;
  const measureFonts = () => [...stage.querySelectorAll<HTMLElement>(
    ".h5p-dragquestion .h5p-draggable p, .h5p-dragquestion .h5p-label"
  )].filter((element) => element.getClientRects().length).map((element) => parseFloat(getComputedStyle(element).fontSize));
  const render = (width: number) => {
    stage.style.width = `${Math.ceil(width)}px`;
    resize();
  };
  const readable = (remaining = 3) => {
    if (destroyed) return;
    const fonts = measureFonts();
    readableWidth = readableRenderWidth(stage.getBoundingClientRect().width, fonts, region.clientWidth);
    render(readableWidth);
    // Library resize and browser layout settle on the next frame. Account for
    // fixed wrapper padding without modifying any answer's own font or size.
    if (remaining > 0) frame = requestAnimationFrame(() => {
      if (mode === "readable" && measureFonts().some((size) => size < 16)) readable(remaining - 1);
    });
  };
  const choose = (next: "readable" | "overview") => {
    mode = next;
    cancelAnimationFrame(frame);
    if (next === "overview") render(region.clientWidth);
    else readable();
  };
  const focus = (event: FocusEvent) => {
    if (event.target instanceof HTMLElement) keepFocusVisible(region, event.target);
  };
  region.addEventListener("focusin", focus);
  let previousAvailableWidth = region.clientWidth;
  const observer = new ResizeObserver(() => {
    if (region.clientWidth === previousAvailableWidth) return;
    previousAvailableWidth = region.clientWidth;
    if (mode !== "zoom") choose(mode);
  });
  observer.observe(region);
  void document.fonts.ready.then(() => { if (!destroyed) choose("readable"); });
  return {
    choose,
    zoom(factor: number) {
      mode = "zoom";
      cancelAnimationFrame(frame);
      render(Math.max(region.clientWidth, Math.min(readableWidth * 4, stage.getBoundingClientRect().width * factor)));
    },
    destroy() {
      destroyed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      region.removeEventListener("focusin", focus);
      stage.style.removeProperty("width");
    }
  };
}
