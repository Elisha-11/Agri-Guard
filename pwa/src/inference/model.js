/**
 * Loads the disease model once and keeps it in memory.
 *
 * Where the model comes from, in order:
 *  1. a newer release downloaded and verified by model-updates.js (Cache Storage);
 *  2. public/models/<version>/ bundled into the build by scripts/fetch-model.mjs,
 *     so the Android app diagnoses offline from its very first launch;
 *  3. otherwise the published release on GitHub Pages (ADR 0016).
 *
 * The manifest's thresholds and the release's labels.json travel with the
 * model, as docs/backend/model-releases.md "For the PWA" requires; nothing
 * here hard-codes them.
 */

import * as tf from "@tensorflow/tfjs-core";
import "@tensorflow/tfjs-backend-webgl";
import "@tensorflow/tfjs-backend-cpu";
import { loadGraphModel } from "@tensorflow/tfjs-converter";
import { apiUrl } from "../native.js";
import { version as APP_VERSION } from "../../package.json";
import {
  CACHE_PREFIX,
  activeDownloadedModel,
  checkForModelUpdate,
  lastUpdateStatus,
} from "./model-updates.js";

export const FALLBACK_VERSION = "2026.10.0";
const PUBLISHED_BASE = "https://elisha-11.github.io/agri-guard-models/models/";

let loading = null;
let loadedVersion = null;

// A wrapper, not `fetch` itself: TensorFlow.js calls fetchFunc as a method,
// and a bare `fetch` with the wrong `this` throws "Illegal invocation".
const plainFetch = (url, init) => fetch(url, init);

/** The loaded model, its labels.json and manifest.json. Safe to call repeatedly. */
export function loadModel() {
  if (!loading) {
    loading = load().catch((error) => {
      loading = null; // let the next photo try again
      throw error;
    });
  }
  return loading;
}

async function load() {
  await chooseBackend();

  const { base, fetchFunc } = (await downloadedSource()) ??
    (await bundledSource()) ?? {
      base: `${PUBLISHED_BASE}${FALLBACK_VERSION}/`,
      fetchFunc: plainFetch,
    };
  const getJson = async (url) => {
    const response = await fetchFunc(url);
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
  };
  const [manifest, labels] = await Promise.all([
    getJson(`${base}manifest.json`),
    getJson(`${base}labels.json`),
  ]);
  const model = await loadGraphModel(`${base}model.json`, { fetchFunc });
  loadedVersion = labels.model_version;

  // The first run compiles the GPU shaders, which takes seconds on a budget
  // phone. Do it now, while the farmer is still framing the leaf.
  const { width, height, channels } = labels.input;
  const warm = model.predict(tf.zeros([1, height, width, channels]));
  await warm.data();
  warm.dispose();

  return { model, labels, manifest, backend: tf.getBackend(), source: base };
}

/** GPU (WebGL) when the phone has it, CPU otherwise. */
async function chooseBackend() {
  for (const name of ["webgl", "cpu"]) {
    try {
      if (await tf.setBackend(name)) {
        await tf.ready();
        return;
      }
    } catch {
      // try the next one
    }
  }
  throw new Error("No TensorFlow.js backend is available on this device");
}

/** A release installed by model-updates.js, served from Cache Storage. */
async function downloadedSource() {
  const active = activeDownloadedModel(localStorage);
  if (!active || typeof caches === "undefined") return null;
  try {
    const cache = await caches.open(`${CACHE_PREFIX}${active.version}`);
    if (!(await cache.match(`${active.base}model.json`))) return null;
    const fetchFunc = async (url) => {
      const hit = await cache.match(String(url));
      if (!hit) throw new Error(`${url} is missing from the downloaded model`);
      return hit;
    };
    return { base: active.base, fetchFunc };
  } catch {
    return null;
  }
}

async function bundledSource() {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}models/current.json`);
    if (!response.ok) return null;
    const { model_version: version } = await response.json();
    return version
      ? { base: `${import.meta.env.BASE_URL}models/${version}/`, fetchFunc: plainFetch }
      : null;
  } catch {
    return null;
  }
}

/** Version of the model in use (or about to be), for update checks and Settings. */
export async function currentModelVersion() {
  if (loadedVersion) return loadedVersion;
  const active = activeDownloadedModel(localStorage);
  if (active) return active.version;
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}models/current.json`);
    if (response.ok) return (await response.json()).model_version;
  } catch {
    // fall through
  }
  return FALLBACK_VERSION;
}

/** Check for a newer release; once installed, the next photo uses it. */
export async function updateModel() {
  if (typeof caches === "undefined") return { result: "unsupported" };
  const status = await checkForModelUpdate({
    fetch: (url, init) => fetch(url, init),
    latestUrl: apiUrl("/api/v1/model/latest/"),
    appVersion: APP_VERSION,
    currentVersion: await currentModelVersion(),
    caches,
    storage: localStorage,
  });
  if (status.result === "installed") {
    loading = null; // load the new release on the next diagnosis
    loadedVersion = null;
  }
  return status;
}

/** Check at startup and whenever the phone gets signal back. */
export function startModelUpdates() {
  let running = false;
  const run = async () => {
    if (running || !navigator.onLine) return;
    running = true;
    try {
      await updateModel();
    } finally {
      running = false;
    }
  };
  run();
  window.addEventListener("online", run);
}

export function modelUpdateStatus() {
  return lastUpdateStatus(localStorage);
}
