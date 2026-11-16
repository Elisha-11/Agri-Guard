/**
 * Differences between the browser PWA and the Android app (Capacitor).
 *
 * In the browser the API is same-origin: Vite proxies /api in development and
 * the PWA is served next to Django in production. Inside the Android app the
 * page origin is https://localhost on the phone itself, so API calls go to the
 * backend's full address instead. CapacitorHttp (capacitor.config.json) sends
 * them as native requests, so the backend needs no CORS entry for the app.
 */

import { SystemBars, SystemBarsStyle } from "@capacitor/core";

export const isNative = Boolean(globalThis.window?.Capacitor?.isNativePlatform?.());

/** Backend for the Android app. Override at build time with VITE_API_BASE. */
const NATIVE_API_BASE = import.meta.env.VITE_API_BASE || "https://agri-guard-staging.onrender.com";

/** `apiUrl("/api/v1/health/")` → a URL that works in the browser and the app. */
export function apiUrl(path) {
  return isNative ? `${NATIVE_API_BASE}${path}` : path;
}

/**
 * Light status-bar icons on a dark screen, dark icons otherwise. Does nothing
 * in the browser, where the page cannot style the system bars.
 */
export function setDarkStatusBar(dark) {
  if (!isNative) return;
  SystemBars.setStyle({ style: dark ? SystemBarsStyle.Dark : SystemBarsStyle.Light }).catch(
    () => {},
  );
}
