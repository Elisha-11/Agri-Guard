/**
 * The offline write queue (docs/offline-sync.md, "Queue (PWA, IndexedDB store
 * `sync_queue`)").
 *
 * Anything the farmer does that must reach the server is written here first,
 * then sent when there is signal. Items go out oldest first. Each item carries
 * the `client_id` it was created with, so a resend after a dropped connection
 * can never create a duplicate on the server (every endpoint that takes queued
 * items is idempotent on `client_id`).
 *
 * Today only the agrovet requests use it (kinds `agrovet_request` and
 * `agrovet_close`). Diagnosis and feedback sync will add their own kinds.
 *
 * What a handler returns decides what happens to its item:
 *   "done"  sent (or the server already had it): remove it
 *   "drop"  the server refused it for good (e.g. a suspended agrovet): remove it
 *   "retry" no signal, a 5xx or a rate limit: keep it and stop for now
 *   "auth"  401: keep it and every item after it, stop, and ask to sign in again
 *
 * Storage is swappable so the tests run without a browser: `memoryStorage()`
 * here, IndexedDB in the app.
 */

const DB_NAME = "agriguard";
const STORE = "sync_queue";

/** IndexedDB storage for the queue. Falls back to memory where IndexedDB is missing. */
export function idbStorage() {
  if (typeof indexedDB === "undefined") return memoryStorage();

  let opening = null;
  const open = () =>
    (opening ??= new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    }));

  const run = async (mode, action) => {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const request = action(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(request?.result);
      tx.onerror = () => reject(tx.error);
    });
  };

  return {
    add: (item) => run("readwrite", (store) => store.add(item)),
    all: () => run("readonly", (store) => store.getAll()),
    remove: (id) => run("readwrite", (store) => store.delete(id)),
  };
}

/** In-memory storage with the same shape as `idbStorage()`. */
export function memoryStorage() {
  let items = [];
  let nextId = 1;
  return {
    add: async (item) => {
      const id = nextId++;
      items.push({ ...item, id });
      return id;
    },
    all: async () => items.map((item) => ({ ...item })),
    remove: async (id) => {
      items = items.filter((item) => item.id !== id);
    },
  };
}

/**
 * @param {{storage?: ReturnType<typeof memoryStorage>, handlers?: Record<string, (item: object) => Promise<string>>}} [options]
 */
export function createOutbox({ storage = idbStorage(), handlers = {} } = {}) {
  let flushing = null;
  let authNeeded = false;

  async function flushOnce() {
    const items = (await storage.all()).sort((a, b) => a.id - b.id);
    for (const item of items) {
      const handler = handlers[item.kind];
      if (!handler) continue; // a kind this build does not send: leave it for one that does

      let outcome;
      try {
        outcome = await handler(item);
      } catch {
        outcome = "retry"; // fetch throws when there is no connection at all
      }

      if (outcome === "done" || outcome === "drop") {
        await storage.remove(item.id);
        continue;
      }
      if (outcome === "auth") authNeeded = true;
      return outcome; // "retry" or "auth": keep this item and everything after it
    }
    authNeeded = false;
    return "empty";
  }

  return {
    /** Queue an item. Resolves once it is stored, before any sending. */
    async add(kind, data) {
      return storage.add({ kind, ...data, queued_at: Date.now() });
    },

    async items() {
      return (await storage.all()).sort((a, b) => a.id - b.id);
    },

    async remove(id) {
      return storage.remove(id);
    },

    /**
     * Send what is queued. Resolves to "empty" (all sent), "retry" or "auth".
     * Calls made while a flush is running share it rather than double-sending.
     */
    flush() {
      flushing ??= flushOnce().finally(() => {
        flushing = null;
      });
      return flushing;
    },

    /** True after a 401, until a later flush gets everything through. */
    get authNeeded() {
      return authNeeded;
    },
  };
}
