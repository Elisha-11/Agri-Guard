/**
 * Screen 3b — Result Uncertain (Figma node 54:21).
 *
 * Shown when top-1 confidence lands between the uncertain and confident
 * thresholds in lib/prediction.js. The "Possible causes" list is the
 * prediction's own top_k, so the farmer sees what the model was torn between
 * rather than a single answer it is not sure of.
 */

import { icons, photos } from "../icons.js";
import { t } from "../i18n.js";
import { esc, demoNote, backButton, bindBack } from "../ui.js";
import { go, back } from "../router.js";
import { session } from "../state.js";
import { displayName, confidencePercent } from "../disease.js";

const TIP_KEYS = ["uncertain.tip.closer", "uncertain.tip.daylight", "uncertain.tip.flat"];

/** Top-2 candidates below the confident threshold, as shown in the design. */
function candidates() {
  const topK = session.prediction?.top_k ?? [];
  return topK.slice(0, 2).map((item) => ({
    name: displayName(item.class_id),
    percent: confidencePercent(item.confidence),
  }));
}

export function render() {
  const photo = session.imageUrl || photos.uncertainPhoto;

  const tips = TIP_KEYS.map(
    (key) => `
      <li>
        <span class="ag-tips__check">
          <img src="${icons.check}" alt="" width="14" height="14" />
        </span>
        <span>${esc(t(key))}</span>
      </li>
    `,
  ).join("");

  const causes = candidates();
  const causesMarkup = causes.length
    ? causes
        .map(
          (candidate) => `
            <div class="ag-causes__row">
              <span class="ag-causes__name">${esc(candidate.name)}</span>
              <span class="ag-causes__pct">${esc(candidate.percent)}%</span>
            </div>
          `,
        )
        .join("")
    : `<p class="ag-subtext">${esc(t("uncertain.noCauses"))}</p>`;

  return `
    <section class="ag-screen ag-uncertain">
      ${demoNote()}

      <div>${backButton({ icon: icons.arrowLeft20, small: true })}</div>

      <div class="ag-uncertain__photo">
        <img src="${esc(photo)}" alt="${esc(t("result.photoAlt"))}" />
      </div>

      <div>
        <h1 class="ag-heading-lg">${esc(t("uncertain.heading"))}</h1>
        <p class="ag-subtext" style="margin-top: 8px">${esc(t("uncertain.subheading"))}</p>
      </div>

      <div class="ag-card">
        <h2 class="ag-card__title">${esc(t("uncertain.tips"))}</h2>
        <ul class="ag-tips">${tips}</ul>
      </div>

      <div class="ag-card">
        <h2 class="ag-card__title">${esc(t("uncertain.causes"))}</h2>
        <div class="ag-causes">${causesMarkup}</div>
      </div>

      <div style="flex: 1 1 auto"></div>

      <button type="button" class="ag-btn ag-btn--mid" id="ag-retake">
        ${esc(t("uncertain.retake"))}
      </button>
    </section>
  `;
}

export function mount(root) {
  bindBack(root, () => back("/capture"));
  root.querySelector("#ag-retake").addEventListener("click", () => go("/capture"));
  return null;
}
