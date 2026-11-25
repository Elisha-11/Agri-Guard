/**
 * Screen 12 — My requests (Figma node 109:2).
 *
 * Every request sent from this phone, newest first, with its status. Opened
 * from "My requests" on the agrovet list. Statuses come from the phone's copy,
 * which is refreshed on app open, when signal returns and on this screen.
 */

import { t } from "../i18n.js";
import { esc, bindBack } from "../ui.js";
import { go, back } from "../router.js";
import { AGROVETS_UPDATED } from "../agrovets.js";
import { agrovetRequests } from "../agrovet-requests.js";
import { mockBanner, avBack, statusChip, diagnosisLabel, isOnline } from "./agrovet-ui.js";

/**
 * @param {object} [params]
 * @param {{requests?: object[], authNeeded?: boolean}} [view] for tests
 */
export function render(params, view = {}) {
  const requests = view.requests ?? agrovetRequests.list();
  const authNeeded = view.authNeeded ?? agrovetRequests.authNeeded;

  const list = requests.length
    ? `<ul class="ag-av-requests">${requests
        .map(
          (request) => `
            <li>
              <button type="button" class="ag-av-request" data-request="${esc(request.client_id)}">
                <span class="ag-av-request__text">
                  <span class="ag-av-request__name">${esc(request.agrovet_name)}</span>
                  <span class="ag-av-request__diagnosis">${esc(
                    diagnosisLabel(request.class_id, request.prediction_status) ||
                      request.description,
                  )}</span>
                </span>
                ${statusChip(request.status)}
              </button>
            </li>`,
        )
        .join("")}</ul>`
    : `<p class="ag-av__empty">${esc(t("request.none"))}</p>`;

  return `
    <section class="ag-screen ag-av ag-av--requests">
      ${mockBanner()}
      <div class="ag-av__header">
        ${avBack({ plain: true })}
        <h1 class="ag-av__title ag-av__title--lg">${esc(t("agrovet.myRequests"))}</h1>
      </div>
      ${
        authNeeded ? `<p class="ag-av__note" role="alert">${esc(t("request.signInAgain"))}</p>` : ""
      }
      ${list}
    </section>
  `;
}

export function mount(root, params = {}) {
  bindBack(root, () => back("/agrovets"));

  root.querySelectorAll("[data-request]").forEach((button) => {
    button.addEventListener("click", () => go("/request", { clientId: button.dataset.request }));
  });

  const redraw = () => go("/requests", { ...params, redraw: true });
  window.addEventListener(AGROVETS_UPDATED, redraw);
  if (!params.redraw && isOnline()) agrovetRequests.sync();

  return () => window.removeEventListener(AGROVETS_UPDATED, redraw);
}
