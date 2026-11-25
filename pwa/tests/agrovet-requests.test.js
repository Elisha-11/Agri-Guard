/**
 * Farmer requests to agrovets (src/agrovet-requests.js) and the mock server
 * that stands in for API contract 0.6.0 (src/agrovet-mock.js).
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  buildRequestPayload,
  createAgrovetRequests,
  cropOf,
  replyLanguageNote,
} from "../src/agrovet-requests.js";
import { createMockServer, MOCK_REPLY_AFTER, MOCK_SEEN_AFTER } from "../src/agrovet-mock.js";
import { memoryStorage } from "../src/outbox.js";

function memoryLocalStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
}

const response = (status, body = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
  headers: { get: () => null },
});

const offline = async () => {
  throw new TypeError("Failed to fetch");
};

const agrovet = { id: "demo-agrovet-1", name: "Demo Agrovet One" };
const form = {
  agrovet,
  classId: "maize__streak",
  predictionStatus: "confident",
  district: "Example District",
  description: " Pale streaks  ",
  share: { photo: true, diagnosis: true, district: true, phone: false },
  thumb: "data:image/jpeg;base64,xx",
};

/** A requests instance whose network is whatever `server` says right now. */
function setup() {
  const calls = [];
  let server = offline;
  let ids = 0;
  const requests = createAgrovetRequests({
    storage: memoryLocalStorage(),
    outboxStorage: memoryStorage(),
    uuid: () => `id-${++ids}`,
    now: () => Date.parse("2026-11-25T10:00:00Z"),
    onChange: () => {},
    fetchImpl: async (path, init = {}) => {
      calls.push({ path, method: init.method ?? "GET", body: init.body && JSON.parse(init.body) });
      return server(path, init);
    },
  });
  return { requests, calls, setServer: (fn) => (server = fn) };
}

describe("request payload", () => {
  const base = { clientId: "c1", agrovetId: "a1" };

  it("leaves the phone number off by default", () => {
    const payload = buildRequestPayload({ ...base, classId: "maize__streak" });
    expect(payload.share_phone).toBe(false);
    expect(Object.keys(payload)).not.toContain("phone");
  });

  it("shares only what is switched on, and leaves the rest out entirely", () => {
    const all = buildRequestPayload({
      ...base,
      classId: "maize__streak",
      predictionStatus: "confident",
      district: "Chongwe",
      description: "  yellow lines ",
      share: { diagnosis: true, district: true, phone: true },
    });
    expect(all).toEqual({
      client_id: "c1",
      agrovet_id: "a1",
      crop: "maize",
      description: "yellow lines",
      share_phone: true,
      class_id: "maize__streak",
      prediction_status: "confident",
      district: "Chongwe",
    });

    const none = buildRequestPayload({
      ...base,
      classId: "maize__streak",
      predictionStatus: "confident",
      district: "Chongwe",
      share: { diagnosis: false, district: false, phone: false },
    });
    expect(none).not.toHaveProperty("class_id");
    expect(none).not.toHaveProperty("prediction_status");
    expect(none).not.toHaveProperty("district");
    expect(Object.values(none)).not.toContain(null);
    expect(Object.values(none)).not.toContain(undefined);
  });

  it("does not send a district the app does not know", () => {
    expect(buildRequestPayload({ ...base, share: { district: true } })).not.toHaveProperty(
      "district",
    );
  });

  it("reads the crop from the class id, maize when there is none", () => {
    expect(cropOf("soybean__rust")).toBe("soybean");
    expect(cropOf(null)).toBe("maize");
  });
});

describe("sending requests", () => {
  it("sends straight away with signal", async () => {
    const { requests, calls, setServer } = setup();
    setServer(async () => response(201, { status: "sent", updated_at: "2026-11-25T10:00:01Z" }));

    const saved = await requests.send(form);
    expect(saved.status).toBe("sent");
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ path: "/api/v1/agrovet-requests/", method: "POST" });
    expect(calls[0].body).toEqual({
      client_id: "id-1",
      agrovet_id: "demo-agrovet-1",
      crop: "maize",
      description: "Pale streaks",
      share_phone: false,
      class_id: "maize__streak",
      prediction_status: "confident",
      district: "Example District",
    });
    expect(await requests.outbox.items()).toEqual([]);
  });

  it("queues offline, then sends with the same client_id when signal returns", async () => {
    const { requests, calls, setServer } = setup();

    const saved = await requests.send(form);
    expect(saved.status).toBe("queued");
    expect(await requests.outbox.items()).toHaveLength(1);

    setServer(async () => response(503));
    await requests.sync();
    expect(requests.find("id-1").status).toBe("queued");

    setServer(async () => response(201, { status: "sent" }));
    await requests.sync();

    const posts = calls.filter((call) => call.method === "POST");
    expect(posts).toHaveLength(3);
    expect(new Set(posts.map((call) => call.body.client_id))).toEqual(new Set(["id-1"]));
    expect(requests.find("id-1").status).toBe("sent");
    expect(await requests.outbox.items()).toEqual([]);
  });

  it("stops on a 401 and keeps everything queued", async () => {
    const { requests, calls, setServer } = setup();
    await requests.send(form);
    await requests.send({ ...form, agrovet: { id: "demo-agrovet-2", name: "Two" } });

    setServer(async () => response(401));
    expect(await requests.sync()).toBe("auth");
    expect(requests.authNeeded).toBe(true);
    // One attempt at the first item, nothing after it.
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(3);
    expect(await requests.outbox.items()).toHaveLength(2);
    expect(requests.list().every((request) => request.status === "queued")).toBe(true);
  });

  it("marks a request the server refuses for good as not sent", async () => {
    const { requests, setServer } = setup();
    setServer(async () => response(400, { code: "agrovet_unavailable", message: "x" }));
    const saved = await requests.send(form);
    expect(saved.status).toBe("failed");
    expect(await requests.outbox.items()).toEqual([]);
  });

  it("keeps the photo on the phone only when it is shared", async () => {
    const { requests } = setup();
    expect((await requests.send(form)).thumb).toBe(form.thumb);
    expect((await requests.send({ ...form, share: { ...form.share, photo: false } })).thumb).toBe(
      null,
    );
  });
});

describe("request status and replies", () => {
  it("follows sent → seen → replied, and keeps the replies", async () => {
    const { requests, setServer } = setup();
    setServer(async () => response(201, { status: "sent", updated_at: "2026-11-25T10:00:00Z" }));
    await requests.send(form);

    setServer(async () =>
      response(200, [{ client_id: "id-1", status: "seen", updated_at: "2026-11-25T10:01:00Z" }]),
    );
    await requests.refresh();
    expect(requests.find("id-1").status).toBe("seen");

    const reply = { id: "r1", in_stock: true, price: { amount: 150, currency: "ZMW" }, lang: "en" };
    setServer(async (path) => {
      expect(path).toContain(`since=${encodeURIComponent("2026-11-25T10:01:00Z")}`);
      return response(200, [
        {
          client_id: "id-1",
          status: "replied",
          updated_at: "2026-11-25T10:02:00Z",
          replies: [reply],
        },
      ]);
    });
    await requests.refresh();
    expect(requests.find("id-1")).toMatchObject({ status: "replied", replies: [reply] });
  });

  it("closes offline and sends the close later; the local close wins meanwhile", async () => {
    const { requests, calls, setServer } = setup();
    setServer(async () => response(201, { status: "sent" }));
    await requests.send(form);

    setServer(offline);
    await requests.close("id-1");
    expect(requests.find("id-1")).toMatchObject({ status: "closed", closePending: true });

    setServer(async (path, init) =>
      init.method === "POST"
        ? response(200, { status: "closed" })
        : response(200, [{ client_id: "id-1", status: "replied", updated_at: "z" }]),
    );
    await requests.sync();
    expect(calls.some((call) => call.path === "/api/v1/agrovet-requests/id-1/close/")).toBe(true);
    expect(requests.find("id-1")).toMatchObject({ status: "closed", closePending: false });
  });

  it("closing a request that never left the phone just takes it out of the outbox", async () => {
    const { requests, calls } = setup();
    await requests.send(form);
    await requests.close("id-1");
    expect(requests.find("id-1").status).toBe("closed");
    expect(await requests.outbox.items()).toEqual([]);
    expect(calls.some((call) => call.path.includes("/close/"))).toBe(false);
  });
});

describe("reply language", () => {
  it("says so when a reply fell back to English", () => {
    expect(replyLanguageNote({ lang: "en" }, "ny")).toBe(true);
  });

  it("says nothing when the reply is in the farmer's language", () => {
    expect(replyLanguageNote({ lang: "en" }, "en")).toBe(false);
    expect(replyLanguageNote({ lang: "ny" }, "ny")).toBe(false);
  });
});

describe("mock server", () => {
  let clock;
  let server;
  const at = (seconds) => (clock = Date.parse("2026-11-25T10:00:00Z") + seconds * 1000);
  const call = async (path, init) => {
    const res = await server.handle(path, init);
    return { status: res.status, body: await res.json() };
  };
  const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body) });

  beforeEach(() => {
    at(0);
    server = createMockServer({ now: () => clock, storage: memoryLocalStorage() });
  });

  it("answers the directory with an ETag and a 304 when unchanged", async () => {
    const first = await server.handle("/api/v1/agrovets/", {});
    expect(first.status).toBe(200);
    const etag = first.headers.get("ETag");
    expect(
      (await server.handle("/api/v1/agrovets/", { headers: { "If-None-Match": etag } })).status,
    ).toBe(304);
  });

  it("is idempotent on client_id and moves a request along over time", async () => {
    const body = {
      client_id: "c1",
      agrovet_id: "demo-agrovet-1",
      crop: "maize",
      share_phone: false,
    };
    await post("/api/v1/agrovet-requests/", body);
    await post("/api/v1/agrovet-requests/", body);
    expect((await call("/api/v1/agrovet-requests/")).body).toHaveLength(1);

    at(MOCK_SEEN_AFTER);
    expect((await call("/api/v1/agrovet-requests/")).body[0].status).toBe("seen");

    at(MOCK_REPLY_AFTER);
    const [replied] = (await call("/api/v1/agrovet-requests/")).body;
    expect(replied.status).toBe("replied");
    expect(replied.replies[0]).toMatchObject({ in_stock: true, visit_farm: true, lang: "en" });
  });

  it("treats closing twice as success", async () => {
    await post("/api/v1/agrovet-requests/", { client_id: "c1", agrovet_id: "demo-agrovet-2" });
    expect((await post("/api/v1/agrovet-requests/c1/close/")).status).toBe(200);
    expect((await post("/api/v1/agrovet-requests/c1/close/")).status).toBe(200);
  });

  it("refuses an agrovet it does not know", async () => {
    expect(
      (await post("/api/v1/agrovet-requests/", { client_id: "c1", agrovet_id: "x" })).status,
    ).toBe(400);
  });
});
