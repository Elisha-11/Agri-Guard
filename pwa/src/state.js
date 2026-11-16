/**
 * App state for the AgriGuard PWA.
 *
 * Settings and the check history persist in localStorage so the app is usable
 * offline and across restarts. The image being diagnosed right now is held in
 * memory only — a full-size photo has no business in localStorage.
 *
 * When the backend sync described in docs/offline-sync.md lands, the history
 * entries written here are the records that will be pushed up.
 */

const KEY = "agriguard.v1";
const MAX_HISTORY = 50;

const defaults = {
  language: "en",
  voiceNarration: true,
  phone: "",
  signedIn: false,
  history: [],
};

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...defaults };
    return { ...defaults, ...JSON.parse(raw) };
  } catch {
    // Private mode, blocked storage or corrupt JSON — carry on with defaults.
    return { ...defaults };
  }
}

const persisted = load();

function save() {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        language: persisted.language,
        voiceNarration: persisted.voiceNarration,
        phone: persisted.phone,
        signedIn: persisted.signedIn,
        history: persisted.history,
      }),
    );
  } catch {
    // Out of quota or storage denied: the session still works, it just will
    // not be remembered next time.
  }
}

export const state = {
  get language() {
    return persisted.language;
  },
  set language(value) {
    persisted.language = value;
    save();
  },

  get voiceNarration() {
    return persisted.voiceNarration;
  },
  set voiceNarration(value) {
    persisted.voiceNarration = Boolean(value);
    save();
  },

  get phone() {
    return persisted.phone;
  },
  set phone(value) {
    persisted.phone = value;
    save();
  },

  get signedIn() {
    return persisted.signedIn;
  },
  set signedIn(value) {
    persisted.signedIn = Boolean(value);
    save();
  },

  get history() {
    return persisted.history;
  },
};

/**
 * The photo currently being diagnosed, plus its prediction once it arrives.
 * Lives only for the life of the page.
 */
export const session = {
  /** @type {Blob|null} */
  imageBlob: null,
  /** @type {string|null} object URL for display */
  imageUrl: null,
  /** @type {object|null} prediction from inference/diagnose.js */
  prediction: null,
  /** @type {string[]} reasons the quality check rejected the photo */
  rejectReasons: [],
};

export function setSessionImage(blob) {
  if (session.imageUrl) URL.revokeObjectURL(session.imageUrl);
  session.imageBlob = blob;
  session.imageUrl = blob ? URL.createObjectURL(blob) : null;
  session.prediction = null;
  session.rejectReasons = [];
}

/** Add a completed check to the history. `thumb` is a small data URL. */
export function addHistoryEntry(entry) {
  persisted.history.unshift({ id: `check-${Date.now()}`, checkedAt: Date.now(), ...entry });
  persisted.history.length = Math.min(persisted.history.length, MAX_HISTORY);
  save();
}

export function findHistoryEntry(id) {
  return persisted.history.find((item) => item.id === id) ?? null;
}

export function clearHistory() {
  persisted.history.length = 0;
  save();
}

export function signOut() {
  persisted.signedIn = false;
  persisted.phone = "";
  save();
}
