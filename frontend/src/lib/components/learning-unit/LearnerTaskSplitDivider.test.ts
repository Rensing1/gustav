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
  type: "pointerdown" | "pointermove" | "pointerup" | "pointercancel",
  init: { pointerId: number; pointerType: string; clientX: number }
) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  for (const [key, value] of Object.entries(init)) {
    Object.defineProperty(event, key, { configurable: true, value });
  }
  return fireEvent(target, event);
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

  it("previews touch movement and commits the final pointer position", async () => {
    const { separator, onPreview, onCommit } = renderDivider();

    await dispatchPointer(separator, "pointerdown", { pointerId: 7, pointerType: "touch", clientX: 540 });
    await dispatchPointer(separator, "pointermove", { pointerId: 7, pointerType: "touch", clientX: 700 });
    expect(onPreview).toHaveBeenLastCalledWith(60);

    await dispatchPointer(separator, "pointerup", { pointerId: 7, pointerType: "touch", clientX: 700 });
    expect(onCommit).toHaveBeenLastCalledWith(60);
  });

  it("keeps the last usable preview when the browser cancels a touch gesture", async () => {
    const { separator, onCommit } = renderDivider();

    await dispatchPointer(separator, "pointerdown", { pointerId: 8, pointerType: "touch", clientX: 540 });
    await dispatchPointer(separator, "pointermove", { pointerId: 8, pointerType: "touch", clientX: 700 });
    await dispatchPointer(separator, "pointercancel", { pointerId: 8, pointerType: "touch", clientX: 0 });

    expect(onCommit).toHaveBeenLastCalledWith(60);
  });
});
