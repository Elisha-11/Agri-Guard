/**
 * AgriGuard AI — temporary inference stub.
 *
 * This module gives the PWA team a stable diagnose(image) interface while
 * Agness develops the real model pipeline. It DOES NOT inspect image pixels
 * and MUST NOT be presented to farmers as a real diagnosis.
 *
 * Contract reference: docs/model-output.md. The real implementation will
 * replace only the mock-score section with TensorFlow.js inference.
 */

import labels from "../../../ml/labels.json";
import { buildPrediction } from "../lib/prediction.js";

/** Lets the PWA identify that this module is still returning mock results. */
export const INFERENCE_MODE = "mock";

/**
 * Return a deterministic, contract-shaped mock prediction.
 *
 * @param {File|Blob|HTMLImageElement|ImageBitmap} image selected/captured image
 * @returns {Promise<object>} Prediction matching docs/model-output.md
 */
export async function diagnose(image) {
  if (!image) {
    throw new Error("An image is required for diagnosis.");
  }

  if (!Array.isArray(labels.classes) || labels.classes.length < 3) {
    throw new Error("ml/labels.json must contain at least three classes.");
  }

  // DEMO ONLY: fixed example matching the model-output illustration.
  // Index 2 is maize__grey_leaf_spot in the current provisional labels.json.
  // No image analysis, TensorFlow model, or disease detection happens here.
  const remainingClasses = labels.classes.length - 3;
  const remainingScore = remainingClasses > 0 ? 0.01 / remainingClasses : 0;
  const probabilities = new Array(labels.classes.length).fill(remainingScore);

  probabilities[2] = 0.91;
  probabilities[1] = 0.06;
  probabilities[3] = 0.02;

  return buildPrediction(probabilities, labels, { inferenceMs: 0 });
}
