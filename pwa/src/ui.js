/**
 * Small markup helpers shared by the screens.
 *
 * Screens build HTML strings, so anything that could contain a disease name,
 * a translation or user input goes through `esc` before it is interpolated.
 */

import { icons } from "./icons.js";
import { t } from "./i18n.js";

const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ENTITIES[char]);
}

/**
 * The demonstration-mode notice.
 *
 * Every prediction in this build comes from the mock stub in
 * inference/diagnose.js, which never looks at the image. Any screen that
 * shows a prediction must carry this.
 */
export function demoNote() {
  return `
    <p class="ag-demo-note" role="note">
      <img src="${icons.warning}" alt="" width="16" height="16" />
      <span>${esc(t("demo.notice"))}</span>
    </p>
  `;
}

export function backButton({ icon = icons.arrowLeft, small = false, bare = false } = {}) {
  const classes = ["ag-back", small ? "ag-back--sm" : "", bare ? "ag-back--bare" : ""]
    .filter(Boolean)
    .join(" ");

  return `
    <button type="button" class="${classes}" data-action="back" aria-label="${esc(
      t("action.back"),
    )}">
      <img src="${icon}" alt="" />
    </button>
  `;
}

/**
 * The three-zone severity bar with the marker placed at `position` (0 to 1).
 * Zone widths (73 / 74 / 73 of 220) come straight from the design.
 */
export function severityBar({ position, label }) {
  const clamped = Math.min(1, Math.max(0, position));

  return `
    <div class="ag-severity">
      <div
        class="ag-severity__track"
        role="img"
        aria-label="${esc(t("severity.aria", { level: label }))}"
      >
        <div class="ag-severity__zones">
          <div class="ag-severity__zone--green"></div>
          <div class="ag-severity__zone--amber"></div>
          <div class="ag-severity__zone--red"></div>
        </div>
        <div class="ag-severity__marker" style="left: ${(clamped * 100).toFixed(1)}%"></div>
      </div>
      <span class="ag-severity__label">${esc(label)}</span>
    </div>
  `;
}

/** Date formatted for the history list, e.g. "8 Nov 2026". */
export function formatCheckDate(
  timestamp,
  locale = (typeof document !== "undefined" && document.documentElement.lang) || "en",
) {
  try {
    return new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(timestamp));
  } catch {
    return new Date(timestamp).toDateString();
  }
}

/** Wire every `[data-action="back"]` in a screen to the router. */
export function bindBack(root, handler) {
  root.querySelectorAll('[data-action="back"]').forEach((button) => {
    button.addEventListener("click", handler);
  });
}
