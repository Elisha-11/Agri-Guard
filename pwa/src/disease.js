/**
 * Turns a prediction from `inference/diagnose.js` into the labels the screens
 * show: a readable disease name, and a severity position on the three-zone
 * bar from the Figma design.
 *
 * The advice copy itself is deliberately NOT written here. docs/model-output.md
 * leaves the advisory content open and the Figma screens carry placeholder
 * text ("pending agronomist sign-off"); real treatment instructions must come
 * from the approved advisory, not from this file.
 */

import { t } from "./i18n.js";

/**
 * `maize__grey_leaf_spot` -> `Maize Grey Leaf Spot`
 * `maize__healthy`        -> `Healthy Maize`
 */
export function displayName(classId) {
  if (!classId) return t("result.unknownDisease");

  const [crop, rest] = classId.split("__");
  const titleCase = (value) =>
    value
      .split("_")
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  if (rest === "healthy") return t("result.healthyCrop", { crop: titleCase(crop) });
  return `${titleCase(crop)} ${titleCase(rest ?? "")}`.trim();
}

/**
 * Where the marker sits on the severity bar (0 = left edge, 1 = right edge)
 * and the label beside it.
 *
 * The model contract currently emits only "none" and "unknown" (severity is an
 * open decision, model-output.md section 5). "unknown" is shown mid-bar and
 * labelled as not yet rated rather than silently presented as moderate.
 */
export function severityDisplay(severity) {
  switch (severity) {
    case "none":
      return { position: 0.08, label: t("severity.none"), key: "none" };
    case "mild":
    case "low":
      return { position: 0.17, label: t("severity.mild"), key: "mild" };
    case "moderate":
      return { position: 0.47, label: t("severity.moderate"), key: "moderate" };
    case "severe":
    case "high":
      return { position: 0.83, label: t("severity.severe"), key: "severe" };
    default:
      return { position: 0.5, label: t("severity.unknown"), key: "unknown" };
  }
}

/** Confidence as a whole percentage, e.g. 0.91 -> 91. */
export function confidencePercent(confidence) {
  return Math.round((Number(confidence) || 0) * 100);
}

/**
 * The three advice sections shown on the result screen and expanded on the
 * advice screen. Text is placeholder copy carried over from the design.
 */
export function adviceSections() {
  return [
    { key: "treat", title: t("advice.treat.title"), body: t("advice.treat.body") },
    { key: "prevent", title: t("advice.prevent.title"), body: t("advice.prevent.body") },
    { key: "check", title: t("advice.check.title"), body: t("advice.check.body") },
  ];
}
