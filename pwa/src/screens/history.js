/**
 * Screen 5 — History (Figma node 88:2).
 *
 * Lists the checks saved by the processing screen, newest first. The three
 * cards in the design are sample data; a farmer who has not run a check yet
 * sees an empty state instead, with the same "Take new photo" action.
 */

import { icons, severityDot } from "../icons.js";
import { t } from "../i18n.js";
import { esc, demoNote, backButton, bindBack, formatCheckDate } from "../ui.js";
import { go, back } from "../router.js";
import { state } from "../state.js";
import { displayName } from "../disease.js";

export function render() {
  const entries = state.history;

  const list = entries.length
    ? `
      <ul class="ag-history__list">
        ${entries
          .map(
            (entry) => `
              <li>
                <button type="button" class="ag-history__card" data-entry="${esc(entry.id)}">
                  <span class="ag-history__thumb">
                    ${
                      entry.thumb
                        ? `<img src="${esc(entry.thumb)}" alt="" />`
                        : `<img src="${icons.leafPlaceholder}" alt="" />`
                    }
                  </span>
                  <span class="ag-history__text">
                    <span class="ag-history__name">
                      ${esc(entry.name ?? displayName(entry.classId))}
                    </span>
                    <span class="ag-history__date">${esc(formatCheckDate(entry.checkedAt))}</span>
                  </span>
                  <img src="${severityDot(entry.severity)}" alt="" width="10" height="10" />
                  <img src="${icons.chevronRight}" alt="" width="8" height="14" />
                </button>
              </li>
            `,
          )
          .join("")}
      </ul>
    `
    : `
      <div class="ag-history__empty">
        <p class="ag-subtext">${esc(t("history.empty"))}</p>
      </div>
    `;

  return `
    <section class="ag-screen">
      ${demoNote()}

      <div class="ag-screen__scroll">
        <div class="ag-history__head">
          ${backButton({ icon: icons.arrowLeftHistory })}
          <h1 class="ag-history__title">${esc(t("history.title"))}</h1>
        </div>
        ${list}
      </div>

      <div class="ag-screen__footer">
        <button type="button" class="ag-btn" id="ag-new">${esc(t("history.newPhoto"))}</button>
      </div>
    </section>
  `;
}

export function mount(root) {
  bindBack(root, () => back("/capture"));

  root.querySelectorAll("[data-entry]").forEach((card) => {
    card.addEventListener("click", () => go("/result", { entryId: card.dataset.entry }));
  });

  root.querySelector("#ag-new").addEventListener("click", () => go("/capture"));

  return null;
}
