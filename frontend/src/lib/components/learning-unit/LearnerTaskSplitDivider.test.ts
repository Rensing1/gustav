import { readFileSync } from "node:fs";
import path from "node:path";

import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import LearnerTaskSplitDivider from "./LearnerTaskSplitDivider.svelte";

function renderDivider(value = 44) {
  const onPreview = vi.fn();
  const onCommit = vi.fn();
  const result = render(LearnerTaskSplitDivider, {
    props: { value, onPreview, onCommit }
  });
  const separator = screen.getByRole("separator", { name: "Spaltenbreite anpassen" });
  Object.defineProperty(separator.parentElement, "getBoundingClientRect", {
    configurable: true,
    value: () => ({ left: 100, right: 1100, top: 0, bottom: 700, width: 1000, height: 700, x: 100, y: 0, toJSON: () => ({}) })
  });
  return { ...result, separator, onPreview, onCommit };
}

function dispatchPointer(
  target: HTMLElement,
  type: "pointerdown" | "pointermove" | "pointerup" | "pointercancel" | "lostpointercapture",
  init: { pointerId: number; pointerType: string; clientX: number; clientY?: number; button?: number }
) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  for (const [key, value] of Object.entries({ clientY: 0, button: 0, ...init })) {
    Object.defineProperty(event, key, { configurable: true, value });
  }
  fireEvent(target, event);
  return event;
}

describe("LearnerTaskSplitDivider", () => {
  it("exposes the bounded column ratio as an accessible vertical separator", () => {
    const { separator } = renderDivider(44);

    expect(separator).toHaveAttribute("aria-orientation", "vertical");
    expect(separator).toHaveAttribute("aria-valuemin", "35");
    expect(separator).toHaveAttribute("aria-valuemax", "65");
    expect(separator).toHaveAttribute("aria-valuenow", "44");
    expect(separator).toHaveAttribute("tabindex", "0");
  });

  it("supports precise and accelerated keyboard changes plus both boundaries", async () => {
    const { separator, onPreview, onCommit } = renderDivider(44);

    await fireEvent.keyDown(separator, { key: "ArrowRight" });
    expect(onPreview).toHaveBeenLastCalledWith(45);
    expect(onCommit).toHaveBeenLastCalledWith(45);

    await fireEvent.keyDown(separator, { key: "ArrowLeft", shiftKey: true });
    expect(onPreview).toHaveBeenLastCalledWith(40);
    expect(onCommit).toHaveBeenLastCalledWith(40);

    await fireEvent.keyDown(separator, { key: "Home" });
    expect(onCommit).toHaveBeenLastCalledWith(35);

    await fireEvent.keyDown(separator, { key: "End" });
    expect(onCommit).toHaveBeenLastCalledWith(65);
  });

  it.each(["touch", "pen"])("keeps vertical %s gestures available for native scrolling", async (pointerType) => {
    const { separator, onPreview, onCommit } = renderDivider();
    const setPointerCapture = vi.fn();
    Object.defineProperty(separator, "setPointerCapture", { configurable: true, value: setPointerCapture });

    const down = dispatchPointer(separator, "pointerdown", { pointerId: 7, pointerType, clientX: 540, clientY: 200 });
    const move = dispatchPointer(separator, "pointermove", { pointerId: 7, pointerType, clientX: 543, clientY: 230 });
    dispatchPointer(separator, "pointerup", { pointerId: 7, pointerType, clientX: 543, clientY: 230 });

    expect(down.defaultPrevented).toBe(false);
    expect(move.defaultPrevented).toBe(false);
    expect(setPointerCapture).not.toHaveBeenCalled();
    expect(onPreview).not.toHaveBeenCalled();
    expect(onCommit).not.toHaveBeenCalled();
  });

  it.each(["touch", "pen"])("starts a %s resize only after a horizontal eight-pixel gesture", async (pointerType) => {
    const { separator, onPreview, onCommit } = renderDivider();
    const setPointerCapture = vi.fn();
    Object.defineProperty(separator, "setPointerCapture", { configurable: true, value: setPointerCapture });

    const down = dispatchPointer(separator, "pointerdown", { pointerId: 8, pointerType, clientX: 540, clientY: 200 });
    const shortMove = dispatchPointer(separator, "pointermove", { pointerId: 8, pointerType, clientX: 547, clientY: 201 });
    expect(down.defaultPrevented).toBe(false);
    expect(shortMove.defaultPrevented).toBe(false);
    expect(onPreview).not.toHaveBeenCalled();

    const dragMove = dispatchPointer(separator, "pointermove", { pointerId: 8, pointerType, clientX: 700, clientY: 202 });
    expect(dragMove.defaultPrevented).toBe(true);
    expect(setPointerCapture).toHaveBeenCalledWith(8);
    expect(onPreview).toHaveBeenLastCalledWith(60);

    dispatchPointer(separator, "pointerup", { pointerId: 8, pointerType, clientX: 700, clientY: 202 });
    expect(onCommit).toHaveBeenLastCalledWith(60);
  });

  it("starts primary mouse resizing immediately but ignores secondary clicks", async () => {
    const { separator, onPreview, onCommit } = renderDivider();

    dispatchPointer(separator, "pointerdown", { pointerId: 9, pointerType: "mouse", clientX: 540, button: 2 });
    expect(onPreview).not.toHaveBeenCalled();

    const down = dispatchPointer(separator, "pointerdown", { pointerId: 10, pointerType: "mouse", clientX: 600 });
    expect(down.defaultPrevented).toBe(true);
    expect(onPreview).toHaveBeenLastCalledWith(50);

    dispatchPointer(separator, "pointerup", { pointerId: 10, pointerType: "mouse", clientX: 650 });
    expect(onCommit).toHaveBeenLastCalledWith(55);
  });

  it.each(["pointercancel", "lostpointercapture"] as const)("restores the starting width without committing after %s", async (eventType) => {
    const { separator, onPreview, onCommit } = renderDivider(44);

    dispatchPointer(separator, "pointerdown", { pointerId: 11, pointerType: "touch", clientX: 540, clientY: 200 });
    dispatchPointer(separator, "pointermove", { pointerId: 11, pointerType: "touch", clientX: 700, clientY: 202 });
    dispatchPointer(separator, eventType, { pointerId: 11, pointerType: "touch", clientX: 700, clientY: 202 });
    dispatchPointer(separator, "pointerup", { pointerId: 11, pointerType: "touch", clientX: 720, clientY: 202 });

    expect(onPreview).toHaveBeenNthCalledWith(1, 60);
    expect(onPreview).toHaveBeenLastCalledWith(44);
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("keeps the first pointer in control when a second contact appears", () => {
    const { separator, onPreview } = renderDivider();

    dispatchPointer(separator, "pointerdown", { pointerId: 12, pointerType: "touch", clientX: 540, clientY: 200 });
    dispatchPointer(separator, "pointerdown", { pointerId: 13, pointerType: "touch", clientX: 600, clientY: 200 });
    dispatchPointer(separator, "pointermove", { pointerId: 13, pointerType: "touch", clientX: 700, clientY: 202 });
    expect(onPreview).not.toHaveBeenCalled();

    dispatchPointer(separator, "pointermove", { pointerId: 12, pointerType: "touch", clientX: 650, clientY: 202 });
    expect(onPreview).toHaveBeenLastCalledWith(55);
  });

  it("uses pan-y and exposes a dedicated coarse-pointer grip", () => {
    const { separator } = renderDivider();
    const source = readFileSync(
      path.resolve(process.cwd(), "src/lib/components/learning-unit/LearnerTaskSplitDivider.svelte"),
      "utf8"
    );

    expect(separator.querySelector(".learner-task-split-divider__grip")).toBeInTheDocument();
    expect(source).toContain("touch-action: pan-y");
    expect(source).toContain("width: 12px");
    expect(source).toMatch(/@media \(any-pointer: coarse\)[\s\S]*\.learner-task-split-divider::before[\s\S]*display: none/);
    expect(source).not.toMatch(/inset-block: 0;\s+inset-inline-start: 50%;\s+width: 44px/);
  });
});
