/**
 * Screen 3d — Result Rejected (Figma node 54:23).
 *
 * Shown when image-quality.js rejects the photo before inference runs. The
 * design lists all three reasons; the ones the check actually flagged are
 * shown at full strength and the rest are dimmed, so the farmer can see what
 * to fix without the list changing shape between attempts.
 */

import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc, backButton, bindBack } from "../ui.js";
import { go, back } from "../router.js";
import { session } from "../state.js";

const REASONS = [
  { key: "blurry", icon: icons.image20, label: "rejected.blurry" },
  { key: "dark", icon: icons.moon, label: "rejected.dark" },
  { key: "small", icon: icons.maximize, label: "rejected.small" },
];

export function render() {
  const flagged = new Set(session.rejectReasons ?? []);

  const items = REASONS.map(
    (reason) => `
      <li class="ag-reason" data-flagged="${flagged.has(reason.key)}">
        <span class="ag-reason__icon">
          <img src="${reason.icon}" alt="" width="20" height="20" />
        </span>
        <span>${esc(t(reason.label))}</span>
      </li>
    `,
  ).join("");

  return `
    <section class="ag-screen ag-rejected">
      <div class="ag-rejected__top">
        <div>${backButton({ icon: icons.arrowLeftRejected, small: true })}</div>

        <div class="ag-rejected__illustration">
          <span class="ag-rejected__badge">
            <img src="${icons.camera64}" alt="" width="64" height="64" />
          </span>
        </div>

        <h1 class="ag-rejected__heading">${esc(t("rejected.heading"))}</h1>

        <ul class="ag-reasons">${items}</ul>
      </div>

      <div class="ag-rejected__bottom">
        <p class="ag-subtext">${esc(t("rejected.subheading"))}</p>
        <button type="button" class="ag-btn ag-btn--dark" id="ag-retake">
          ${esc(t("rejected.retake"))}
        </button>
      </div>
    </section>
  `;
}

export function mount(root) {
  bindBack(root, () => back("/capture"));
  root.querySelector("#ag-retake").addEventListener("click", () => go("/capture"));
  return null;
}
