/**
 * The "Find agrovet" button added to the result, uncertain, consult and
 * advice screens. It remembers which check it was pressed from, so the
 * request form can fill in the crop, diagnosis and photo, then opens the
 * agrovet list.
 */

import { t } from "./i18n.js";
import { esc } from "./ui.js";
import { go } from "./router.js";
import { setRequestContext } from "./agrovet-requests.js";

export function findAgrovetButton() {
  return `
    <button type="button" class="ag-find-agrovet" id="ag-find-agrovet">
      ${esc(t("agrovet.find"))}
    </button>
  `;
}

/**
 * @param {Element} root
 * @param {() => {classId?: string|null, predictionStatus?: string|null, thumb?: string|null, useSessionPhoto?: boolean}} context
 */
export function bindFindAgrovet(root, context) {
  root.querySelector("#ag-find-agrovet")?.addEventListener("click", () => {
    setRequestContext(context());
    go("/agrovets");
  });
}
