#!/usr/bin/env node
/**
 * Download a published model release into public/models/<version>/ so it ships
 * inside the build (and the Android APK) and diagnosis works offline from the
 * first launch.
 *
 *   node scripts/fetch-model.mjs            # default release below
 *   node scripts/fetch-model.mjs 2026.11.0  # a specific release
 *
 * Checks what docs/backend/model-releases.md "For the PWA" asks for: the
 * SHA-256 of model.json against manifest.json, every shard present, and the
 * total size. The files stay out of git (pwa/.gitignore); releases live at
 * https://elisha-11.github.io/agri-guard-models/ (ADR 0016).
 */

import { createHash } from "node:crypto";
import { mkdir, writeFile, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const DEFAULT_VERSION = "2026.10.0";
const BASE = "https://elisha-11.github.io/agri-guard-models/models/";

const version = process.argv[2] ?? DEFAULT_VERSION;
if (!/^\d{4}\.\d+\.\d+$/.test(version)) {
  console.error(`Not a model version: ${version}`);
  process.exit(1);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const modelsDir = path.join(here, "..", "public", "models");
const outDir = path.join(modelsDir, version);
const url = (file) => `${BASE}${version}/${file}`;

async function get(file) {
  const response = await fetch(url(file));
  if (!response.ok) throw new Error(`${url(file)}: HTTP ${response.status}`);
  return Buffer.from(await response.arrayBuffer());
}

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

const manifestBytes = await get("manifest.json");
const manifest = JSON.parse(manifestBytes);
const labelsBytes = await get("labels.json");
const labels = JSON.parse(labelsBytes);
const modelBytes = await get("model.json");

if (manifest.model_version !== version || labels.model_version !== version) {
  throw new Error(`manifest/labels are for ${manifest.model_version}/${labels.model_version}, not ${version}`);
}
if (sha256(modelBytes) !== manifest.sha256) {
  throw new Error("model.json SHA-256 does not match manifest.json; refusing to use it");
}

const shardNames = JSON.parse(modelBytes).weightsManifest.flatMap((group) => group.paths);
const shards = [];
for (const name of shardNames) shards.push([name, await get(name)]);

const total = modelBytes.length + shards.reduce((sum, [, bytes]) => sum + bytes.length, 0);
if (manifest.size_bytes && total !== manifest.size_bytes) {
  throw new Error(`downloaded ${total} bytes, manifest says ${manifest.size_bytes}`);
}

await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });
await writeFile(path.join(outDir, "manifest.json"), manifestBytes);
await writeFile(path.join(outDir, "labels.json"), labelsBytes);
await writeFile(path.join(outDir, "model.json"), modelBytes);
for (const [name, bytes] of shards) await writeFile(path.join(outDir, name), bytes);
await writeFile(path.join(modelsDir, "current.json"), JSON.stringify({ model_version: version }) + "\n");

console.log(
  `Model ${version}: ${shards.length} shards, ${(total / 1e6).toFixed(1)} MB, SHA-256 verified -> public/models/${version}/`,
);
