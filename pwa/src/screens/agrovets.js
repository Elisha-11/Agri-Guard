/**
 * Screen 10 — Agrovets (Figma node 108:2).
 *
 * Agrovets near the farmer, from the cached directory (src/agrovets.js), so
 * the list works offline. Sorted by distance when location is on; otherwise
 * the farmer's district (or everyone, by name) with the "turn on location"
 * note. Tapping a card opens the request form (screen 11). Call and WhatsApp
 * need signal and say so when there is none.
 */

import { t } from "../i18n.js";
import { esc, bindBack, formatCheckDate } from "../ui.js";
import { go, back } from "../router.js";
import {
  AGROVETS_UPDATED,
  cachedDirectory,
  knownDistrict,
  refreshDirectory,
  roughLocation,
  sortAgrovets,
  whatsappUrl,
} from "../agrovets.js";
import { mockBanner, avBack, isOnline } from "./agrovet-ui.js";

function contact({ label, href, online, cls, external = false }) {
  if (!href) return "";
  if (!online) {
    return `<span class="ag-av-card__btn ${cls} is-disabled" aria-disabled="true">${esc(
      label,
    )}</span>`;
  }
  const target = external ? ' target="_blank" rel="noopener"' : "";
  return `<a class="ag-av-card__btn ${cls}" href="${esc(href)}"${target}>${esc(label)}</a>`;
}

function card(agrovet, { online, showDistance }) {
  const call = contact({
    label: t("agrovet.call"),
    href: agrovet.phone ? `tel:${agrovet.phone}` : null,
    online,
    cls: "ag-av-card__btn--call",
  });
  const whatsapp = contact({
    label: t("agrovet.whatsapp"),
    href: whatsappUrl(agrovet.whatsapp),
    online,
    cls: "ag-av-card__btn--whatsapp",
    external: true,
  });

  return `
    <li class="ag-av-card">
      <button type="button" class="ag-av-card__open" data-agrovet="${esc(agrovet.id)}"
        aria-label="${esc(t("agrovet.openRequest", { name: agrovet.name }))}">
        <span class="ag-av-card__name">${esc(agrovet.name)}</span>
        <span class="ag-av-card__details">
          <span class="ag-av-card__town">${esc(agrovet.town)}</span>
          ${
            showDistance && agrovet.km != null
              ? `<span class="ag-av-card__km">${esc(
                  t("agrovet.distance", { km: agrovet.km }),
                )}</span>`
              : ""
          }
        </span>
      </button>
      ${call || whatsapp ? `<div class="ag-av-card__actions">${call}${whatsapp}</div>` : ""}
      ${
        !online && (call || whatsapp)
          ? `<p class="ag-av-card__signal">${esc(t("agrovet.needsSignal"))}</p>`
          : ""
      }
    </li>
  `;
}

/**
 * @param {object} [params]
 * @param {{cache?: object|null, location?: object|null, district?: string|null, online?: boolean}} [view] for tests
 */
export function render(params, view = {}) {
  const cache = view.cache !== undefined ? view.cache : cachedDirectory();
  const online = view.online ?? isOnline();
  const sorted = sortAgrovets(cache?.items, {
    location: view.location !== undefined ? view.location : roughLocation(),
    district: view.district !== undefined ? view.district : knownDistrict(),
  });

  const title =
    sorted.mode === "distance"
      ? t("agrovet.title")
      : sorted.mode === "district"
        ? t("agrovet.titleDistrict", { district: sorted.district })
        : t("agrovet.titleAll");

  let body;
  if (!cache) {
    body = `<p class="ag-av__empty">${esc(
      t(online ? "agrovet.loading" : "agrovet.neverFetchedOffline"),
    )}</p>`;
  } else if (!sorted.items.length) {
    body = `<p class="ag-av__empty">${esc(t("agrovet.none"))}</p>`;
  } else {
    body = `<ul class="ag-av__list">${sorted.items
      .map((agrovet) => card(agrovet, { online, showDistance: sorted.mode === "distance" }))
      .join("")}</ul>`;
  }

  return `
    <section class="ag-screen ag-av">
      ${mockBanner()}

      <div class="ag-av__nav">
        ${avBack()}
        <button type="button" class="ag-av__link" id="ag-av-my-requests">
          ${esc(t("agrovet.myRequests"))}
        </button>
      </div>

      <h1 class="ag-av__title">${esc(title)}</h1>

      ${body}

      ${
        cache?.fetchedAt
          ? `<p class="ag-av__meta">${esc(
              t("agrovet.updated", { date: formatCheckDate(cache.fetchedAt) }),
            )}</p>`
          : ""
      }

      ${
        sorted.mode === "distance"
          ? ""
          : `<p class="ag-av__note" role="note">${esc(t("agrovet.noLocation"))}</p>`
      }
    </section>
  `;
}

export function mount(root, params = {}) {
  bindBack(root, () => back("/capture"));

  root.querySelector("#ag-av-my-requests").addEventListener("click", () => go("/requests"));

  root.querySelectorAll("[data-agrovet]").forEach((button) => {
    button.addEventListener("click", () =>
      go("/agrovet-request", { agrovetId: button.dataset.agrovet }),
    );
  });

  // Redraw when a fresher list arrives or the connection changes. A redraw
  // does not fetch again, so a server without ETags cannot cause a loop.
  const redraw = () => go("/agrovets", { ...params, redraw: true });
  window.addEventListener(AGROVETS_UPDATED, redraw);
  window.addEventListener("online", redraw);
  window.addEventListener("offline", redraw);
  if (!params.redraw && isOnline()) refreshDirectory();

  return () => {
    window.removeEventListener(AGROVETS_UPDATED, redraw);
    window.removeEventListener("online", redraw);
    window.removeEventListener("offline", redraw);
  };
}
