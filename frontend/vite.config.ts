import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import { buildWarningGate, handleBuildWarning } from "./tooling/build-warning-gate";

export default defineConfig({
  plugins: [sveltekit(), buildWarningGate()],
  build: {
    rollupOptions: {
      onwarn: handleBuildWarning,
      // The H5P sidecar serves these webcomponents at runtime behind `/h5p/*`.
      external: (id) => id.startsWith("/h5p/webcomponents/")
    }
  }
});
