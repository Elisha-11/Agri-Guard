import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { Buffer } from "node:buffer";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import * as tf from "@tensorflow/tfjs-core";
import "@tensorflow/tfjs-backend-cpu";
import { loadGraphModel } from "@tensorflow/tfjs-converter";
import { diagnose, INFERENCE_MODE } from "../src/inference/diagnose.js";
import { buildPrediction } from "../src/lib/prediction.js";

describe("diagnose()", () => {
  it("runs the real model, not the old mock", () => {
    expect(INFERENCE_MODE).toBe("model");
  });

  it("rejects a missing image before loading anything", async () => {
    await expect(diagnose(null)).rejects.toThrow("An image is required for diagnosis.");
  });
});

/*
 * The published model itself, run on the CPU backend. Needs the files that
 * `npm run model:fetch` downloads into public/models/ (git-ignored), so it
 * skips on a fresh clone and in CI.
 */
const modelsDir = fileURLToPath(new URL("../public/models", import.meta.url));
const current = path.join(modelsDir, "current.json");
const fetched = existsSync(current);

describe.skipIf(!fetched)("bundled model (run `npm run model:fetch` first)", () => {
  const load = async () => {
    const { model_version: version } = JSON.parse(readFileSync(current, "utf8"));
    const dir = path.join(modelsDir, version);
    const read = (file) => JSON.parse(readFileSync(path.join(dir, file), "utf8"));
    const modelJson = read("model.json");
    const shards = modelJson.weightsManifest
      .flatMap((group) => group.paths)
      .map((file) => readFileSync(path.join(dir, file)));
    const weightData = new Uint8Array(Buffer.concat(shards)).buffer;

    await tf.setBackend("cpu");
    const model = await loadGraphModel({
      load: async () => ({
        modelTopology: modelJson.modelTopology,
        weightSpecs: modelJson.weightsManifest.flatMap((group) => group.weights),
        weightData,
        format: modelJson.format,
        generatedBy: modelJson.generatedBy,
        convertedBy: modelJson.convertedBy,
        signature: modelJson.signature,
      }),
    });
    return { model, labels: read("labels.json"), manifest: read("manifest.json") };
  };

  const run = (model, input) => {
    const output = model.predict(input);
    const values = Array.from(output.dataSync());
    output.dispose();
    input.dispose();
    return values;
  };

  it("returns one softmax probability per labels.json class", async () => {
    const { model, labels, manifest } = await load();
    const { width, height } = labels.input;

    // a flat mid-green "leaf", in the 0-255 range the contract specifies
    const probabilities = run(
      model,
      tf.add(tf.zeros([1, height, width, 3]), tf.tensor1d([60, 140, 50])),
    );

    expect(probabilities).toHaveLength(labels.classes.length);
    expect(probabilities.every((p) => p >= 0 && p <= 1)).toBe(true);
    expect(probabilities.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 3);

    const prediction = buildPrediction(probabilities, labels, { thresholds: manifest.thresholds });
    expect(prediction.model_version).toBe(labels.model_version);
    expect(prediction.top_k).toHaveLength(3);
  }, 60_000);

  it("gives different answers for different pictures (it looks at the pixels)", async () => {
    const { model, labels } = await load();
    const { width, height } = labels.input;

    const green = run(model, tf.add(tf.zeros([1, height, width, 3]), tf.tensor1d([60, 140, 50])));
    const brown = run(model, tf.add(tf.zeros([1, height, width, 3]), tf.tensor1d([140, 90, 40])));

    const difference = green.reduce((sum, p, i) => sum + Math.abs(p - brown[i]), 0);
    expect(difference).toBeGreaterThan(0.01);
  }, 60_000);
});
