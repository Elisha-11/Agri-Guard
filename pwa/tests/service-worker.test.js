/**
 * Guards the offline precache.
 *
 * The app makes exactly two runtime network requests: the translation bundle
 * (src/i18n.js) and the API health check (src/screens/settings.js). The first
 * must be precached or the app comes up untranslated offline; the second must
 * never be cached, because a stale API answer is worse than a clear failure.
 *
 * These assertions run against the generated service worker, so they only
 * mean anything after a build. They skip with a note otherwise rather than
 * failing a plain `npm test`.
 */

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const swPath = fileURLToPath(new URL("../dist/sw.js", import.meta.url));
const built = existsSync(swPath);
const sw = built ? readFileSync(swPath, "utf8") : "";

describe.skipIf(!built)("service worker precache (run `npm run build` first)", () => {
  it("precaches the app shell", () => {
    expect(sw).toContain("index.html");
    expect(sw).toContain("manifest.webmanifest");
    expect(sw).toContain("icons/icon-192.png");
    expect(sw).toContain("icons/icon-512.png");
  });

  it("precaches every translation bundle i18n.js can ask for", () => {
    for (const code of ["en", "bem", "ny", "toi"]) {
      expect(sw, `locale "${code}" is missing from the precache`).toContain(
        `locales/${code}/translation.json`,
      );
    }
  });

  it("precaches the bundled leaf photographs used as placeholders", () => {
    expect(sw).toMatch(/assets\/capture-preview-[\w-]+\.png/);
    expect(sw).toMatch(/assets\/result-photo-[\w-]+\.png/);
  });

  it("never serves the API from cache", () => {
    expect(sw).toContain("NetworkOnly");
  });

  it("falls back to the shell for navigations, since routing is hash-based", () => {
    expect(sw).toContain("index.html");
    expect(sw).toMatch(/createHandlerBoundToURL|navigationRoute|NavigationRoute/);
  });
});

describe.skipIf(built)("service worker precache", () => {
  it("is only checked after a build", () => {
    expect(built).toBe(false);
  });
});
