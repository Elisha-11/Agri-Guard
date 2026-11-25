/**
 * Farmer requests to agrovets (spec v2 §2–§7; mock switch in src/agrovet-api.js).
 *
 * - A request is saved on the phone and put in the outbox (src/outbox.js)
 *   before anything is sent, so it survives no signal, a closed app or a
 *   flat battery. Its `client_id` is made once and reused on every retry.
 * - Statuses: "queued" exists only on the phone (waiting for signal); "sent",
 *   "seen", "replied" and "closed" come from the server. "failed" is shown
 *   when the server refused the request for good (e.g. the agrovet was
 *   suspended).
 * - Closing works offline too: the close is queued like a request. Closing a
 *   request that never left the phone just takes it out of the outbox.
 * - Replies are fetched when the app opens, when signal comes back and when
 *   the farmer opens a request. There are no push notifications.
 * - The photo: until the backend picks a photo endpoint (spec §3), a shared
 *   photo is kept on the phone as a thumbnail and NOT uploaded.
 */

import { agrovetFetch } from "./agrovet-api.js";
import { createOutbox } from "./outbox.js";
import { AGROVETS_UPDATED, refreshDirectory } from "./agrovets.js";
import { currentLanguage } from "./i18n.js";

const KEY = "agriguard.agrovetRequests.v1";

/** The diagnosis a "Find agrovet" button was pressed from. Page-lifetime only. */
let context = null;

export function setRequestContext(value) {
  context = value;
}

export function requestContext() {
  return context;
}

/** "maize__streak" -> "maize". Maize is the only crop the model reads today. */
export function cropOf(classId) {
  return classId?.split("__")[0] || "maize";
}

/**
 * The POST body. Anything the farmer switched off is left out entirely, not
 * sent empty. The phone number is never in the body: `share_phone` only tells
 * the server whether the agrovet may see the number on the farmer's account.
 */
export function buildRequestPayload({
  clientId,
  agrovetId,
  classId = null,
  predictionStatus = null,
  district = null,
  description = "",
  share = {},
}) {
  const payload = {
    client_id: clientId,
    agrovet_id: agrovetId,
    crop: cropOf(classId),
    description: description.trim(),
    share_phone: share.phone === true,
  };
  if (share.diagnosis !== false && classId) payload.class_id = classId;
  if (share.diagnosis !== false && predictionStatus) payload.prediction_status = predictionStatus;
  if (share.district !== false && district) payload.district = district;
  return payload;
}

/** Which language a reply is shown in, and whether to say it fell back to English. */
export function replyLanguageNote(reply, lang = currentLanguage()) {
  return Boolean(reply?.lang) && reply.lang === "en" && lang !== "en";
}

const STATUS_RANK = { queued: 0, failed: 0, sent: 1, seen: 2, replied: 3, closed: 4 };

/**
 * @param {{storage?: Storage, fetchImpl?: typeof fetch, outboxStorage?: object, now?: () => number, uuid?: () => string, onChange?: () => void}} [deps]
 */
export function createAgrovetRequests(deps = {}) {
  const {
    fetchImpl = agrovetFetch,
    now = Date.now,
    uuid = () => crypto.randomUUID(),
    onChange = () => globalThis.window?.dispatchEvent?.(new Event(AGROVETS_UPDATED)),
  } = deps;

  // Looked up on use, not at import: tests install a localStorage after importing.
  const storage = () => deps.storage ?? globalThis.localStorage;

  const read = () => {
    try {
      return JSON.parse(storage().getItem(KEY) ?? "null") ?? { requests: [], since: null };
    } catch {
      return { requests: [], since: null };
    }
  };
  const write = (db) => {
    try {
      storage().setItem(KEY, JSON.stringify(db));
    } catch {
      // storage full: the request is still in the outbox and will be sent
    }
  };
  const update = (clientId, change) => {
    const db = read();
    const request = db.requests.find((item) => item.client_id === clientId);
    if (request) Object.assign(request, change(request));
    write(db);
    onChange();
  };

  const post = (path, body) =>
    fetchImpl(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });

  /** Turn an HTTP status into an outbox outcome. */
  const outcomeOf = (response) => {
    if (response.ok) return "done";
    if (response.status === 401) return "auth";
    if (response.status === 429 || response.status >= 500) return "retry";
    return "drop";
  };

  const outbox = createOutbox({
    ...(deps.outboxStorage ? { storage: deps.outboxStorage } : {}),
    handlers: {
      async agrovet_request(item) {
        const response = await post("/api/v1/agrovet-requests/", item.payload);
        const outcome = outcomeOf(response);
        if (outcome === "done") {
          const body = await response.json().catch(() => null);
          update(item.client_id, (request) => ({
            status: request.status === "closed" ? "closed" : body?.status ?? "sent",
            updated_at: body?.updated_at ?? request.updated_at,
          }));
        } else if (outcome === "drop") {
          update(item.client_id, () => ({ status: "failed" }));
        }
        return outcome;
      },
      async agrovet_close(item) {
        const response = await post(`/api/v1/agrovet-requests/${item.client_id}/close/`);
        const outcome = outcomeOf(response);
        if (outcome === "done" || outcome === "drop") {
          update(item.client_id, () => ({ closePending: false }));
        }
        return outcome;
      },
    },
  });

  let authNeeded = false;

  async function flush() {
    const result = await outbox.flush();
    authNeeded = result === "auth";
    return result;
  }

  return {
    outbox,

    list() {
      return [...read().requests].sort((a, b) => b.created_at.localeCompare(a.created_at));
    },

    find(clientId) {
      return read().requests.find((item) => item.client_id === clientId) ?? null;
    },

    get authNeeded() {
      return authNeeded;
    },

    /**
     * Save a request and try to send it. Resolves to the saved request, whose
     * status says whether it went ("sent") or is waiting ("queued").
     */
    async send({ agrovet, classId, predictionStatus, district, description, share, thumb }) {
      const clientId = uuid();
      const payload = buildRequestPayload({
        clientId,
        agrovetId: agrovet.id,
        classId,
        predictionStatus,
        district,
        description,
        share,
      });
      const at = new Date(now()).toISOString();

      const db = read();
      db.requests.push({
        ...payload,
        agrovet_name: agrovet.name,
        thumb: share.photo !== false && thumb ? thumb : null,
        status: "queued",
        closePending: false,
        replies: [],
        created_at: at,
        updated_at: at,
      });
      write(db);
      onChange();

      await outbox.add("agrovet_request", { client_id: clientId, payload });
      await flush();
      return this.find(clientId);
    },

    /** Close a request, now or as soon as there is signal. */
    async close(clientId) {
      const request = this.find(clientId);
      if (!request || request.status === "closed") return;

      if (request.status === "queued" || request.status === "failed") {
        // Never reached the server: take it out of the outbox, nothing to send.
        const pending = (await outbox.items()).filter(
          (item) => item.kind === "agrovet_request" && item.client_id === clientId,
        );
        await Promise.all(pending.map((item) => outbox.remove(item.id)));
        update(clientId, () => ({ status: "closed", closePending: false }));
        return;
      }

      update(clientId, () => ({ status: "closed", closePending: true }));
      await outbox.add("agrovet_close", { client_id: clientId });
      await flush();
    },

    /**
     * Fetch status changes and replies since the last check. Resolves to
     * "updated" | "unchanged" | "offline" | "auth" | "none"; never rejects.
     */
    async refresh() {
      const db = read();
      if (!db.requests.some((item) => item.status !== "queued")) return "none";

      try {
        const query = db.since ? `?since=${encodeURIComponent(db.since)}` : "";
        const response = await fetchImpl(`/api/v1/agrovet-requests/${query}`, {
          cache: "no-store",
        });
        if (response.status === 401) {
          authNeeded = true;
          return "auth";
        }
        if (!response.ok) return "offline";

        const body = await response.json();
        const changed = Array.isArray(body) ? body : body?.results ?? [];
        const fresh = read();
        for (const remote of changed) {
          const local = fresh.requests.find((item) => item.client_id === remote.client_id);
          if (!local) continue;
          // A close made on the phone wins until the server has it.
          const status =
            local.closePending || STATUS_RANK[local.status] > STATUS_RANK[remote.status]
              ? local.status
              : remote.status;
          Object.assign(local, {
            status,
            updated_at: remote.updated_at ?? local.updated_at,
            replies: remote.replies ?? local.replies,
          });
          if (!fresh.since || (remote.updated_at && remote.updated_at > fresh.since)) {
            fresh.since = remote.updated_at;
          }
        }
        write(fresh);
        if (changed.length) onChange();
        return changed.length ? "updated" : "unchanged";
      } catch {
        return "offline";
      }
    },

    /** Send anything queued, then fetch replies. */
    async sync() {
      const sent = await flush();
      if (sent === "auth") return "auth";
      return this.refresh();
    },
  };
}

export const agrovetRequests = createAgrovetRequests();

/** Directory and requests: now, and whenever the phone gets signal back. */
export function startAgrovetSync() {
  const run = () => {
    refreshDirectory();
    agrovetRequests.sync();
  };
  run();
  window.addEventListener("online", run);
}
