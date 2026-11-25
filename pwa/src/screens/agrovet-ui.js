/**
 * Pieces shared by the four agrovet screens (Figma 10–13).
 */

import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc } from "../ui.js";
import { AGROVET_MOCK } from "../agrovet-api.js";
import { displayName } from "../disease.js";

/** "Demo data" banner, shown on every agrovet screen while the mock is on. */
export function mockBanner() {
  return AGROVET_MOCK
    ? `<p class="ag-av-banner" role="note">${esc(t("agrovet.mockNote"))}</p>`
    : "";
}

/**
 * Back button. Frames 10, 11 and 13 draw a 36 px bordered circle, frame 12 a
 * 40 px plain one; both use the app's existing arrow icon.
 */
export function avBack({ plain = false } = {}) {
  return `
    <button type="button" class="ag-av-back${plain ? " ag-av-back--plain" : ""}" data-action="back"
      aria-label="${esc(t("action.back"))}">
      <img src="${icons.arrowLeft20}" alt="" width="20" height="20" />
    </button>
  `;
}

export function statusChip(status, { large = false } = {}) {
  return `<span class="ag-av-chip ag-av-chip--${esc(status)}${
    large ? " ag-av-chip--lg" : ""
  }">${esc(t(`request.status.${status}`))}</span>`;
}

/** What the "Diagnosis" line says for a class and prediction status. */
export function diagnosisLabel(classId, predictionStatus) {
  if (!classId) return predictionStatus ? t("request.diagnosisNone") : "";
  const name = displayName(classId);
  return predictionStatus === "uncertain" ? t("request.diagnosisUncertain", { name }) : name;
}

export const isOnline = () => globalThis.navigator?.onLine !== false;
