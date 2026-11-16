/**
 * Nearby outbreak alerts (ADR 0019, contract GET /api/v1/alerts/nearby/).
 *
 * - Location is used only after the farmer turns alerts on (state.locationConsent),
 *   at coarse accuracy, rounded to 2 decimal places (~1 km) before it leaves the
 *   phone. The server only ever returns aggregate counts.
 * - The last response is kept in localStorage with the time it was fetched, so
 *   the card still shows offline with "last updated".
 * - Refreshed when the app opens and when the phone gets signal back. When the
 *   diagnosis sync queue lands (docs/offline-sync.md), call refreshAlerts() at
 *   the end of each sync as well.
 * - Alerts never carry advice text: each one links to the disease's published
 *   advice from src/advisory.js (ADR 0008).
 */

import { apiUrl } from "./native.js";
import { state } from "./state.js";
import { t } from "./i18n.js";
import { esc } from "./ui.js";
import { displayName } from "./disease.js";
import { adviceFor } from "./advisory.js";

const KEY = "agriguard.alerts.v1";
/** Fired on window after a successful refresh, so open screens can redraw. */
export const ALERTS_UPDATED = "agriguard:alerts-updated";
/** How many alerts the capture-screen card shows; the rest are summarised. */
export const CARD_LIMIT = 2;

/** 2 decimal places, about 1 km: enough for a 10 km radius, too coarse to find a homestead. */
export const roundCoord = (value) => Math.round(value * 100) / 100;

export function cachedAlerts() {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null");
  } catch {
    return null;
  }
}

function store(value) {
  try {
    localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    // storage full or blocked: the card just won't survive a restart
  }
}

const UNAVAILABLE_KEY = "agriguard.alerts.unavailableAt";

function markUnavailable(at) {
  try {
    localStorage.setItem(UNAVAILABLE_KEY, String(at));
  } catch {
    // not worth failing over
  }
}

/** True when the server answered but couldn't give alerts, and we have no copy yet. */
export function alertsUnavailable() {
  try {
    return localStorage.getItem(UNAVAILABLE_KEY) !== null;
  } catch {
    return false;
  }
}

export function clearAlerts() {
  try {
    localStorage.removeItem(KEY);
    localStorage.removeItem(UNAVAILABLE_KEY);
  } catch {
    // nothing to clear
  }
}

/** The phone's coarse position, or null if unavailable or refused. */
function currentPosition() {
  if (!navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ lat: position.coords.latitude, lng: position.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: false, maximumAge: 30 * 60 * 1000, timeout: 15000 },
    );
  });
}

/**
 * Fetch alerts for the farmer's area and cache them.
 * Resolves to "updated" | "no-consent" | "no-location" | "offline"; never rejects.
 *
 * @param {{position?: () => Promise<{lat:number,lng:number}|null>, fetchImpl?: typeof fetch, now?: () => number}} [deps]
 */
export async function refreshAlerts(deps = {}) {
  const { position = currentPosition, fetchImpl = fetch, now = Date.now } = deps;
  if (!state.locationConsent) return "no-consent";

  const here = await position();
  if (!here) return "no-location";
  const area = { lat: roundCoord(here.lat), lng: roundCoord(here.lng) };

  try {
    const response = await fetchImpl(
      apiUrl(`/api/v1/alerts/nearby/?lat=${area.lat}&lng=${area.lng}`),
      {
        cache: "no-store",
      },
    );
    if (!response.ok) {
      // Reachable but not serving alerts (e.g. a server without this endpoint yet).
      markUnavailable(now());
      return "offline";
    }
    const data = await response.json();
    store({ fetchedAt: now(), area, data });
    try {
      localStorage.removeItem(UNAVAILABLE_KEY);
    } catch {
      // ignore
    }
    globalThis.window?.dispatchEvent?.(new Event(ALERTS_UPDATED));
    return "updated";
  } catch {
    return "offline";
  }
}

/** Refresh now and every time the phone comes back online. */
export function startAlertSync() {
  refreshAlerts();
  window.addEventListener("online", () => refreshAlerts());
}

/** The cached alert for a disease, if that disease is active nearby. */
export function alertFor(classId) {
  return cachedAlerts()?.data?.alerts?.find((alert) => alert.class_id === classId) ?? null;
}

/** Name from the published advice if there is one, else the generated name. */
export function alertName(classId) {
  const advice = adviceFor(classId);
  return advice?.local_name || advice?.name || displayName(classId);
}

/** One alert as a sentence, for the card and for narration. */
export function alertSentence(alert) {
  return t("alerts.item", {
    name: alertName(alert.class_id),
    count: alert.farm_count,
    km: alert.distance_band_km,
    days: alert.window_days,
  });
}

/** "Updated 3 hours ago"-style text, coarse on purpose. */
export function updatedAgo(fetchedAt, now = Date.now()) {
  const minutes = Math.max(0, Math.round((now - fetchedAt) / 60000));
  if (minutes < 2) return t("alerts.updatedJustNow");
  if (minutes < 90) return t("alerts.updatedMinutes", { count: minutes });
  const hours = Math.round(minutes / 60);
  if (hours < 36) return t("alerts.updatedHours", { count: hours });
  return t("alerts.updatedDays", { count: Math.round(hours / 24) });
}

/**
 * The alerts card on the capture screen. Pure: everything it depends on is
 * passed in, so each state renders the same in tests and on the phone.
 *
 * @param {{consent: boolean, cache: object|null, online: boolean, now?: number}} view
 */
export function alertsCardHtml({ consent, cache, online, unavailable = false, now = Date.now() }) {
  if (!consent) {
    return `
      <section class="ag-alerts ag-alerts--off" aria-label="${esc(t("alerts.title"))}">
        <p class="ag-alerts__text">${esc(t("alerts.offExplain"))}</p>
        <button type="button" class="ag-alerts__enable" id="ag-alerts-enable">
          ${esc(t("alerts.enable"))}
        </button>
      </section>
    `;
  }

  if (!cache?.data) {
    return `
      <section class="ag-alerts" aria-label="${esc(t("alerts.title"))}">
        <p class="ag-alerts__text">${esc(
          t(
            !online
              ? "alerts.neverFetchedOffline"
              : unavailable
                ? "alerts.unavailable"
                : "alerts.loading",
          ),
        )}</p>
      </section>
    `;
  }

  const alerts = cache.data.alerts ?? [];
  const stamp = `${updatedAgo(cache.fetchedAt, now)}${online ? "" : ` · ${t("alerts.offline")}`}`;

  if (!alerts.length) {
    return `
      <section class="ag-alerts ag-alerts--none" aria-label="${esc(t("alerts.title"))}">
        <p class="ag-alerts__text">${esc(
          t("alerts.none", { km: cache.data.radius_km, days: cache.data.window_days }),
        )}</p>
        <p class="ag-alerts__stamp">${esc(stamp)}</p>
      </section>
    `;
  }

  const shown = alerts.slice(0, CARD_LIMIT);
  const more = alerts.length - shown.length;
  return `
    <section class="ag-alerts ag-alerts--active" aria-label="${esc(t("alerts.title"))}">
      <div class="ag-alerts__head">
        <h2 class="ag-alerts__title">${esc(t("alerts.title"))}</h2>
        <button type="button" class="ag-alerts__listen" id="ag-alerts-listen" aria-label="${esc(
          t("alerts.listen"),
        )}">🔊</button>
      </div>
      <ul class="ag-alerts__list">
        ${shown
          .map(
            (alert) => `
              <li>
                <button type="button" class="ag-alerts__item" data-alert="${esc(alert.class_id)}">
                  ${esc(alertSentence(alert))}
                </button>
              </li>`,
          )
          .join("")}
      </ul>
      ${more > 0 ? `<p class="ag-alerts__stamp">${esc(t("alerts.more", { count: more }))}</p>` : ""}
      <p class="ag-alerts__stamp">${esc(stamp)}</p>
    </section>
  `;
}

/** What narration reads for the card. */
export function alertsSpeech(cache) {
  const alerts = cache?.data?.alerts ?? [];
  return [t("alerts.title"), ...alerts.map(alertSentence)];
}
