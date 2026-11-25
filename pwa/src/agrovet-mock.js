/**
 * The fake agrovet server used while VITE_AGROVET_MOCK is on (see
 * src/agrovet-api.js). It answers the agrovet endpoints in memory, using only
 * the field names in the agrovet spec, so the screens can be built and
 * demonstrated before the backend serves them.
 *
 * It is only ever loaded through a dynamic import behind the switch, so a
 * production build (switch off) leaves this whole module, its fake shops and
 * their dummy numbers out of the bundle.
 *
 * The fake agrovets have made-up names and phone numbers (+260 00 …) that
 * cannot ring a real person.
 */

import { MESSAGE_MAX_LENGTH } from "./agrovet-api.js";

const MOCK_KEY = "agriguard.mock.agrovetServer";
const MOCK_ETAG = '"mock-directory-1"';

/** Seconds after sending before the fake agrovet has seen, then answered, a request. */
export const MOCK_SEEN_AFTER = 10;
export const MOCK_REPLY_AFTER = 30;
/** Seconds before a fake agrovet answers a message (Two never answers). */
export const MOCK_CHAT_REPLY_AFTER = 15;
const MOCK_CHAT_ANSWERS = {
  "demo-agrovet-1": "Demo message: Thank you. Please send a clear photo of the lower leaves too.",
  "demo-agrovet-3": "Demo message: We expect new stock on Monday. I will message you then.",
};

export const MOCK_AGROVETS = [
  {
    id: "demo-agrovet-1",
    name: "Demo Agrovet One",
    town: "Example Town",
    district: "Example District",
    province: "Example Province",
    location: { lat: -15.41, lng: 28.29 },
    phone: "+260000000001",
    whatsapp: "+260000000001",
    updated_at: "2026-11-25T08:00:00Z",
  },
  {
    id: "demo-agrovet-2",
    name: "Demo Agrovet Two",
    town: "Example Town",
    district: "Example District",
    province: "Example Province",
    location: { lat: -15.45, lng: 28.33 },
    phone: "+260000000002",
    whatsapp: null,
    updated_at: "2026-11-25T08:00:00Z",
  },
  {
    id: "demo-agrovet-3",
    name: "Demo Agrovet Three",
    town: "Other Town",
    district: "Other District",
    province: "Example Province",
    location: { lat: -15.6, lng: 28.5 },
    phone: "+260000000003",
    whatsapp: "+260000000003",
    updated_at: "2026-11-25T08:00:00Z",
  },
];

/** How each fake agrovet answers: One has it, Two never replies, Three is out of stock. */
const MOCK_REPLIES = {
  "demo-agrovet-1": {
    in_stock: true,
    price: { amount: 150, currency: "ZMW" },
    product: { id: null, name: "Demo product" },
    visit_farm: true,
    template_key: "can_visit",
    text: "Demo reply: I can visit your farm to discuss the symptoms and next steps.",
    lang: "en",
  },
  "demo-agrovet-3": {
    in_stock: false,
    price: null,
    product: null,
    visit_farm: false,
    template_key: "out_of_stock",
    text: "Demo reply: Not in stock this week. Please ask again on Monday.",
    lang: "en",
  },
};

function json(status, body, headers = {}) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => headers[name] ?? headers[name.toLowerCase()] ?? null },
    json: async () => body,
  });
}

export function createMockServer({ now = () => Date.now(), storage: given } = {}) {
  // Looked up on use, not at import: tests install a localStorage after importing.
  const storage = () => given ?? globalThis.localStorage;
  const load = () => {
    try {
      return JSON.parse(storage()?.getItem(MOCK_KEY) ?? "null") ?? { requests: [] };
    } catch {
      return { requests: [] };
    }
  };
  const save = (db) => {
    try {
      storage()?.setItem(MOCK_KEY, JSON.stringify(db));
    } catch {
      // a demo without storage just forgets its requests
    }
  };

  /** Move a request along sent → seen → replied as fake time passes. */
  const advance = (request) => {
    if (request.status === "closed") return request;
    const age = (now() - Date.parse(request.created_at)) / 1000;
    const reply = MOCK_REPLIES[request.agrovet_id];

    if (reply && age >= MOCK_REPLY_AFTER && !request.replies.length) {
      const at = new Date(Date.parse(request.created_at) + MOCK_REPLY_AFTER * 1000).toISOString();
      request.replies = [{ id: `${request.client_id}-r1`, created_at: at, ...reply }];
      request.status = "replied";
      request.updated_at = at;
    } else if (request.status === "sent" && age >= MOCK_SEEN_AFTER) {
      request.status = "seen";
      request.updated_at = new Date(
        Date.parse(request.created_at) + MOCK_SEEN_AFTER * 1000,
      ).toISOString();
    }
    return advanceChat(request);
  };

  /** The fake agrovet answers each farmer message once, a little later. */
  const advanceChat = (request) => {
    const answer = MOCK_CHAT_ANSWERS[request.agrovet_id];
    request.messages ??= [];
    if (!answer || request.status === "closed") return request;
    for (const message of request.messages) {
      if (message.sender !== "farmer" || message.answered) continue;
      if ((now() - Date.parse(message.created_at)) / 1000 < MOCK_CHAT_REPLY_AFTER) continue;
      message.answered = true;
      const at = new Date(now()).toISOString();
      request.messages.push({
        id: `${message.client_id}-answer`,
        request_client_id: request.client_id,
        sender: "agrovet",
        text: answer,
        created_at: at,
        lang: "en",
        template_key: null,
      });
      request.last_message_at = at;
      request.updated_at = at;
    }
    return request;
  };

  /** A message as the API returns it (no mock bookkeeping). */
  const publicMessage = ({ answered, ...message }) => {
    void answered;
    return message;
  };

  return {
    handle(path, init = {}) {
      const method = (init.method ?? "GET").toUpperCase();
      const url = new URL(path, "https://mock.invalid");
      const route = url.pathname;

      if (method === "GET" && route === "/api/v1/agrovets/") {
        const etag = init.headers?.["If-None-Match"];
        if (etag === MOCK_ETAG) return json(304, null);
        return json(200, MOCK_AGROVETS, { ETag: MOCK_ETAG });
      }

      if (method === "POST" && route === "/api/v1/agrovet-requests/") {
        const body = JSON.parse(init.body ?? "{}");
        if (!MOCK_AGROVETS.some((agrovet) => agrovet.id === body.agrovet_id)) {
          return json(400, { code: "agrovet_unavailable", message: "Agrovet not available" });
        }
        const db = load();
        let request = db.requests.find((item) => item.client_id === body.client_id);
        if (!request) {
          const at = new Date(now()).toISOString();
          request = {
            ...body,
            status: "sent",
            created_at: at,
            updated_at: at,
            replies: [],
            messages: [],
            last_message_at: null,
          };
          db.requests.push(request);
          save(db);
        }
        return json(201, request);
      }

      if (method === "GET" && route === "/api/v1/agrovet-requests/") {
        const since = url.searchParams.get("since");
        const db = load();
        db.requests.forEach(advance);
        save(db);
        const changed = db.requests
          .filter((item) => !since || item.updated_at > since)
          .map(({ messages: thread, ...item }) => {
            void thread; // the list carries last_message_at; the thread has its own endpoint
            return item;
          });
        return json(200, changed);
      }

      const messages = route.match(/^\/api\/v1\/agrovet-requests\/([^/]+)\/messages\/$/);
      if (messages) {
        const db = load();
        const request = db.requests.find((item) => item.client_id === messages[1]);
        if (!request) return json(404, { code: "not_found", message: "No such request" });
        advance(request);

        if (method === "GET") {
          save(db);
          const since = url.searchParams.get("since");
          return json(
            200,
            request.messages
              .filter((message) => !since || message.created_at > since)
              .map(publicMessage),
          );
        }

        if (method === "POST") {
          const body = JSON.parse(init.body ?? "{}");
          const text = String(body.text ?? "").trim();
          if (request.status === "closed") {
            return json(409, { code: "request_closed", message: "This request is closed" });
          }
          if (!text || text.length > MESSAGE_MAX_LENGTH) {
            return json(400, { code: "invalid_text", message: "Empty or too long" });
          }
          let message = request.messages.find((item) => item.client_id === body.client_id);
          if (!message) {
            const at = new Date(now()).toISOString();
            message = {
              id: `m-${body.client_id}`,
              client_id: body.client_id,
              request_client_id: request.client_id,
              sender: "farmer",
              text,
              created_at: at,
              lang: null,
              template_key: null,
            };
            request.messages.push(message);
            request.last_message_at = at;
            request.updated_at = at;
            save(db);
          }
          return json(201, publicMessage(message));
        }
      }

      const close = route.match(/^\/api\/v1\/agrovet-requests\/([^/]+)\/close\/$/);
      if (method === "POST" && close) {
        const db = load();
        const request = db.requests.find((item) => item.client_id === close[1]);
        if (!request) return json(404, { code: "not_found", message: "No such request" });
        if (request.status !== "closed") {
          request.status = "closed";
          request.updated_at = new Date(now()).toISOString();
          save(db);
        }
        return json(200, request); // closing twice is a success, as the spec asks
      }

      return json(404, { code: "not_found", message: `Mock has no ${method} ${route}` });
    },
  };
}

export const mockServer = createMockServer();
