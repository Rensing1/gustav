<script lang="ts">
  import { onMount } from "svelte";

  import {
    clampTaskColumnRatio,
    MAX_TASK_COLUMN_RATIO,
    MIN_TASK_COLUMN_RATIO
  } from "$lib/learning-unit/task-column-preference";

  let {
    value = null,
    onPreview,
    onCommit
  }: {
    value?: number | null;
    onPreview: (value: number) => void;
    onCommit: (value: number) => void;
  } = $props();

  const TOUCH_DRAG_THRESHOLD_PX = 8;

  let divider = $state<HTMLDivElement | null>(null);
  let activePointerId = $state<number | null>(null);
  let pointerStartX = 0;
  let pointerStartY = 0;
  let pointerStartValue = 44;
  let pointerIsDragging = false;
  let currentValue = $state(44);

  $effect(() => {
    if (value !== null && activePointerId === null) {
      currentValue = clampTaskColumnRatio(value);
    }
  });

  function containerRatioFromLayout(): number | null {
    const container = divider?.parentElement;
    const contextPane = divider?.previousElementSibling;
    if (!(contextPane instanceof HTMLElement) || !container) {
      return null;
    }
    const containerWidth = container.getBoundingClientRect().width;
    if (containerWidth <= 0) {
      return null;
    }
    return clampTaskColumnRatio((contextPane.getBoundingClientRect().width / containerWidth) * 100);
  }

  function ratioAt(clientX: number): number {
    const bounds = divider?.parentElement?.getBoundingClientRect();
    if (!Number.isFinite(clientX) || !bounds || bounds.width <= 0) {
      return currentValue;
    }
    return clampTaskColumnRatio(((clientX - bounds.left) / bounds.width) * 100);
  }

  function preview(next: number) {
    currentValue = clampTaskColumnRatio(next);
    onPreview(currentValue);
  }

  function commit(next: number) {
    preview(next);
    onCommit(currentValue);
  }

  function capturePointer(event: PointerEvent) {
    if (!(event.currentTarget instanceof HTMLElement)) {
      return;
    }
    try {
      event.currentTarget.setPointerCapture?.(event.pointerId);
    } catch {
      // Synthetic events and older engines may not expose an active pointer to capture.
    }
  }

  function clearPointerInteraction() {
    activePointerId = null;
    pointerIsDragging = false;
  }

  function handlePointerDown(event: PointerEvent) {
    if (activePointerId !== null || (event.pointerType === "mouse" && event.button !== 0)) {
      return;
    }

    activePointerId = event.pointerId;
    pointerStartX = event.clientX;
    pointerStartY = event.clientY;
    pointerStartValue = currentValue;
    pointerIsDragging = event.pointerType === "mouse";

    if (pointerIsDragging) {
      event.preventDefault();
      capturePointer(event);
      preview(ratioAt(event.clientX));
    }
  }

  function handlePointerMove(event: PointerEvent) {
    if (activePointerId !== event.pointerId) {
      return;
    }

    if (!pointerIsDragging) {
      const horizontalDistance = Math.abs(event.clientX - pointerStartX);
      const verticalDistance = Math.abs(event.clientY - pointerStartY);

      // Leave a clearly vertical gesture to the browser instead of turning it into a resize.
      if (verticalDistance >= TOUCH_DRAG_THRESHOLD_PX && verticalDistance > horizontalDistance) {
        clearPointerInteraction();
        return;
      }
      if (horizontalDistance < TOUCH_DRAG_THRESHOLD_PX || horizontalDistance <= verticalDistance) {
        return;
      }

      pointerIsDragging = true;
      capturePointer(event);
    }

    event.preventDefault();
    preview(ratioAt(event.clientX));
  }

  function releasePointer(event: PointerEvent) {
    if (!(event.currentTarget instanceof HTMLElement)) {
      return;
    }
    try {
      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    } catch {
      // Losing capture is harmless because the latest preview remains valid.
    }
  }

  function finishPointerDrag(event: PointerEvent) {
    if (activePointerId !== event.pointerId) {
      return;
    }

    if (!pointerIsDragging) {
      clearPointerInteraction();
      return;
    }

    event.preventDefault();
    const next = ratioAt(event.clientX);
    clearPointerInteraction();
    releasePointer(event);
    commit(next);
  }

  function cancelPointerDrag(event: PointerEvent) {
    if (activePointerId !== event.pointerId) {
      return;
    }
    const restoreValue = pointerStartValue;
    const restorePreview = pointerIsDragging;
    clearPointerInteraction();
    releasePointer(event);
    if (restorePreview) {
      preview(restoreValue);
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    let next: number | null = null;
    const step = event.shiftKey ? 5 : 1;
    if (event.key === "ArrowLeft") next = currentValue - step;
    if (event.key === "ArrowRight") next = currentValue + step;
    if (event.key === "Home") next = MIN_TASK_COLUMN_RATIO;
    if (event.key === "End") next = MAX_TASK_COLUMN_RATIO;
    if (next === null) {
      return;
    }
    event.preventDefault();
    commit(next);
  }

  onMount(() => {
    if (value !== null) {
      return;
    }
    const measure = () => {
      if (activePointerId !== null) return;
      currentValue = containerRatioFromLayout() ?? currentValue;
    };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    if (divider?.parentElement) observer?.observe(divider.parentElement);
    return () => observer?.disconnect();
  });
</script>

<!-- A focusable ARIA separator is an adjustable widget, despite being represented by a div. -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
  bind:this={divider}
  class="learner-task-split-divider"
  role="separator"
  tabindex="0"
  aria-label="Spaltenbreite anpassen"
  aria-orientation="vertical"
  aria-valuemin={MIN_TASK_COLUMN_RATIO}
  aria-valuemax={MAX_TASK_COLUMN_RATIO}
  aria-valuenow={currentValue}
  aria-valuetext={`Kontextspalte ${currentValue} Prozent`}
  onkeydown={handleKeyDown}
  onpointerdown={handlePointerDown}
  onpointermove={handlePointerMove}
  onpointerup={finishPointerDrag}
  onpointercancel={cancelPointerDrag}
  onlostpointercapture={cancelPointerDrag}
>
  <span class="learner-task-split-divider__grip" aria-hidden="true"></span>
</div>

<style>
  .learner-task-split-divider {
    position: relative;
    z-index: 4;
    width: 1px;
    min-width: 1px;
    height: 100%;
    padding: 0;
    border: 0;
    border-radius: 0;
    align-self: stretch;
    background: var(--color-border);
    cursor: col-resize;
    touch-action: pan-y;
  }

  .learner-task-split-divider::before {
    content: "";
    position: absolute;
    inset-block: 0;
    inset-inline-start: 50%;
    width: 12px;
    transform: translateX(-50%);
  }

  .learner-task-split-divider__grip {
    position: absolute;
    inset-block-start: 50%;
    inset-inline-start: 50%;
    width: 44px;
    height: 44px;
    transform: translate(-50%, -50%);
    touch-action: pan-y;
  }

  .learner-task-split-divider__grip::after {
    content: "";
    position: absolute;
    inset-block-start: 50%;
    inset-inline-start: 50%;
    width: 0.32rem;
    height: 3rem;
    border-radius: 999px;
    background: var(--color-text-muted);
    transform: translate(-50%, -50%);
  }

  .learner-task-split-divider:hover .learner-task-split-divider__grip::after,
  .learner-task-split-divider:focus-visible .learner-task-split-divider__grip::after {
    background: var(--color-accent);
  }

  .learner-task-split-divider:focus-visible {
    outline: 2px solid var(--color-focus-ring);
    outline-offset: 4px;
  }

  @media (any-pointer: coarse) {
    .learner-task-split-divider::before {
      display: none;
    }
  }
</style>
