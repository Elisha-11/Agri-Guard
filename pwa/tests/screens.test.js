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

    const resultHtml = result.render();
    expect(resultHtml).toContain("Maize Grey Leaf Spot");
    expect(resultHtml).toContain("91% sure");
    expect(resultHtml).toContain("Moderate");
    expect(resultHtml).toContain("Treat now");

    const adviceHtml = advice.render();
    expect(adviceHtml).toContain("Maize Grey Leaf Spot");
    expect(adviceHtml).toContain("Safety");
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
