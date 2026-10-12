import { describe, expect, it } from "vitest";
import { buildPrediction, statusFor } from "../src/lib/prediction.js";

const labels = {
  model_version: "test.0",
  classes: [
    { index: 0, id: "maize__healthy", is_healthy: true },
    { index: 1, id: "maize__northern_leaf_blight", is_healthy: false },
    { index: 2, id: "maize__grey_leaf_spot", is_healthy: false },
    { index: 3, id: "maize__common_rust", is_healthy: false },
  ],
};

describe("statusFor", () => {
  it("applies the contract thresholds, inclusive at the boundary", () => {
    expect(statusFor(0.7)).toBe("confident");
    expect(statusFor(0.69)).toBe("uncertain");
    expect(statusFor(0.4)).toBe("uncertain");
    expect(statusFor(0.39)).toBe("consult");
  });

  it("uses thresholds from the model manifest when given", () => {
    expect(statusFor(0.75, { confident: 0.8, uncertain: 0.5 })).toBe("uncertain");
  });
});

describe("buildPrediction", () => {
  it("returns the contract shape with top-3 sorted descending", () => {
    const p = buildPrediction([0.01, 0.06, 0.91, 0.02], labels, { inferenceMs: 1840.4 });

    expect(p).toEqual({
      class_id: "maize__grey_leaf_spot",
      class_index: 2,
      confidence: 0.91,
      status: "confident",
      severity: "unknown",
      top_k: [
        { class_id: "maize__grey_leaf_spot", confidence: 0.91 },
        { class_id: "maize__northern_leaf_blight", confidence: 0.06 },
        { class_id: "maize__common_rust", confidence: 0.02 },
      ],
      model_version: "test.0",
      inference_ms: 1840,
    });
  });

  it("marks healthy leaves with severity none", () => {
    expect(buildPrediction([0.97, 0.01, 0.01, 0.01], labels).severity).toBe("none");
  });

  it("refuses a model/labels mismatch instead of guessing", () => {
    expect(() => buildPrediction([0.5, 0.5], labels)).toThrow(/labels.json/);
  });
});
