import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import { buildWarningGate, handleBuildWarning } from "./tooling/build-warning-gate";

export default defineConfig({
  plugins: [sveltekit(), buildWarningGate()],
  build: {
    // Keep Vite 6's other browser targets and explicitly retain Safari 15.3.1.
    target: ["es2020", "chrome87", "edge88", "firefox78", "safari15.3"],
    rollupOptions: {
      onwarn: handleBuildWarning,
      // The H5P sidecar serves these webcomponents at runtime behind `/h5p/*`.
      external: (id) => id.startsWith("/h5p/webcomponents/")
    }
  }
});
