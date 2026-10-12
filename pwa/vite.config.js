import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    // forward /api to Django during development, so the PWA and API share an origin
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "node",
  },
});
