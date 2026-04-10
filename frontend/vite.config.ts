import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  build: {
    rollupOptions: {
      // The H5P sidecar serves these webcomponents at runtime behind `/h5p/*`.
      external: (id) => id.startsWith("/h5p/webcomponents/")
    }
  }
});
