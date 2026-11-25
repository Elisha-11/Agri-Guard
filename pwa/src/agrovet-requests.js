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
 * - Messages (PROPOSED endpoints, mock only until the backend confirms them):
 *   each open request has one message thread. A farmer message goes through
 *   the outbox like everything else (kind `agrovet_message`, idempotent on the
 *   message's own `client_id`) and is always sent after the request it belongs
 *   to. Its status is "queued" (waiting for signal), "sending", "sent" or
 *   "failed". Threads are fetched from GET …/{client_id}/messages/?since= when
 *   the request is opened, and on app open and signal back for any request
 *   whose `last_message_at` is newer than what the phone has.
 */

import { agrovetFetch, MESSAGE_MAX_LENGTH } from "./agrovet-api.js";
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

/**
 * True when a message looks like it holds a phone number: 9 or more digits,
 * allowing spaces, dashes and a leading +. Used to warn a farmer who chose not
 * to share their number before they type it into a message.
 */
export function looksLikePhoneNumber(text) {
  return /\+?\d(?:[\s-]?\d){8,}/.test(String(text ?? ""));
}

/** Why a message cannot be sent: "empty", "tooLong", or null when it is fine. */
export function messageProblem(text) {
  const body = String(text ?? "").trim();
  if (!body) return "empty";
  if (body.length > MESSAGE_MAX_LENGTH) return "tooLong";
  return null;
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
      async agrovet_message(item) {
        const mark = (change) =>
          update(item.request_client_id, (request) => ({
            messages: (request.messages ?? []).map((message) =>
              message.client_id === item.client_id ? { ...message, ...change } : message,
            ),
          }));

        mark({ status: "sending" });
        let response;
        try {
          response = await post(
            `/api/v1/agrovet-requests/${item.request_client_id}/messages/`,
            item.payload,
          );
        } catch (error) {
          mark({ status: "queued" }); // no signal after all: back to waiting
          throw error;
        }

        const outcome = outcomeOf(response);
        if (outcome === "done") {
          const body = await response.json().catch(() => null);
          mark({ ...(body ?? {}), sender: "farmer", status: "sent" });
        } else {
          mark({ status: outcome === "drop" ? "failed" : "queued" });
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
        messages: [],
        last_message_at: null,
        created_at: at,
        updated_at: at,
      });
      write(db);
      onChange();

      await outbox.add("agrovet_request", { client_id: clientId, payload });
      await flush();
      return this.find(clientId);
    },

    /** True when the farmer may send messages on this request. */
    canMessage(clientId) {
      const request = this.find(clientId);
      return Boolean(request) && request.status !== "closed" && request.status !== "failed";
    },

    /**
     * Add a message and try to send it. It shows straight away as "queued"
     * and goes out after the request itself has been sent. Returns null, and
     * saves nothing, for an empty or over-long message or a closed request.
     */
    async sendMessage(clientId, text) {
      const body = String(text ?? "").trim();
      if (messageProblem(body) || !this.canMessage(clientId)) return null;

      const message = {
        client_id: uuid(),
        sender: "farmer",
        text: body,
        created_at: new Date(now()).toISOString(),
        status: "queued",
      };
      update(clientId, (request) => ({ messages: [...(request.messages ?? []), message] }));
      await outbox.add("agrovet_message", {
        client_id: message.client_id,
        request_client_id: clientId,
        payload: { client_id: message.client_id, text: body },
      });
      await flush();
      return this.find(clientId).messages.find((item) => item.client_id === message.client_id);
    },

    /**
     * Fetch new chat messages for one request. Resolves to "updated" |
     * "unchanged" | "offline" | "auth" | "none"; never rejects.
     */
    async refreshMessages(clientId) {
      const request = this.find(clientId);
      if (!request || request.status === "queued" || request.status === "failed") return "none";

      try {
        const since = request.messages_since;
        const response = await fetchImpl(
          `/api/v1/agrovet-requests/${clientId}/messages/${
            since ? `?since=${encodeURIComponent(since)}` : ""
          }`,
          { cache: "no-store" },
        );
        if (response.status === 401) {
          authNeeded = true;
          return "auth";
        }
        if (!response.ok) return "offline";

        const body = await response.json();
        const incoming = Array.isArray(body) ? body : body?.results ?? [];
        if (!incoming.length) return "unchanged";

        update(clientId, (local) => {
          const messages = [...(local.messages ?? [])];
          let latest = local.messages_since ?? "";
          for (const remote of incoming) {
            const index = messages.findIndex(
              (message) =>
                (remote.client_id && message.client_id === remote.client_id) ||
                (remote.id && message.id === remote.id),
            );
            const merged = { ...remote, status: "sent" };
            if (index === -1) messages.push(merged);
            else messages[index] = { ...messages[index], ...merged };
            if (remote.created_at > latest) latest = remote.created_at;
          }
          return { messages, messages_since: latest };
        });
        return "updated";
      } catch {
        return "offline";
      }
    },

    /**
     * Fetch the thread of every request with messages the phone has not got
     * yet (its `last_message_at` is newer than the last message fetched).
     */
    async refreshAllMessages() {
      const stale = read().requests.filter(
        (request) =>
          request.status !== "queued" &&
          request.status !== "failed" &&
          request.last_message_at &&
          request.last_message_at > (request.messages_since ?? ""),
      );
      for (const request of stale) {
        if ((await this.refreshMessages(request.client_id)) === "auth") return "auth";
      }
      return stale.length ? "updated" : "unchanged";
    },

    /** Close a request, now or as soon as there is signal. */
    async close(clientId) {
      const request = this.find(clientId);
      if (!request || request.status === "closed") return;

      if (request.status === "queued" || request.status === "failed") {
        // Never reached the server: take it and its unsent messages out of the outbox.
        const pending = (await outbox.items()).filter(
          (item) =>
            (item.kind === "agrovet_request" && item.client_id === clientId) ||
            (item.kind === "agrovet_message" && item.request_client_id === clientId),
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
            last_message_at: remote.last_message_at ?? local.last_message_at ?? null,
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

    /** Send anything queued, then fetch replies and new messages. */
    async sync() {
      const sent = await flush();
      if (sent === "auth") return "auth";
      const refreshed = await this.refresh();
      if (refreshed === "auth") return "auth";
      await this.refreshAllMessages();
      return refreshed;
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
