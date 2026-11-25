/**
 * Messages on an agrovet request: the outbox, the proposed endpoints as the
 * mock answers them (src/agrovet-mock.js), and the thread on screen 13
 * (src/screens/message-thread.js).
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { initI18n, t } from "../src/i18n.js";
import {
  agrovetRequests as appRequests,
  createAgrovetRequests,
  looksLikePhoneNumber,
  messageProblem,
} from "../src/agrovet-requests.js";
import { MESSAGE_MAX_LENGTH } from "../src/agrovet-api.js";
import { createMockServer, MOCK_CHAT_REPLY_AFTER } from "../src/agrovet-mock.js";
import { memoryStorage } from "../src/outbox.js";
import * as requestDetail from "../src/screens/request-detail.js";
import {
  bindThread,
  hintFor,
  messageBubble,
  QUICK_REPLIES,
} from "../src/screens/message-thread.js";

function memoryLocalStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
}

const json = (status, body = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
  headers: { get: () => null },
});

const form = {
  agrovet: { id: "demo-agrovet-1", name: "Demo Agrovet One" },
  classId: "maize__streak",
  predictionStatus: "confident",
  district: null,
  description: "Pale streaks",
  share: { photo: false, diagnosis: true, district: false, phone: false },
};

/**
 * Requests wired to the real mock server. `network` can be swapped to go
 * offline or to answer with a fixed status; `wait` moves the fake clock.
 */
function setup() {
  let clock = Date.parse("2026-11-25T10:00:00Z");
  let ids = 0;
  const server = createMockServer({ now: () => clock, storage: memoryLocalStorage() });
  const calls = [];
  const statuses = [];
  let network = (path, init) => server.handle(path, init);
  const requests = createAgrovetRequests({
    storage: memoryLocalStorage(),
    outboxStorage: memoryStorage(),
    uuid: () => `id-${++ids}`,
    now: () => clock,
    onChange: () => {
      const message = requests.list()[0]?.messages?.at(-1);
      if (message) statuses.push(message.status);
    },
    fetchImpl: (path, init = {}) => {
      calls.push({ path, method: init.method ?? "GET", body: init.body && JSON.parse(init.body) });
      return network(path, init);
    },
  });
  return {
    requests,
    calls,
    statuses,
    offline: () =>
      (network = async () => {
        throw new TypeError("Failed to fetch");
      }),
    respond: (status) => (network = async () => json(status)),
    online: () => (network = (path, init) => server.handle(path, init)),
    wait: (seconds) => (clock += seconds * 1000),
  };
}

const messagePosts = (calls) =>
  calls.filter((call) => call.method === "POST" && call.path.endsWith("/messages/"));

beforeAll(async () => {
  globalThis.localStorage ??= memoryLocalStorage();
  const localeUrl = new URL("../public/locales/en/translation.json", import.meta.url);
  globalThis.fetch = async (url) =>
    String(url).includes("/locales/en/")
      ? { ok: true, json: async () => JSON.parse(readFileSync(fileURLToPath(localeUrl), "utf8")) }
      : { ok: false };
  await initI18n("en");
});

describe("sending messages through the outbox", () => {
  it("sends online, going from sending to sent", async () => {
    const { requests, calls, statuses } = setup();
    const request = await requests.send(form);

    const message = await requests.sendMessage(request.client_id, "  Is it in stock?  ");
    expect(message).toMatchObject({ sender: "farmer", text: "Is it in stock?", status: "sent" });
    expect(statuses).toContain("sending");
    expect(messagePosts(calls)[0].body).toEqual({
      client_id: message.client_id,
      text: "Is it in stock?",
    });
    expect(await requests.outbox.items()).toEqual([]);
  });

  it("keeps a message offline as waiting for signal, behind its request", async () => {
    const { requests, offline } = setup();
    offline();
    const request = await requests.send(form);
    const message = await requests.sendMessage(request.client_id, "Hello");

    expect(message.status).toBe("queued");
    expect((await requests.outbox.items()).map((item) => item.kind)).toEqual([
      "agrovet_request",
      "agrovet_message",
    ]);
  });

  it("sends it later with the same client_id, and only after the request", async () => {
    const { requests, calls, offline, online } = setup();
    offline();
    const request = await requests.send(form);
    const message = await requests.sendMessage(request.client_id, "Hello");
    await requests.sync(); // still offline: another failed try

    online();
    await requests.sync();

    const posts = calls.filter((call) => call.method === "POST");
    const lastRequestPost = posts.map((call) => call.path).lastIndexOf("/api/v1/agrovet-requests/");
    const firstMessagePost = posts.findIndex((call) => call.path.endsWith("/messages/"));
    expect(firstMessagePost).toBeGreaterThan(lastRequestPost);
    expect(new Set(messagePosts(calls).map((call) => call.body.client_id))).toEqual(
      new Set([message.client_id]),
    );
    expect(requests.find(request.client_id).messages[0].status).toBe("sent");
    expect(await requests.outbox.items()).toEqual([]);
  });

  it("keeps everything queued on a 401", async () => {
    const { requests, respond } = setup();
    const request = await requests.send(form); // sent while online
    respond(401);
    const message = await requests.sendMessage(request.client_id, "Hello");
    await requests.sendMessage(request.client_id, "Are you there?");

    expect(message.status).toBe("queued");
    expect(requests.authNeeded).toBe(true);
    expect(await requests.outbox.items()).toHaveLength(2);
    expect(requests.find(request.client_id).messages.every((m) => m.status === "queued")).toBe(
      true,
    );
  });

  it("cannot send on a closed request", async () => {
    const { requests, calls } = setup();
    const request = await requests.send(form);
    await requests.close(request.client_id);

    expect(requests.canMessage(request.client_id)).toBe(false);
    expect(await requests.sendMessage(request.client_id, "Hello")).toBeNull();
    expect(messagePosts(calls)).toHaveLength(0);
  });

  it("drops the unsent messages of a request closed before it left the phone", async () => {
    const { requests, offline } = setup();
    offline();
    const request = await requests.send(form);
    await requests.sendMessage(request.client_id, "Hello");
    await requests.close(request.client_id);
    expect(await requests.outbox.items()).toEqual([]);
  });

  it("blocks empty and over-long messages without saving them", async () => {
    const { requests } = setup();
    const request = await requests.send(form);
    expect(await requests.sendMessage(request.client_id, "   ")).toBeNull();
    expect(
      await requests.sendMessage(request.client_id, "x".repeat(MESSAGE_MAX_LENGTH + 1)),
    ).toBeNull();
    expect(await requests.sendMessage(request.client_id, "x".repeat(MESSAGE_MAX_LENGTH))).not.toBe(
      null,
    );
    expect(requests.find(request.client_id).messages).toHaveLength(1);
  });
});

describe("fetching messages", () => {
  it("fetches the agrovet's answer once, without duplicating the farmer's message", async () => {
    const { requests, wait } = setup();
    const request = await requests.send(form);
    await requests.sendMessage(request.client_id, "Do you deliver?");

    wait(MOCK_CHAT_REPLY_AFTER);
    expect(await requests.refreshMessages(request.client_id)).toBe("updated");
    expect(await requests.refreshMessages(request.client_id)).toBe("unchanged");

    const thread = requests.find(request.client_id).messages;
    expect(thread.map((message) => message.sender)).toEqual(["farmer", "agrovet"]);
    expect(thread[1]).toMatchObject({ request_client_id: request.client_id, lang: "en" });
  });

  it("on app open or signal back, fetches only threads with new messages", async () => {
    const { requests, calls, wait } = setup();
    const busy = await requests.send(form);
    const quiet = await requests.send({
      ...form,
      agrovet: { id: "demo-agrovet-2", name: "Demo Agrovet Two" },
    });
    await requests.sendMessage(busy.client_id, "Hello");
    await requests.refreshMessages(busy.client_id); // the phone is up to date

    wait(MOCK_CHAT_REPLY_AFTER);
    calls.length = 0;
    await requests.sync(); // what app open and the "online" event run

    const threadGets = calls.filter(
      (call) => call.method === "GET" && call.path.includes("/messages/"),
    );
    expect(threadGets.map((call) => call.path.split("/")[4])).toEqual([busy.client_id]);
    expect(requests.find(busy.client_id).messages.at(-1).sender).toBe("agrovet");
    expect(requests.find(quiet.client_id).messages).toEqual([]);
  });
});

describe("message checks", () => {
  it("says why a message cannot be sent", () => {
    expect(messageProblem("  ")).toBe("empty");
    expect(messageProblem("x".repeat(MESSAGE_MAX_LENGTH + 1))).toBe("tooLong");
    expect(messageProblem("Hello")).toBeNull();
    expect(MESSAGE_MAX_LENGTH).toBe(1000);

    expect(hintFor("", { submitted: true })).toEqual({
      error: true,
      text: "Type a message first.",
    });
    expect(hintFor("x".repeat(1001)).text).toBe(
      "This message is too long. Keep it under 1000 characters.",
    );
    expect(hintFor("x".repeat(950))).toEqual({ error: false, text: "950 of 1000 characters" });
    expect(hintFor("Hello").text).toBe("");
  });

  it("spots phone numbers but leaves ordinary messages alone", () => {
    expect(looksLikePhoneNumber("call me on 0977 123 456")).toBe(true);
    expect(looksLikePhoneNumber("+260 97 712 3456")).toBe(true);
    expect(looksLikePhoneNumber("I need 2 bags for 3 hectares")).toBe(false);
    expect(looksLikePhoneNumber("Price K150 for 25 kg")).toBe(false);
  });
});

describe("mock message endpoints", () => {
  let server;
  const call = async (path, init) => {
    const res = await server.handle(path, init);
    return { status: res.status, body: await res.json() };
  };
  const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body) });
  const base = "/api/v1/agrovet-requests/";

  beforeEach(async () => {
    server = createMockServer({ now: () => Date.now(), storage: memoryLocalStorage() });
    await post(base, { client_id: "r1", agrovet_id: "demo-agrovet-2", crop: "maize" });
  });

  it("is idempotent on client_id and fills request_client_id from the URL", async () => {
    await post(`${base}r1/messages/`, { client_id: "m1", text: "Hi" });
    await post(`${base}r1/messages/`, { client_id: "m1", text: "Hi" });
    const { body } = await call(`${base}r1/messages/`);
    expect(body).toHaveLength(1);
    expect(body[0]).toMatchObject({
      client_id: "m1",
      request_client_id: "r1",
      sender: "farmer",
      text: "Hi",
    });
  });

  it("refuses empty, over-long and closed-request messages", async () => {
    expect((await post(`${base}r1/messages/`, { client_id: "a", text: " " })).status).toBe(400);
    expect(
      (await post(`${base}r1/messages/`, { client_id: "b", text: "x".repeat(1001) })).status,
    ).toBe(400);
    await post(`${base}r1/close/`);
    expect((await post(`${base}r1/messages/`, { client_id: "c", text: "Hi" })).status).toBe(409);
  });
});

describe("message thread on the request screen", () => {
  const request = {
    client_id: "c1",
    agrovet_name: "Demo Agrovet One",
    crop: "maize",
    class_id: "maize__streak",
    prediction_status: "confident",
    description: "Pale streaks",
    share_phone: false,
    status: "replied",
    created_at: "2026-11-25T10:00:00Z",
    replies: [{ id: "r1", in_stock: true, created_at: "2026-11-25T10:00:30Z", lang: "en" }],
    messages: [
      // stored out of order on purpose: the thread sorts by time
      {
        client_id: "m3",
        sender: "farmer",
        text: "Thank you",
        created_at: "2026-11-25T10:03:00Z",
        status: "queued",
      },
      {
        client_id: "m1",
        sender: "farmer",
        text: "Can you deliver?",
        created_at: "2026-11-25T10:01:00Z",
        status: "sent",
      },
      {
        id: "a1",
        sender: "agrovet",
        text: "Yes, on Friday.",
        created_at: "2026-11-25T10:02:00Z",
        lang: "en",
      },
    ],
  };

  it("puts the thread below the reply card, in time order, on the right sides", () => {
    const html = requestDetail.render({}, { request, lang: "en" });
    const at = (text) => html.indexOf(text);
    expect(at("In stock")).toBeLessThan(at("Can you deliver?"));
    expect(at("Can you deliver?")).toBeLessThan(at("Yes, on Friday."));
    expect(at("Yes, on Friday.")).toBeLessThan(at("Thank you"));

    const sides = [...html.matchAll(/ag-av-msg--(farmer|agrovet)/g)].map((match) => match[1]);
    expect(sides).toEqual(["farmer", "agrovet", "farmer"]);
  });

  it("shows each farmer message's status", () => {
    expect(messageBubble({ ...request.messages[1], status: "sending" })).toContain("Sending…");
    expect(messageBubble(request.messages[1])).toContain("Sent");
    expect(messageBubble(request.messages[0])).toContain("Waiting for signal");
  });

  it("notes English on an agrovet message for a farmer using another language", () => {
    expect(messageBubble(request.messages[2], "ny")).toContain("Shown in English");
    expect(messageBubble(request.messages[2], "en")).not.toContain("Shown in English");
  });

  it("offers the quick replies and a message box while the request is open", () => {
    const html = requestDetail.render({}, { request, lang: "en" });
    expect(html).toContain('id="ag-av-compose"');
    for (const key of QUICK_REPLIES) expect(html).toContain(t(key));
    expect(html).toContain("Can you send prices?");
    expect(html).toContain("Can you visit my farm?");
  });

  it("hides the message box on a closed request and says why", () => {
    const html = requestDetail.render(
      {},
      { request: { ...request, status: "closed" }, lang: "en" },
    );
    expect(html).toContain("Yes, on Friday.");
    expect(html).not.toContain('id="ag-av-compose"');
    expect(html).not.toContain("data-quick");
    expect(html).toContain(t("message.closed"));
    expect(html).toContain("Closed");
  });
});

describe("message box behaviour", () => {
  /** Just enough of a DOM for bindThread: the elements it looks up by id. */
  function fakeScreen() {
    const element = (extra = {}) => {
      const listeners = {};
      return {
        value: "",
        hidden: false,
        textContent: "",
        dataset: {},
        classList: { toggle() {} },
        focus() {},
        setSelectionRange() {},
        addEventListener: (type, fn) => (listeners[type] = fn),
        fire: (type) => listeners[type]?.({ preventDefault() {} }),
        ...extra,
      };
    };
    const els = {
      "#ag-av-compose": element(),
      "#ag-av-message": element(),
      "#ag-av-message-hint": element(),
      "#ag-av-phone-warning": element({ hidden: true }),
      "#ag-av-send-anyway": element(),
      "#ag-av-edit-message": element(),
    };
    const chips = QUICK_REPLIES.map((key) => element({ dataset: { quick: key } }));
    return {
      els,
      chips,
      querySelector: (selector) => els[selector] ?? null,
      querySelectorAll: () => chips,
    };
  }

  beforeEach(() => {
    globalThis.localStorage = memoryLocalStorage();
  });

  it("fills the box from a quick reply, editable, without sending", async () => {
    const screen = fakeScreen();
    let sent = 0;
    bindThread(screen, "nope", { onSent: () => sent++ });

    screen.chips[0].fire("click");
    expect(screen.els["#ag-av-message"].value).toBe("Can you send prices?");
    screen.els["#ag-av-message"].value += " For 2 bags.";
    expect(screen.els["#ag-av-message"].value).toBe("Can you send prices? For 2 bags.");
    expect(sent).toBe(0);
  });

  it("says why an empty message was not sent", () => {
    const screen = fakeScreen();
    bindThread(screen, "nope");
    screen.els["#ag-av-compose"].fire("submit");
    expect(screen.els["#ag-av-message-hint"].textContent).toBe("Type a message first.");
  });

  it("asks before sending a phone number the farmer chose not to share", async () => {
    const request = await appRequests.send({ ...form, share: { ...form.share, phone: false } });
    const screen = fakeScreen();
    bindThread(screen, request.client_id);

    screen.els["#ag-av-message"].value = "Call me on 0977 123 456";
    screen.els["#ag-av-compose"].fire("submit");
    expect(screen.els["#ag-av-phone-warning"].hidden).toBe(false);
    expect(screen.els["#ag-av-compose"].hidden).toBe(true);
    expect(appRequests.find(request.client_id).messages).toEqual([]);
  });
});
