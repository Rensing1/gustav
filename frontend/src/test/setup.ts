import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.stubGlobal("__SVELTEKIT_PAYLOAD__", { base: "", assets: "" });
vi.stubGlobal("__SVELTEKIT_PATHS__", { base: "", assets: "" });
vi.stubGlobal("__SVELTEKIT_APP_DIR__", "_app");

// jsdom does not implement media queries. Components should still exercise
// the same listener lifecycle that browsers provide.
if (typeof window !== "undefined") {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(() => true)
    })
  });
}

class TestResizeObserver implements ResizeObserver {
  disconnect = vi.fn();
  observe = vi.fn();
  unobserve = vi.fn();
}

Object.defineProperty(globalThis, "ResizeObserver", {
  configurable: true,
  writable: true,
  value: TestResizeObserver
});
