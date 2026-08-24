import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        /**
         * Split the dependencies away from the app.
         *
         * Leaflet and its React bindings are a third of the bundle and matter
         * only once a trip comes back, so they no longer sit in front of the
         * first paint. Splitting MUI and the rest of the vendor code out as
         * well means editing this app leaves the cached copies alone.
         */
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("leaflet")) return "leaflet";
          if (id.includes("@mui")) return "mui";
          return "vendor";
        },
      },
    },
  },
});
