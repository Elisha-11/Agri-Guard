import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    VitePWA({
      // The app shell is precached on install, so a farmer who installs the
      // PWA once can open it and run a check with no connection at all.
      // Inference is already on-device (src/inference/diagnose.js), so there
      // is nothing in the check flow that needs the network.
      registerType: "autoUpdate",

      // public/manifest.webmanifest is the source of truth and is already
      // linked from index.html; the plugin must not generate a second one.
      manifest: false,
      injectRegister: null,

      workbox: {
        // Precache the built shell plus the translation bundles, which are
        // fetched at runtime by src/i18n.js and would otherwise be missing
        // offline. The manifest and icons come from public/.
        globPatterns: ["**/*.{js,css,html,svg,png,ico,webmanifest,json}"],

        // Any navigation falls back to the shell: the app is a hash router,
        // so every screen lives at index.html.
        navigateFallback: "index.html",

        // 3 MB: the two leaf photographs bundled as placeholders are ~420 kB
        // together and the default 2 MB limit would silently drop them.
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,

        cleanupOutdatedCaches: true,
        clientsClaim: true,

        runtimeCaching: [
          {
            // The Django API is never served from cache: a stale health check
            // or, later, a stale sync response is worse than a clear failure.
            // See docs/offline-sync.md for the queued-write design.
            urlPattern: ({ url }) => url.pathname.startsWith("/api/"),
            handler: "NetworkOnly",
          },
        ],
      },

      devOptions: {
        // Keep the service worker out of `npm run dev`; a stale precache
        // during development is a well-known source of phantom bugs.
        // Test offline behaviour with `npm run build && npm run preview`.
        enabled: false,
      },
    }),
  ],

  server: {
    port: 5173,
    // forward /api to Django during development, so the PWA and API share an origin
    proxy: { "/api": "http://localhost:8000" },
  },

  test: {
    environment: "node",
  },
});
