/**
 * Treatment advice from the approved advisory bundle
 * (GET /api/v1/advisory/bundle/?lang=…, docs/backend/advisory-bundle.md).
 *
 * The app shows only what this bundle contains. The backend publishes advice
 * only after an agronomist is recorded as its reviewer, so nothing the farmer
 * reads about treatment is written in the app's code. A disease with no
 * published advice gets the bundle's `ui.no_advice` message instead.
 *
 * Bundles are kept in localStorage with their ETag (about 600 bytes per
 * disease per language) so advice is there offline, and rechecked with
 * If-None-Match whenever the app opens or comes back online; a 304 costs a
 * few hundred bytes.
 */

import { apiUrl } from "./native.js";
import { currentLanguage, t } from "./i18n.js";

const KEY = (lang) => `agriguard.advisory.${lang}`;

function read(lang) {
  try {
    return JSON.parse(localStorage.getItem(KEY(lang)) ?? "null");
  } catch {
    return null;
  }
}

function write(lang, value) {
  try {
    localStorage.setItem(KEY(lang), JSON.stringify(value));
  } catch {
    // storage full or blocked: advice simply stays online-only
  }
}

/**
 * Fetch the bundle for `lang` if it changed since the stored copy.
 * Resolves to "updated", "unchanged" or "offline"; never rejects.
 */
export async function refreshAdvisory(lang) {
  const stored = read(lang);
  try {
    const response = await fetch(
      apiUrl(`/api/v1/advisory/bundle/?lang=${encodeURIComponent(lang)}`),
      {
        headers: stored?.etag ? { "If-None-Match": stored.etag } : {},
        cache: "no-store",
      },
    );
    if (response.status === 304) return "unchanged";
    if (!response.ok) return "offline";

    const bundle = await response.json();
    write(lang, { etag: response.headers.get("ETag") ?? `"${bundle.bundle_version}"`, bundle });
    return "updated";
  } catch {
    return "offline";
  }
}

/** Refresh the farmer's language and English (the per-disease fallback). */
export function refreshAllAdvisory() {
  const langs = new Set([currentLanguage(), "en"]);
  return Promise.all([...langs].map(refreshAdvisory));
}

/** Keep advice current: now, and every time the phone gets signal back. */
export function startAdvisorySync() {
  refreshAllAdvisory();
  window.addEventListener("online", () => refreshAllAdvisory());
}

/**
 * Published advice for a class, in the farmer's language if it exists,
 * otherwise English. Null when no reviewed advice has been published.
 */
export function adviceFor(classId) {
  if (!classId) return null;
  for (const lang of new Set([currentLanguage(), "en"])) {
    const disease = read(lang)?.bundle?.diseases?.find((entry) => entry.class_id === classId);
    if (disease) return disease;
  }
  return null;
}

/** A fixed message from the bundle's `ui` (no_advice, uncertain, consult, rejected). */
export function advisoryMessage(key) {
  for (const lang of new Set([currentLanguage(), "en"])) {
    const message = read(lang)?.bundle?.ui?.[key];
    if (message) return message;
  }
  return t(`advisory.${key}`);
}

/**
 * The three cards on the result and advice screens, from published advice.
 * Empty when there is none: the screens then show advisoryMessage("no_advice").
 */
export function adviceCards(advice) {
  if (!advice) return [];
  return [
    { key: "treat", section: advice.treatment },
    { key: "prevent", section: advice.prevention },
    { key: "check", section: advice.follow_up },
  ]
    .filter(({ section }) => section?.title && section.steps?.length)
    .map(({ key, section }) => ({ key, title: section.title, steps: section.steps }));
}
