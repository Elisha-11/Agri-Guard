/**
 * Render smoke tests for the twelve screens built from the AgriGuard Screens
 * Figma file.
 *
 * Each screen's `render()` is a pure string builder, so it can be exercised
 * without a DOM. These catch the things that break quietly: a missing
 * translation key, a renamed asset export, a screen that throws when there is
 * no prediction or no saved history. `mount()` needs real elements and is not
 * covered here.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { beforeAll, describe, expect, it } from "vitest";

import { initI18n, t } from "../src/i18n.js";
import { displayName, severityDisplay, confidencePercent } from "../src/disease.js";
import { esc, formatCheckDate } from "../src/ui.js";
import { THRESHOLDS } from "../src/image-quality.js";
import { session, addHistoryEntry, state } from "../src/state.js";

// Node has no localStorage; src/advisory.js keeps the advisory bundle there.
if (typeof globalThis.localStorage === "undefined") {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
  };
}

import * as capture from "../src/screens/capture.js";
import * as processing from "../src/screens/processing.js";
import * as result from "../src/screens/result.js";
import * as resultUncertain from "../src/screens/result-uncertain.js";
import * as resultConsult from "../src/screens/result-consult.js";
import * as resultRejected from "../src/screens/result-rejected.js";
import * as advice from "../src/screens/advice.js";
import * as history from "../src/screens/history.js";
import * as settings from "../src/screens/settings.js";
import * as language from "../src/screens/language.js";
import * as signIn from "../src/screens/sign-in.js";
import * as enterCode from "../src/screens/enter-code.js";
import * as agrovets from "../src/screens/agrovets.js";
import * as agrovetRequest from "../src/screens/agrovet-request.js";
import * as requests from "../src/screens/requests.js";
import * as requestDetail from "../src/screens/request-detail.js";
import { AGROVET_MOCK } from "../src/agrovet-api.js";

const localeUrl = new URL("../public/locales/en/translation.json", import.meta.url);

beforeAll(async () => {
  // i18n fetches its bundles over HTTP in the browser; serve them from disk here.
  globalThis.fetch = async (url) => {
    const path = String(url);
    if (!path.includes("/locales/en/")) return { ok: false };
    return {
      ok: true,
      json: async () => JSON.parse(readFileSync(fileURLToPath(localeUrl), "utf8")),
    };
  };

  await initI18n("en");
});

describe("disease labels", () => {
  it("turns a class id into the name the design shows", () => {
    expect(displayName("maize__grey_leaf_spot")).toBe("Maize Grey Leaf Spot");
    expect(displayName("cassava__mosaic_disease")).toBe("Cassava Mosaic Disease");
  });

  it("reads healthy classes as a healthy crop", () => {
    expect(displayName("maize__healthy")).toBe("Healthy Maize");
  });

  it("falls back when there is no class", () => {
    expect(displayName(undefined)).toBe(t("result.unknownDisease"));
  });

  it("rounds confidence to whole percent", () => {
    expect(confidencePercent(0.91)).toBe(91);
    expect(confidencePercent(undefined)).toBe(0);
  });
});

describe("severity bar", () => {
  it("places known severities along the bar", () => {
    expect(severityDisplay("none").position).toBeLessThan(0.33);
    expect(severityDisplay("severe").position).toBeGreaterThan(0.66);
  });

  it("does not present an unrated severity as moderate", () => {
    const unknown = severityDisplay("unknown");
    expect(unknown.key).toBe("unknown");
    expect(unknown.label).toBe(t("severity.unknown"));
    expect(unknown.label).not.toBe(t("severity.moderate"));
  });
});

describe("markup helpers", () => {
  it("escapes values interpolated into screen markup", () => {
    expect(esc('<img src=x onerror="alert(1)">')).not.toContain("<");
    expect(esc("Maize & Co")).toBe("Maize &amp; Co");
  });

  it("formats a check date", () => {
    expect(formatCheckDate(Date.UTC(2026, 10, 8), "en-GB")).toMatch(/2026/);
  });
});

describe("photo quality thresholds", () => {
  it("keeps the model input size as the minimum short side", () => {
    expect(THRESHOLDS.minShortSide).toBe(224);
    expect(THRESHOLDS.minMeanLuminance).toBeGreaterThan(0);
    expect(THRESHOLDS.minFocusVariance).toBeGreaterThan(0);
  });
});

describe("screens render", () => {
  it("renders capture with the Figma instruction and both controls", () => {
    const html = capture.render();
    expect(html).toContain("Hold the phone over the leaf.");
    expect(html).toContain("Upload from gallery");
    expect(html).toContain("ag-capture__shutter");
  });

  it("renders processing with the checking message", () => {
    expect(processing.render()).toContain("Checking your plant...");
  });

  it("renders every result state without a prediction present", () => {
    session.prediction = null;
    session.rejectReasons = ["blurry"];

    expect(result.render()).toBe("");
    expect(advice.render()).toBe("");
    expect(resultConsult.render()).toContain("extension officer");
    expect(resultRejected.render()).toContain("This photo is hard to read.");
    expect(resultUncertain.render()).toContain("We are not sure.");
  });

  it("renders the result and advice screens from a prediction", () => {
    session.prediction = {
      class_id: "maize__grey_leaf_spot",
      confidence: 0.91,
      status: "confident",
      severity: "moderate",
      top_k: [
        { class_id: "maize__grey_leaf_spot", confidence: 0.91 },
        { class_id: "maize__common_rust", confidence: 0.06 },
      ],
      model_version: "0.0.0-untrained",
    };

    // No advisory bundle downloaded: no treatment text at all, only the
    // "not checked by an expert yet" message.
    localStorage.removeItem("agriguard.advisory.en");
    const resultHtml = result.render();
    expect(resultHtml).toContain("Maize Grey Leaf Spot");
    expect(resultHtml).toContain("91% sure");
    expect(resultHtml).toContain("Moderate");
    expect(resultHtml).toContain(t("advisory.no_advice"));

    const adviceHtml = advice.render();
    expect(adviceHtml).toContain("Maize Grey Leaf Spot");
    expect(adviceHtml).toContain(t("advisory.no_advice"));
    expect(adviceHtml).not.toContain("Safety");
  });

  it("shows published advice from the advisory bundle, safety warning first", () => {
    const previous = session.prediction;
    session.prediction = {
      class_id: "maize__grey_leaf_spot",
      confidence: 0.91,
      status: "confident",
      severity: "unknown",
      top_k: [{ class_id: "maize__grey_leaf_spot", confidence: 0.91 }],
      model_version: "2026.10.0",
    };
    // Test fixture in the bundle's shape; the strings are markers, not advice.
    const section = (name) => ({
      title: `${name} title`,
      steps: [`${name} step 1`, `${name} step 2`],
    });
    localStorage.setItem(
      "agriguard.advisory.en",
      JSON.stringify({
        etag: '"test"',
        bundle: {
          bundle_version: "test",
          lang: "en",
          diseases: [
            {
              class_id: "maize__grey_leaf_spot",
              lang: "en",
              name: "Fixture Disease Name",
              local_name: null,
              treatment: section("TREATMENT"),
              prevention: section("PREVENTION"),
              follow_up: section("FOLLOWUP"),
              safety_warning: "FIXTURE SAFETY WARNING",
              reviewed_by: "Fixture Reviewer",
              reviewed_at: "2026-11-01",
            },
          ],
          ui: {},
        },
      }),
    );

    try {
      const resultHtml = result.render();
      expect(resultHtml).toContain("Fixture Disease Name");
      expect(resultHtml).toContain("TREATMENT title");
      expect(resultHtml).toContain("TREATMENT step 1");
      expect(resultHtml).not.toContain(t("advisory.no_advice"));

      const adviceHtml = advice.render();
      expect(adviceHtml).toContain("FOLLOWUP step 2");
      expect(adviceHtml).toContain("Fixture Reviewer");
      expect(adviceHtml.indexOf("FIXTURE SAFETY WARNING")).toBeLessThan(
        adviceHtml.indexOf("TREATMENT step 1"),
      );
    } finally {
      localStorage.removeItem("agriguard.advisory.en");
      session.prediction = previous;
    }
  });

  it("keeps the demonstration-mode notice on every screen showing a prediction", () => {
    const notice = t("demo.notice");
    expect(result.render()).toContain(notice);
    expect(advice.render()).toContain(notice);
    expect(resultUncertain.render()).toContain(notice);
    expect(resultConsult.render()).toContain(notice);
    expect(history.render()).toContain(notice);
  });

  it("lists the model's runners-up as possible causes", () => {
    const html = resultUncertain.render();
    expect(html).toContain("Maize Common Rust");
    expect(html).toContain("6%");
  });

  it("shows an empty history, then a saved check", () => {
    expect(history.render()).toContain(t("history.empty"));

    addHistoryEntry({
      classId: "maize__grey_leaf_spot",
      name: "Maize Grey Leaf Spot",
      confidence: 0.91,
      severity: "moderate",
      status: "confident",
      thumb: "",
    });

    const html = history.render();
    expect(html).toContain("Maize Grey Leaf Spot");
    expect(html).not.toContain(t("history.empty"));
  });

  it("renders settings, language, sign in and code entry", () => {
    state.phone = "970000000";

    expect(settings.render()).toContain("Voice narration");
    expect(settings.render()).toContain("Sign out");
    expect(language.render()).toContain("Nyanja");
    expect(language.render()).toContain("Tonga");
    expect(signIn.render()).toContain("Send code");
    expect(enterCode.render()).toContain("+260 970000000");
  });
});

describe("agrovet screens", () => {
  const shops = [
    {
      id: "a1",
      name: "Demo Agrovet One",
      town: "Example Town",
      district: "Example District",
      location: { lat: -15.41, lng: 28.3 },
      phone: "+260000000001",
      whatsapp: "+260000000001",
    },
    {
      id: "a2",
      name: "Demo Agrovet Two",
      town: "Example Town",
      district: "Example District",
      location: { lat: -15.5, lng: 28.3 },
      phone: "+260000000002",
      whatsapp: null,
    },
  ];
  const cache = { etag: '"v1"', fetchedAt: Date.UTC(2026, 10, 25), items: shops };

  it("adds one Find agrovet button to the result, uncertain, consult and advice screens", () => {
    session.prediction = {
      class_id: "maize__streak",
      confidence: 0.91,
      status: "confident",
      severity: "none",
      top_k: [{ class_id: "maize__streak", confidence: 0.91 }],
      model_version: "x",
    };
    for (const screen of [result, advice, resultUncertain, resultConsult]) {
      const html = screen.render();
      expect(html.match(/id="ag-find-agrovet"/g)).toHaveLength(1);
      expect(html).toContain("Find agrovet");
    }
    expect(resultRejected.render()).not.toContain("ag-find-agrovet");
    expect(capture.render()).not.toContain("ag-find-agrovet");
  });

  it("lists agrovets by distance with Call and WhatsApp links", () => {
    const html = agrovets.render({}, { cache, location: { lat: -15.4, lng: 28.3 }, online: true });
    expect(html).toContain("Agrovets near you");
    expect(html.indexOf("Demo Agrovet One")).toBeLessThan(html.indexOf("Demo Agrovet Two"));
    expect(html).toContain("1.1 km away");
    expect(html).toContain('href="tel:+260000000001"');
    expect(html).toContain('href="https://wa.me/260000000001"');
    // Two has no WhatsApp number, so no WhatsApp button.
    expect(html.match(/ag-av-card__btn--whatsapp/g)).toHaveLength(1);
    expect(html).toContain("My requests");
    expect(html).not.toContain("Turn on location");
  });

  it("without location, shows the district and the turn-on-location note", () => {
    const html = agrovets.render(
      {},
      { cache, location: null, district: "Example District", online: true },
    );
    expect(html).toContain("Agrovets in Example District");
    expect(html).toContain("Turn on location to see the closest agrovets first.");
    expect(html).not.toContain("km away");
  });

  it("works offline from the cache, with Call and WhatsApp marked as needing signal", () => {
    const html = agrovets.render({}, { cache, location: null, district: null, online: false });
    expect(html).toContain("Demo Agrovet One");
    expect(html).toContain("Needs signal");
    expect(html).not.toContain("tel:");
    expect(html).not.toContain("wa.me");
  });

  it("explains an empty list offline before the first download", () => {
    const html = agrovets.render(
      {},
      { cache: null, location: null, district: null, online: false },
    );
    expect(html).toContain(t("agrovet.neverFetchedOffline"));
  });

  it("shows the demo banner exactly while the mock is on", () => {
    const html = agrovets.render({}, { cache, online: true });
    expect(html.includes("Demo data. These agrovets are not real.")).toBe(AGROVET_MOCK);
  });

  it("renders the request form with phone off and everything else on", () => {
    const html = agrovetRequest.render(
      {},
      {
        agrovet: shops[0],
        context: { classId: "maize__streak", predictionStatus: "confident", thumb: "data:x" },
        district: "Example District",
        online: true,
      },
    );
    expect(html).toContain("Ask Demo Agrovet One");
    expect(html).toContain("Maize Streak");
    expect(html).toContain("Describe the problem in your own words");
    for (const key of ["photo", "diagnosis", "district"]) {
      expect(html).toMatch(new RegExp(`data-share="${key}"\\s+checked`));
    }
    expect(html).toMatch(/data-share="phone"\s+\/>/);
    expect(html).toContain("Off unless you turn it on. If on, the agrovet can call you.");
  });

  it("offers only the toggles there is something to share for", () => {
    const html = agrovetRequest.render(
      {},
      { agrovet: shops[0], context: null, district: null, online: false },
    );
    expect(html).not.toContain('data-share="photo"');
    expect(html).not.toContain('data-share="diagnosis"');
    expect(html).not.toContain('data-share="district"');
    expect(html).toContain('data-share="phone"');
    expect(html).toContain(t("request.offlineHint"));
  });

  it("labels an uncertain diagnosis as not sure", () => {
    const html = agrovetRequest.render(
      {},
      {
        agrovet: shops[0],
        context: { classId: "maize__streak", predictionStatus: "uncertain" },
        district: null,
        online: true,
      },
    );
    expect(html).toContain("Maize Streak (not sure)");
  });

  const sent = {
    client_id: "c1",
    agrovet_id: "a1",
    agrovet_name: "Demo Agrovet One",
    crop: "maize",
    class_id: "maize__streak",
    prediction_status: "confident",
    description: "Pale streaks appeared on the leaves this week.",
    share_phone: false,
    thumb: "data:x",
    status: "replied",
    replies: [
      {
        id: "r1",
        in_stock: true,
        price: { amount: 150, currency: "ZMW" },
        product: { id: null, name: "Demo product" },
        visit_farm: true,
        text: "I can visit your farm.",
        lang: "en",
      },
    ],
    created_at: "2026-11-25T10:00:00Z",
  };

  it("lists my requests with their status", () => {
    const html = requests.render(
      {},
      {
        requests: [sent, { ...sent, client_id: "c2", status: "queued", replies: [] }],
        authNeeded: false,
      },
    );
    expect(html).toContain("My requests");
    expect(html).toContain("Replied");
    expect(html).toContain("Waiting for signal");
    expect(requests.render({}, { requests: [], authNeeded: false })).toContain(t("request.none"));
    expect(requests.render({}, { requests: [], authNeeded: true })).toContain(
      t("request.signInAgain"),
    );
  });

  it("shows a reply with stock, price, product, farm visit and text", () => {
    const html = requestDetail.render({}, { request: sent, lang: "en" });
    expect(html).toContain("Request to Demo Agrovet One");
    expect(html).toContain("Your description: Pale streaks appeared on the leaves this week.");
    expect(html).toContain("In stock");
    expect(html).toContain("Price: K150");
    expect(html).toContain("Suggested product: Demo product");
    expect(html).toContain("Can visit your farm");
    expect(html).toContain("I can visit your farm.");
    expect(html).toContain("Close request");
    expect(html).toContain("Close this request?");
    expect(html).not.toContain("Shown in English");
  });

  it("notes an English fallback for a farmer using another language", () => {
    expect(requestDetail.render({}, { request: sent, lang: "ny" })).toContain("Shown in English");
  });

  it("shows waiting and closed states", () => {
    const waiting = requestDetail.render({}, { request: { ...sent, status: "sent", replies: [] } });
    expect(waiting).toContain("No reply yet");

    const queued = requestDetail.render(
      {},
      { request: { ...sent, status: "queued", replies: [] } },
    );
    expect(queued).toContain(t("request.willSend"));

    const closed = requestDetail.render({}, { request: { ...sent, status: "closed" } });
    expect(closed).toContain("Closed");
    expect(closed).not.toContain("Close request");
  });
});
