/**
 * Minimal runtime i18n for the PWA.
 *
 * Translation files live in `public/locales/<code>/translation.json` and are
 * fetched at start-up, so translators can edit them without a rebuild.
 * English is always loaded as the fallback: at the time of writing only
 * `en` is populated, and bem/ny/toi are empty, so choosing one of those
 * languages currently falls back to English string by string. That is the
 * intended behaviour until the translations land — nothing in the UI breaks.
 */

export const LANGUAGES = [
  { code: "en", label: "English", speech: "en-GB" },
  { code: "ny", label: "Nyanja", speech: "ny-MW" },
  { code: "bem", label: "Bemba", speech: "bem-ZM" },
  { code: "toi", label: "Tonga", speech: "toi-ZM" },
];

const DEFAULT_LANGUAGE = "en";

let fallbackBundle = {};
let activeBundle = {};
let activeCode = DEFAULT_LANGUAGE;

async function fetchBundle(code) {
  try {
    const response = await fetch(`/locales/${code}/translation.json`);
    if (!response.ok) return {};
    return await response.json();
  } catch {
    // Offline with a cold cache: fall through to the built-in English copy.
    return {};
  }
}

/** Load the fallback bundle plus `code`. Call once at start-up. */
export async function initI18n(code) {
  fallbackBundle = await fetchBundle(DEFAULT_LANGUAGE);
  await setLanguage(code);
}

export async function setLanguage(code) {
  activeCode = LANGUAGES.some((l) => l.code === code) ? code : DEFAULT_LANGUAGE;
  activeBundle = activeCode === DEFAULT_LANGUAGE ? fallbackBundle : await fetchBundle(activeCode);
  if (typeof document !== "undefined") document.documentElement.lang = activeCode;
}

export function currentLanguage() {
  return activeCode;
}

export function languageLabel(code = activeCode) {
  return LANGUAGES.find((l) => l.code === code)?.label ?? code;
}

/** BCP-47 tag used when asking the browser for a speech voice. */
export function speechTag(code = activeCode) {
  return LANGUAGES.find((l) => l.code === code)?.speech ?? "en-GB";
}

/**
 * Look up `key`, falling back to English and then to the key itself.
 * `vars` fills `{name}` placeholders.
 */
export function t(key, vars = {}) {
  const raw = activeBundle[key] ?? fallbackBundle[key] ?? key;
  return raw.replace(/\{(\w+)\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match,
  );
}
