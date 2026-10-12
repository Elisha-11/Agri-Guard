/**
 * Turns raw model output into the Prediction object defined in docs/model-output.md.
 * Pure function with no TensorFlow.js dependency, so it is tested without a model.
 */

export const DEFAULT_THRESHOLDS = Object.freeze({ confident: 0.7, uncertain: 0.4 });

/** Map top-1 confidence to the contract status. Thresholds come from the model manifest. */
export function statusFor(confidence, thresholds = DEFAULT_THRESHOLDS) {
  if (confidence >= thresholds.confident) return "confident";
  if (confidence >= thresholds.uncertain) return "uncertain";
  return "consult";
}

const round2 = (n) => Math.round(n * 100) / 100;

/**
 * @param {ArrayLike<number>} probabilities softmax output, length N
 * @param {{model_version: string, classes: {index:number,id:string,is_healthy:boolean}[]}} labels labels.json
 * @param {{thresholds?: {confident:number, uncertain:number}, inferenceMs?: number}} [options]
 */
export function buildPrediction(probabilities, labels, options = {}) {
  const { thresholds = DEFAULT_THRESHOLDS, inferenceMs } = options;
  if (probabilities.length !== labels.classes.length) {
    throw new Error(
      `Model returned ${probabilities.length} scores but labels.json lists ${labels.classes.length} classes`,
    );
  }

  const ranked = Array.from(probabilities, (p, index) => ({ index, p })).sort((a, b) => b.p - a.p);
  const top = labels.classes[ranked[0].index];
  const confidence = round2(ranked[0].p);

  const prediction = {
    class_id: top.id,
    class_index: top.index,
    confidence,
    status: statusFor(ranked[0].p, thresholds),
    // severity source is an open decision (model-output.md §5); healthy is always "none"
    severity: top.is_healthy ? "none" : "unknown",
    top_k: ranked.slice(0, 3).map(({ index, p }) => ({
      class_id: labels.classes[index].id,
      confidence: round2(p),
    })),
    model_version: labels.model_version,
  };
  if (Number.isFinite(inferenceMs)) prediction.inference_ms = Math.round(inferenceMs);
  return prediction;
}
