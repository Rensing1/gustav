import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.stubGlobal("__SVELTEKIT_PAYLOAD__", { base: "", assets: "" });
vi.stubGlobal("__SVELTEKIT_PATHS__", { base: "", assets: "" });
vi.stubGlobal("__SVELTEKIT_APP_DIR__", "_app");
