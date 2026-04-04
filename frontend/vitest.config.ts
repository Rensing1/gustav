import { sveltekit } from "@sveltejs/kit/vite";
import { svelteTesting } from "@testing-library/svelte/vite";
import { defineConfig } from "vitest/config";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [sveltekit(), svelteTesting()],
  resolve: {
    alias: {
      "$lib/components/H5PTaskPlayer.svelte": path.resolve(rootDir, "src/test/stubs/H5PTaskPlayer.svelte"),
      "$lib/components/learning-unit/MarkdownWysiwygEditor.svelte": path.resolve(
        rootDir,
        "src/test/stubs/MarkdownWysiwygEditor.svelte"
      )
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.ts"]
  }
});
