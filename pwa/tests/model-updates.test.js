import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { Buffer } from "node:buffer";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  CACHE_PREFIX,
  activeDownloadedModel,
  checkForModelUpdate,
  compareVersions,
  releaseBase,
} from "../src/inference/model-updates.js";

describe("compareVersions", () => {
  it("compares numerically, part by part", () => {
    expect(compareVersions("0.1.0", "0.1.0")).toBe(0);
    expect(compareVersions("0.10.0", "0.9.9")).toBe(1);
    expect(compareVersions("0.1", "0.1.1")).toBe(-1);
  });
});

/* ------------------------------------------------------------------ fakes */

const BASE = "https://models.example/models/2026.11.0/";
const LATEST = "https://api.example/api/v1/model/latest/";

function memoryStorage() {
  const map = new Map();
  return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => map.set(k, String(v)), map };
}

function memoryCaches() {
  const stores = new Map();
  return {
    stores,
    async open(name) {
      if (!stores.has(name)) stores.set(name, new Map());
      const store = stores.get(name);
      return { put: async (url, response) => store.set(url, await response.arrayBuffer()) };
    },
    keys: async () => [...stores.keys()],
    delete: async (name) => stores.delete(name),
  };
}

/** A release folder served from memory, built from the real bundled model when present. */
const modelsDir = fileURLToPath(new URL("../public/models", import.meta.url));
const hasModel = existsSync(path.join(modelsDir, "current.json"));

function release({
  version = "2026.11.0",
  tamperModel = false,
  minApp = "0.1.0",
  wrongSize = false,
} = {}) {
  const bundled = JSON.parse(
    readFileSync(path.join(modelsDir, "current.json"), "utf8"),
  ).model_version;
  const dir = path.join(modelsDir, bundled);
  const files = Object.fromEntries(
    readdirSync(dir).map((f) => [f, readFileSync(path.join(dir, f))]),
  );
  const bundledManifest = JSON.parse(files["manifest.json"]);

  const labels = { ...JSON.parse(files["labels.json"]), model_version: version };
  files["labels.json"] = Buffer.from(JSON.stringify(labels));
  if (tamperModel) files["model.json"] = Buffer.concat([files["model.json"], Buffer.from(" ")]);

  const manifest = {
    ...bundledManifest,
    model_version: version,
    model_url: `${BASE}model.json`,
    labels_url: `${BASE}labels.json`,
    min_app_version: minApp,
    size_bytes: bundledManifest.size_bytes + (wrongSize ? 1 : 0),
  };

  const requested = [];
  const fetch = async (url) => {
    requested.push(url);
    if (url === LATEST) return new Response(JSON.stringify(manifest), { status: 200 });
    const name = url.startsWith(BASE) ? url.slice(BASE.length) : null;
    if (name && files[name]) return new Response(files[name], { status: 200 });
    return new Response("not found", { status: 404 });
  };
  return { fetch, manifest, requested };
}

const run = (overrides) => {
  const storage = memoryStorage();
  const caches = memoryCaches();
  return {
    storage,
    caches,
    promise: checkForModelUpdate({
      latestUrl: LATEST,
      appVersion: "0.1.0",
      currentVersion: "2026.10.0",
      caches,
      storage,
      ...overrides,
    }),
  };
};

/* ------------------------------------------------------------------ rules */

describe("checkForModelUpdate", () => {
  it("does nothing when the server has no current model (404)", async () => {
    const { promise, caches } = run({ fetch: async () => new Response("{}", { status: 404 }) });
    expect((await promise).result).toBe("no-model");
    expect(caches.stores.size).toBe(0);
  });

  it("is quiet when offline", async () => {
    const { promise } = run({
      fetch: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    expect((await promise).result).toBe("offline");
  });

  it.skipIf(!hasModel)("does not download when the app is older than min_app_version", async () => {
    const r = release({ minApp: "0.2.0" });
    const { promise } = run({ fetch: r.fetch });
    expect(await promise).toMatchObject({ result: "app-too-old", needs: "0.2.0" });
    expect(r.requested).toEqual([LATEST]);
  });

  it.skipIf(!hasModel)("does not download the version already in use", async () => {
    const r = release({ version: "2026.10.0" });
    const { promise } = run({ fetch: r.fetch });
    expect((await promise).result).toBe("up-to-date");
    expect(r.requested).toEqual([LATEST]);
  });

  it.skipIf(!hasModel)("installs a newer, verified release and makes it active", async () => {
    const r = release();
    const { promise, storage, caches } = run({ fetch: r.fetch });
    expect(await promise).toMatchObject({ result: "installed", version: "2026.11.0" });

    expect(activeDownloadedModel(storage)).toEqual({ version: "2026.11.0", base: BASE });
    const stored = caches.stores.get(`${CACHE_PREFIX}2026.11.0`);
    expect([...stored.keys()].sort()).toEqual(
      [
        `${BASE}group1-shard1of2.bin`,
        `${BASE}group1-shard2of2.bin`,
        `${BASE}labels.json`,
        `${BASE}manifest.json`,
        `${BASE}model.json`,
      ].sort(),
    );
  });

  it.skipIf(!hasModel)(
    "rejects a model.json whose SHA-256 does not match, keeping the current model",
    async () => {
      const r = release({ tamperModel: true });
      const { promise, storage, caches } = run({ fetch: r.fetch });
      expect(await promise).toMatchObject({
        result: "rejected",
        reason: expect.stringMatching(/SHA-256/),
      });
      expect(activeDownloadedModel(storage)).toBeNull();
      expect(caches.stores.size).toBe(0);
    },
  );

  it.skipIf(!hasModel)("rejects a release whose size differs from the manifest", async () => {
    const r = release({ wrongSize: true });
    const { promise, storage } = run({ fetch: r.fetch });
    expect(await promise).toMatchObject({
      result: "rejected",
      reason: expect.stringMatching(/bytes/),
    });
    expect(activeDownloadedModel(storage)).toBeNull();
  });

  it("finds the release folder from model_url", () => {
    expect(releaseBase({ model_url: `${BASE}model.json` })).toBe(BASE);
  });
});
