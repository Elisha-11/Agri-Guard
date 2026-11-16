/**
 * Over-the-air model updates (docs/backend/model-releases.md, "For the PWA"):
 *
 *  1. Ask GET /api/v1/model/latest/ when online. 404 `no_model`: keep what we have.
 *  2. If `min_app_version` is newer than this app, do not download; the farmer
 *     needs to update the app first.
 *  3. If `model_version` differs from the model in use, download model.json, its
 *     shards and labels.json from the release folder, check model.json's SHA-256
 *     and the total size against the manifest, and only then switch to it. The
 *     model in use stays until the new one is fully verified.
 *  4. Keep the manifest with the model, for its thresholds.
 *
 * Verified files go into Cache Storage under their release URLs; the active
 * release is remembered in localStorage. Dependencies are passed in so the
 * logic is tested without a network or a browser.
 */

const ACTIVE_KEY = "agriguard.model.active";
const STATUS_KEY = "agriguard.model.updateStatus";
export const CACHE_PREFIX = "agriguard-model-";

/** -1, 0 or 1, comparing dotted versions numerically ("0.10.0" > "0.9.1"). */
export function compareVersions(a, b) {
  const pa = String(a).split(".").map(Number);
  const pb = String(b).split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
    const diff = (pa[i] || 0) - (pb[i] || 0);
    if (diff) return Math.sign(diff);
  }
  return 0;
}

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** The release folder a manifest's model_url lives in, with a trailing slash. */
export function releaseBase(manifest) {
  return manifest.model_url.slice(0, manifest.model_url.lastIndexOf("/") + 1);
}

/**
 * Check for and install a newer model.
 *
 * @param {object} deps
 * @param {(url: string, init?: object) => Promise<Response>} deps.fetch
 * @param {string} deps.latestUrl  URL of GET /api/v1/model/latest/
 * @param {string} deps.appVersion this app's version (package.json)
 * @param {string|null} deps.currentVersion model version in use now
 * @param {{open(name:string):Promise<{put(url:string, r:Response):Promise<void>}>, keys():Promise<string[]>, delete(name:string):Promise<boolean>}} deps.caches
 * @param {{getItem(k:string):string|null, setItem(k:string, v:string):void}} deps.storage
 * @returns {Promise<{result: string, version?: string}>}
 *   result: "installed" | "up-to-date" | "no-model" | "app-too-old" | "offline" | "rejected"
 */
export async function checkForModelUpdate(deps) {
  const { fetch, latestUrl, appVersion, currentVersion, caches, storage } = deps;
  const remember = (status) => {
    storage.setItem(STATUS_KEY, JSON.stringify({ ...status, checkedAt: Date.now() }));
    return status;
  };

  let manifest;
  try {
    const response = await fetch(latestUrl, { cache: "no-store" });
    if (response.status === 404) return remember({ result: "no-model" });
    if (!response.ok) return { result: "offline" };
    manifest = await response.json();
  } catch {
    return { result: "offline" };
  }

  const version = manifest.model_version;
  if (manifest.min_app_version && compareVersions(appVersion, manifest.min_app_version) < 0) {
    return remember({ result: "app-too-old", version, needs: manifest.min_app_version });
  }
  if (version === currentVersion) return remember({ result: "up-to-date", version });

  const base = releaseBase(manifest);
  try {
    const get = async (url) => {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
      return new Uint8Array(await response.arrayBuffer());
    };

    const modelBytes = await get(manifest.model_url);
    if ((await sha256Hex(modelBytes)) !== manifest.sha256)
      throw new Error("model.json SHA-256 mismatch");

    const modelJson = JSON.parse(new TextDecoder().decode(modelBytes));
    const shardNames = modelJson.weightsManifest.flatMap((group) => group.paths);
    const shards = [];
    for (const name of shardNames) shards.push([`${base}${name}`, await get(`${base}${name}`)]);

    const labelsBytes = await get(manifest.labels_url);
    const labels = JSON.parse(new TextDecoder().decode(labelsBytes));
    if (labels.model_version !== version)
      throw new Error("labels.json is for another model version");
    if (!labels.input || !Array.isArray(labels.classes))
      throw new Error("labels.json is incomplete");

    const total = modelBytes.length + shards.reduce((sum, [, bytes]) => sum + bytes.length, 0);
    if (manifest.size_bytes && total !== manifest.size_bytes) {
      throw new Error(`downloaded ${total} bytes, manifest says ${manifest.size_bytes}`);
    }

    // Everything checks out: store it, then switch.
    const cache = await caches.open(`${CACHE_PREFIX}${version}`);
    const put = (url, bytes, type) =>
      cache.put(url, new Response(bytes, { headers: { "Content-Type": type } }));
    await put(manifest.model_url, modelBytes, "application/json");
    for (const [url, bytes] of shards) await put(url, bytes, "application/octet-stream");
    await put(manifest.labels_url, labelsBytes, "application/json");
    await put(
      `${base}manifest.json`,
      new TextEncoder().encode(JSON.stringify(manifest)),
      "application/json",
    );

    storage.setItem(ACTIVE_KEY, JSON.stringify({ version, base }));

    // Old downloaded releases are no longer needed once the new one is active.
    for (const name of await caches.keys()) {
      if (name.startsWith(CACHE_PREFIX) && name !== `${CACHE_PREFIX}${version}`)
        await caches.delete(name);
    }
    return remember({ result: "installed", version });
  } catch (error) {
    // The model in use is untouched; the next check tries again.
    return remember({ result: "rejected", version, reason: String(error.message ?? error) });
  }
}

/** The downloaded release to use instead of the bundled one, if any. */
export function activeDownloadedModel(storage) {
  try {
    return JSON.parse(storage.getItem(ACTIVE_KEY) ?? "null");
  } catch {
    return null;
  }
}

/** What the last update check found, for the Settings screen. */
export function lastUpdateStatus(storage) {
  try {
    return JSON.parse(storage.getItem(STATUS_KEY) ?? "null");
  } catch {
    return null;
  }
}
