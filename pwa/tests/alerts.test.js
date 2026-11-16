/**
 * Nearby outbreak alerts (src/alerts.js, ADR 0019): the capture-screen card in
 * its online, offline/cached and no-alerts states, the refresh rules (consent,
 * ~1 km rounding, offline keeps the cache), and the post-diagnosis banner.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";

// Node has no localStorage; alerts and advice are cached there on the phone.
const store = new Map();
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, String(value)),
  removeItem: (key) => store.delete(key),
};

const { initI18n, t } = await import("../src/i18n.js");
const { state, session } = await import("../src/state.js");
const alertsModule = await import("../src/alerts.js");
const {
  alertsCardHtml,
  alertsSpeech,
  alertFor,
  cachedAlerts,
  refreshAlerts,
  roundCoord,
  updatedAgo,
} = alertsModule;
const result = await import("../src/screens/result.js");
const advice = await import("../src/screens/advice.js");

const localeUrl = new URL("../public/locales/en/translation.json", import.meta.url);
const HOUR = 60 * 60 * 1000;
const NOW = Date.UTC(2026, 10, 16, 12, 0, 0);

const response = (alerts) => ({
  generated_at: "2026-11-16T12:00:00Z",
  radius_km: 10,
  window_days: 7,
  min_farms: 3,
  alerts,
});
const GLS_ALERT = {
  class_id: "maize__grey_leaf_spot",
  farm_count: 5,
  distance_band_km: 10,
  window_days: 7,
};
const RUST_ALERT = {
  class_id: "maize__common_rust",
  farm_count: 3,
  distance_band_km: 10,
  window_days: 7,
};
const cacheOf = (alerts, ageMs = HOUR) => ({
  fetchedAt: NOW - ageMs,
  area: { lat: -15.4, lng: 28.3 },
  data: response(alerts),
});

beforeAll(async () => {
  globalThis.fetch = async (url) =>
    String(url).includes("/locales/en/")
      ? { ok: true, json: async () => JSON.parse(readFileSync(fileURLToPath(localeUrl), "utf8")) }
      : { ok: false };
  await initI18n("en");
});

beforeEach(() => {
  store.clear();
  state.locationConsent = false;
});

/* ------------------------------------------------------------------- card */

describe("alerts card", () => {
  it("asks before using location, and shows nothing else until then", () => {
    const html = alertsCardHtml({
      consent: false,
      cache: cacheOf([GLS_ALERT]),
      online: true,
      now: NOW,
    });
    expect(html).toContain(t("alerts.enable"));
    expect(html).toContain('id="ag-alerts-enable"');
    expect(html).not.toContain("Grey Leaf Spot");
  });

  it("online: lists active alerts with counts, radius, window and when it was updated", () => {
    const html = alertsCardHtml({
      consent: true,
      cache: cacheOf([GLS_ALERT, RUST_ALERT]),
      online: true,
      now: NOW,
    });
    expect(html).toContain(t("alerts.title"));
    expect(html).toContain("Maize Grey Leaf Spot: 5 farms within 10 km in the last 7 days");
    expect(html).toContain("Maize Common Rust: 3 farms within 10 km in the last 7 days");
    expect(html).toContain('data-alert="maize__grey_leaf_spot"');
    expect(html).toContain("Updated 60 minutes ago");
    expect(html).not.toContain(t("alerts.offline"));
  });

  it("offline: still shows the cached alerts, marked offline with the last update time", () => {
    const html = alertsCardHtml({
      consent: true,
      cache: cacheOf([GLS_ALERT], 5 * HOUR),
      online: false,
      now: NOW,
    });
    expect(html).toContain("Maize Grey Leaf Spot: 5 farms");
    expect(html).toContain(`Updated 5 hours ago · ${t("alerts.offline")}`);
  });

  it("no alerts: says so for the configured radius and window", () => {
    const html = alertsCardHtml({ consent: true, cache: cacheOf([]), online: true, now: NOW });
    expect(html).toContain("No disease alerts within 10 km in the last 7 days.");
    expect(html).not.toContain("data-alert");
  });

  it("never fetched: explains, online or offline", () => {
    expect(alertsCardHtml({ consent: true, cache: null, online: true, now: NOW })).toContain(
      t("alerts.loading"),
    );
    expect(alertsCardHtml({ consent: true, cache: null, online: false, now: NOW })).toContain(
      t("alerts.neverFetchedOffline"),
    );
  });

  it("server reachable but without alerts: says they are not available yet", async () => {
    state.locationConsent = true;
    await refreshAlerts({
      position: async () => ({ lat: -15.4, lng: 28.3 }),
      fetchImpl: async () => ({ ok: false, status: 404 }),
    });
    expect(alertsModule.alertsUnavailable()).toBe(true);
    const html = alertsCardHtml({
      consent: true,
      cache: null,
      online: true,
      unavailable: true,
      now: NOW,
    });
    expect(html).toContain(t("alerts.unavailable"));
  });

  it("shows two alerts and summarises the rest", () => {
    const third = { ...RUST_ALERT, class_id: "soybean__rust" };
    const html = alertsCardHtml({
      consent: true,
      cache: cacheOf([GLS_ALERT, RUST_ALERT, third]),
      online: true,
      now: NOW,
    });
    expect(html).not.toContain("Soybean Rust");
    expect(html).toContain("and 1 more");
  });

  it("is readable aloud", () => {
    expect(alertsSpeech(cacheOf([GLS_ALERT]))).toEqual([
      t("alerts.title"),
      "Maize Grey Leaf Spot: 5 farms within 10 km in the last 7 days",
    ]);
  });

  it("uses the published disease name when the advisory has one, and never advice text", () => {
    localStorage.setItem(
      "agriguard.advisory.en",
      JSON.stringify({
        etag: '"t"',
        bundle: {
          diseases: [
            {
              class_id: "maize__grey_leaf_spot",
              name: "Fixture Published Name",
              treatment: { title: "FIXTURE TREATMENT", steps: ["FIXTURE STEP"] },
            },
          ],
          ui: {},
        },
      }),
    );
    const html = alertsCardHtml({
      consent: true,
      cache: cacheOf([GLS_ALERT]),
      online: true,
      now: NOW,
    });
    expect(html).toContain("Fixture Published Name: 5 farms");
    expect(html).not.toContain("FIXTURE TREATMENT");
    expect(html).not.toContain("FIXTURE STEP");
  });

  it("says how old the copy is, coarsely", () => {
    expect(updatedAgo(NOW - 30_000, NOW)).toBe("Updated just now");
    expect(updatedAgo(NOW - 3 * 24 * HOUR, NOW)).toBe("Updated 3 days ago");
  });
});

/* ---------------------------------------------------------------- refresh */

describe("refreshAlerts", () => {
  const here = async () => ({ lat: -15.41234, lng: 28.28766 });

  it("does nothing without the farmer's consent: no location, no request", async () => {
    let calls = 0;
    const result = await refreshAlerts({
      position: async () => {
        calls += 1;
        return here();
      },
      fetchImpl: async () => {
        calls += 1;
      },
    });
    expect(result).toBe("no-consent");
    expect(calls).toBe(0);
  });

  it("sends only a ~1 km rounded location and caches the answer with its time", async () => {
    state.locationConsent = true;
    let url;
    const result = await refreshAlerts({
      position: here,
      now: () => NOW,
      fetchImpl: async (u) => {
        url = String(u);
        return { ok: true, json: async () => response([GLS_ALERT]) };
      },
    });
    expect(result).toBe("updated");
    expect(url).toBe("/api/v1/alerts/nearby/?lat=-15.41&lng=28.29");
    expect(url).not.toContain("1234");
    expect(cachedAlerts()).toMatchObject({ fetchedAt: NOW, area: { lat: -15.41, lng: 28.29 } });
    expect(alertFor("maize__grey_leaf_spot")).toEqual(GLS_ALERT);
    expect(alertFor("maize__common_rust")).toBeNull();
  });

  it("offline keeps the previous copy", async () => {
    state.locationConsent = true;
    localStorage.setItem("agriguard.alerts.v1", JSON.stringify(cacheOf([GLS_ALERT])));
    const result = await refreshAlerts({
      position: here,
      fetchImpl: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    expect(result).toBe("offline");
    expect(alertFor("maize__grey_leaf_spot")).toEqual(GLS_ALERT);
  });

  it("reports when the phone gives no location", async () => {
    state.locationConsent = true;
    expect(await refreshAlerts({ position: async () => null })).toBe("no-location");
  });

  it("rounds to two decimal places", () => {
    expect(roundCoord(-15.41234)).toBe(-15.41);
    expect(roundCoord(28.285)).toBe(28.29);
  });
});

/* ---------------------------------------------------- after a diagnosis */

describe("after a diagnosis", () => {
  const diagnosed = (classId) => {
    session.prediction = {
      class_id: classId,
      confidence: 0.91,
      status: "confident",
      severity: "unknown",
      top_k: [{ class_id: classId, confidence: 0.91 }],
      model_version: "2026.10.0",
    };
  };

  it("warns when the same disease is active nearby", () => {
    localStorage.setItem("agriguard.alerts.v1", JSON.stringify(cacheOf([GLS_ALERT])));
    diagnosed("maize__grey_leaf_spot");
    expect(result.render()).toContain("5 farms within 10 km reported this in the last 7 days.");
  });

  it("stays quiet for a disease that is not active nearby", () => {
    localStorage.setItem("agriguard.alerts.v1", JSON.stringify(cacheOf([GLS_ALERT])));
    diagnosed("maize__common_rust");
    expect(result.render()).not.toContain("reported this in the last");
  });

  it("an alert opens the disease's advice screen without a photo or severity", () => {
    const html = advice.render({ classId: "maize__grey_leaf_spot" });
    expect(html).toContain("Maize Grey Leaf Spot");
    expect(html).toContain('class="ag-advice__nophoto"');
    expect(html).not.toContain("ag-advice__photo");
    // No published advice in this test: only the "not checked by an expert" message.
    expect(html).toContain(t("advisory.no_advice"));
  });
});
