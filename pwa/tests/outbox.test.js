/**
 * The offline write queue (src/outbox.js, docs/offline-sync.md).
 */

import { describe, expect, it } from "vitest";
import { createOutbox, memoryStorage } from "../src/outbox.js";

function outboxWith(handler) {
  const calls = [];
  const outbox = createOutbox({
    storage: memoryStorage(),
    handlers: {
      thing: async (item) => {
        calls.push(item.client_id);
        return handler(item, calls.length);
      },
    },
  });
  return { outbox, calls };
}

describe("outbox", () => {
  it("sends items oldest first and removes them once sent", async () => {
    const { outbox, calls } = outboxWith(async () => "done");
    await outbox.add("thing", { client_id: "a" });
    await outbox.add("thing", { client_id: "b" });

    expect(await outbox.flush()).toBe("empty");
    expect(calls).toEqual(["a", "b"]);
    expect(await outbox.items()).toEqual([]);
  });

  it("keeps an item and stops when there is no signal", async () => {
    const { outbox, calls } = outboxWith(async () => {
      throw new TypeError("Failed to fetch");
    });
    await outbox.add("thing", { client_id: "a" });
    await outbox.add("thing", { client_id: "b" });

    expect(await outbox.flush()).toBe("retry");
    expect(calls).toEqual(["a"]);
    expect((await outbox.items()).map((item) => item.client_id)).toEqual(["a", "b"]);
  });

  it("stops on a 401, keeps every item, and clears once sending works again", async () => {
    let signedIn = false;
    const { outbox, calls } = outboxWith(async () => (signedIn ? "done" : "auth"));
    await outbox.add("thing", { client_id: "a" });
    await outbox.add("thing", { client_id: "b" });

    expect(await outbox.flush()).toBe("auth");
    expect(outbox.authNeeded).toBe(true);
    expect(calls).toEqual(["a"]);
    expect(await outbox.items()).toHaveLength(2);

    signedIn = true;
    expect(await outbox.flush()).toBe("empty");
    expect(outbox.authNeeded).toBe(false);
  });

  it("removes an item the server refused for good", async () => {
    const { outbox } = outboxWith(async () => "drop");
    await outbox.add("thing", { client_id: "a" });
    expect(await outbox.flush()).toBe("empty");
    expect(await outbox.items()).toEqual([]);
  });

  it("does not double-send when two flushes overlap", async () => {
    const { outbox, calls } = outboxWith(async () => "done");
    await outbox.add("thing", { client_id: "a" });
    await Promise.all([outbox.flush(), outbox.flush()]);
    expect(calls).toEqual(["a"]);
  });

  it("leaves kinds it has no handler for in the queue", async () => {
    const { outbox } = outboxWith(async () => "done");
    await outbox.add("diagnosis", { client_id: "d" });
    expect(await outbox.flush()).toBe("empty");
    expect(await outbox.items()).toHaveLength(1);
  });
});
