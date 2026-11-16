/**
 * Screen 3c — Result Consult (Figma node 54:22).
 *
 * Shown when confidence falls below the uncertain threshold, or when
 * inference failed outright. The app deliberately names no disease here —
 * it hands the farmer on to an extension officer.
 *
 * "Find an extension officer" has no directory to call yet; the officer
 * lookup is a backend concern that does not exist in docs/api-contract.yaml,
 * so the button explains that rather than pretending to search.
 */

import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc, demoNote, backButton, bindBack } from "../ui.js";
import { go, back } from "../router.js";

export function render() {
  return `
    <section class="ag-screen ag-consult">
      ${demoNote()}

      <div>${backButton({ icon: icons.arrowLeft20, small: true })}</div>

      <div class="ag-consult__image">
        <img src="${icons.leafPlaceholder}" alt="" width="64" height="64" />
      </div>

      <div class="ag-consult__text">
        <h1 class="ag-heading-lg">${esc(t("consult.heading"))}</h1>
        <p class="ag-subtext" style="margin-top: 12px">${esc(t("consult.subheading"))}</p>
      </div>

      <div class="ag-consult__actions">
        <p class="ag-subtext" id="ag-officer-note" hidden></p>

        <button type="button" class="ag-btn ag-btn--sage" id="ag-find">
          ${esc(t("consult.find"))}
        </button>

        <button type="button" class="ag-btn ag-btn--link" id="ag-home">
          ${esc(t("consult.home"))}
        </button>
      </div>
    </section>
  `;
}

export function mount(root) {
  bindBack(root, () => back("/capture"));

  const note = root.querySelector("#ag-officer-note");

  root.querySelector("#ag-find").addEventListener("click", () => {
    note.textContent = t("consult.findPending");
    note.hidden = false;
  });

  root.querySelector("#ag-home").addEventListener("click", () => go("/capture"));

  return null;
}
