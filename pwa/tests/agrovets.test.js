/**
 * The agrovet directory: distance sorting, the no-location case and the
 * ETag cache (src/agrovets.js).
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  cachedDirectory,
  distanceKm,
  refreshDirectory,
  sortAgrovets,
  whatsappUrl,
} from "../src/agrovets.js";

const store = new Map();
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, String(value)),
  removeItem: (key) => store.delete(key),
};

const here = { lat: -15.4, lng: 28.3 };
const shops = [
  { id: "far", name: "Far", district: "A", location: { lat: -15.8, lng: 28.3 } },
  { id: "near", name: "Near", district: "B", location: { lat: -15.41, lng: 28.3 } },
  { id: "mid", name: "Mid", district: "A", location: { lat: -15.5, lng: 28.3 } },
  { id: "unknown", name: "Aardvark", district: "A", location: null },
];

describe("agrovet sorting", () => {
  it("puts the closest first when location is on, with km to one decimal", () => {
    const sorted = sortAgrovets(shops, { location: here });
    expect(sorted.mode).toBe("distance");
    expect(sorted.items.map((shop) => shop.id)).toEqual(["near", "mid", "far", "unknown"]);
    expect(sorted.items[0].km).toBe(1.1);
    expect(sorted.items[3].km).toBeNull();
  });

  it("breaks distance ties by name", () => {
    const twins = [
      { id: "2", name: "Zed", location: here },
      { id: "1", name: "Abe", location: here },
    ];
    expect(sortAgrovets(twins, { location: here }).items.map((shop) => shop.name)).toEqual([
      "Abe",
      "Zed",
    ]);
  });

  it("without location, lists the farmer's district by name", () => {
    const sorted = sortAgrovets(shops, { location: null, district: "A" });
    expect(sorted.mode).toBe("district");
    expect(sorted.district).toBe("A");
    expect(sorted.items.map((shop) => shop.id)).toEqual(["unknown", "far", "mid"]);
    expect(sorted.items.every((shop) => shop.km === undefined)).toBe(true);
  });

  it("without location or a known district, lists everyone by name", () => {
    const sorted = sortAgrovets(shops, { location: null, district: null });
    expect(sorted.mode).toBe("all");
    expect(sorted.items.map((shop) => shop.name)).toEqual(["Aardvark", "Far", "Mid", "Near"]);
  });

  it("falls back to everyone when no agrovet is in the district", () => {
    expect(sortAgrovets(shops, { district: "Nowhere" }).mode).toBe("all");
  });

  it("measures distance sensibly", () => {
    expect(distanceKm(here, here)).toBe(0);
    expect(distanceKm(here, { lat: -15.5, lng: 28.3 })).toBeCloseTo(11.1, 1);
  });

  it("builds WhatsApp links from E.164 numbers", () => {
    expect(whatsappUrl("+260000000001")).toBe("https://wa.me/260000000001");
    expect(whatsappUrl(null)).toBeNull();
  });
});

describe("agrovet directory cache", () => {
  beforeEach(() => store.clear());

  it("stores the list with its ETag and revalidates with If-None-Match", async () => {
    const seen = [];
    const fetchImpl = async (path, init) => {
      seen.push(init.headers);
      if (init.headers["If-None-Match"] === '"v1"') return { status: 304, ok: false };
      return {
        status: 200,
        ok: true,
        headers: { get: () => '"v1"' },
        json: async () => shops,
      };
    };

    expect(await refreshDirectory({ fetchImpl, now: () => 1 })).toBe("updated");
    expect(cachedDirectory()).toMatchObject({ etag: '"v1"', fetchedAt: 1 });
    expect(cachedDirectory().items).toHaveLength(4);

    expect(await refreshDirectory({ fetchImpl, now: () => 2 })).toBe("unchanged");
    expect(seen[1]).toEqual({ "If-None-Match": '"v1"' });
    expect(cachedDirectory()).toMatchObject({ fetchedAt: 2 });
    expect(cachedDirectory().items).toHaveLength(4);
  });

  it("keeps the cached list when offline", async () => {
    await refreshDirectory({
      fetchImpl: async () => ({
        status: 200,
        ok: true,
        headers: { get: () => null },
        json: async () => shops,
      }),
    });
    const result = await refreshDirectory({
      fetchImpl: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    expect(result).toBe("offline");
    expect(cachedDirectory().items).toHaveLength(4);
  });
});
