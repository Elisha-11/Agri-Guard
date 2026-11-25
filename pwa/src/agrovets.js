/**
 * The agrovet directory (spec v2 §1, GET /api/v1/agrovets/; see
 * src/agrovet-api.js for the mock switch).
 *
 * - Kept in localStorage with its ETag, like the advisory bundle, so the list
 *   is there offline. Rechecked with If-None-Match when the app opens and when
 *   the phone gets signal back.
 * - Sorted by straight-line distance from the same rounded location (~1 km)
 *   the outbreak alerts use. That location only exists once the farmer has
 *   turned alerts on, and it never leaves the phone for this feature: the
 *   distances are worked out here.
 * - Without a location: the agrovets in the farmer's district, or everyone in
 *   name order when the district is not known either.
 */

import { agrovetFetch, MOCK_DISTRICT } from "./agrovet-api.js";
import { cachedAlerts } from "./alerts.js";
import { state } from "./state.js";

const KEY = "agriguard.agrovets.v1";
/** Fired on window when the directory or the requests change, so open screens can redraw. */
export const AGROVETS_UPDATED = "agriguard:agrovets-updated";

export function cachedDirectory() {
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
    // storage full or blocked: the list just won't be there offline
  }
}

/** The response is the list itself; a paginated `{results}` body is accepted too. */
function listFrom(body) {
  return Array.isArray(body) ? body : body?.results ?? [];
}

/**
 * Fetch the directory if it changed. Resolves to "updated", "unchanged" or
 * "offline"; never rejects.
 */
export async function refreshDirectory({ fetchImpl = agrovetFetch, now = Date.now } = {}) {
  const cached = cachedDirectory();
  try {
    const response = await fetchImpl("/api/v1/agrovets/", {
      headers: cached?.etag ? { "If-None-Match": cached.etag } : {},
      cache: "no-store",
    });
    if (response.status === 304) {
      store({ ...cached, fetchedAt: now() });
      return "unchanged";
    }
    if (!response.ok) return "offline";
    const items = listFrom(await response.json());
    store({ etag: response.headers.get("ETag"), fetchedAt: now(), items });
    globalThis.window?.dispatchEvent?.(new Event(AGROVETS_UPDATED));
    return "updated";
  } catch {
    return "offline";
  }
}

/** The rough location alerts already use, or null when the farmer has not turned it on. */
export function roughLocation() {
  if (!state.locationConsent) return null;
  return cachedAlerts()?.area ?? null;
}

/**
 * The farmer's district, when the app knows it. Real sign-in will read it from
 * GET /me/; until then only the mock profile has one.
 */
export function knownDistrict() {
  return MOCK_DISTRICT;
}

/** Great-circle distance in km. */
export function distanceKm(a, b) {
  const rad = (deg) => (deg * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

const byName = (a, b) => a.name.localeCompare(b.name);

/**
 * The list as the screen shows it.
 *
 * @returns {{mode: "distance"|"district"|"all", district: string|null, items: Array<object & {km?: number}>}}
 */
export function sortAgrovets(agrovets, { location = null, district = null } = {}) {
  const list = [...(agrovets ?? [])];

  if (location) {
    const items = list
      .map((agrovet) => ({
        ...agrovet,
        km: agrovet.location ? Math.round(distanceKm(location, agrovet.location) * 10) / 10 : null,
      }))
      .sort((a, b) => (a.km ?? Infinity) - (b.km ?? Infinity) || byName(a, b));
    return { mode: "distance", district: null, items };
  }

  if (district) {
    const items = list.filter((agrovet) => agrovet.district === district).sort(byName);
    if (items.length) return { mode: "district", district, items };
  }

  return { mode: "all", district: null, items: list.sort(byName) };
}

export function findAgrovet(id) {
  return cachedDirectory()?.items?.find((agrovet) => agrovet.id === id) ?? null;
}

/** `https://wa.me/260…` for a WhatsApp number in E.164, or null. */
export function whatsappUrl(number) {
  const digits = String(number ?? "").replace(/\D/g, "");
  return digits ? `https://wa.me/${digits}` : null;
}
