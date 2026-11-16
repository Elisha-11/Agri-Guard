/**
 * AgriGuard AI: on-device diagnosis with the published TensorFlow.js model.
 *
 * Contract: docs/model-output.md. The model takes raw RGB pixels as float32 in
 * [0, 255], shape [1, 224, 224, 3] (EfficientNet preprocessing is inside the
 * graph), and returns softmax probabilities in labels.json order.
 *
 * The photo is resized to the model's input by stretching the whole frame,
 * without cropping, which is how ml/scripts/train_baseline.py prepares its
 * validation and test photos.
 */

import * as tf from "@tensorflow/tfjs-core";
import { buildPrediction } from "../lib/prediction.js";
import { loadModel } from "./model.js";

/** "model" now that real inference runs; the screens no longer say "simulated". */
export const INFERENCE_MODE = "model";

/**
 * @param {File|Blob} image captured or uploaded photo
 * @returns {Promise<object>} Prediction matching docs/model-output.md section 3
 */
export async function diagnose(image) {
  if (!image) {
    throw new Error("An image is required for diagnosis.");
  }

  const startedAt = performance.now();
  const { model, labels, manifest } = await loadModel();
  const { width, height } = labels.input;

  // Decode straight to the model size: a 12-megapixel camera photo never has
  // to sit in memory at full resolution on a 1-2 GB phone.
  const bitmap = await createImageBitmap(image, {
    resizeWidth: width,
    resizeHeight: height,
    resizeQuality: "high",
  });

  let output;
  try {
    output = tf.tidy(() => {
      const pixels = tf.cast(tf.browser.fromPixels(bitmap, 3), "float32");
      // Function form: tfjs-core ships without the chained `.expandDims()` methods.
      return model.predict(tf.expandDims(pixels, 0));
    });
  } finally {
    bitmap.close?.();
  }

  const probabilities = await output.data();
  output.dispose();

  return buildPrediction(probabilities, labels, {
    thresholds: manifest.thresholds,
    inferenceMs: performance.now() - startedAt,
  });
}
