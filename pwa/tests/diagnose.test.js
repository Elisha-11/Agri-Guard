import { describe, expect, it } from "vitest";
import { diagnose, INFERENCE_MODE } from "../src/inference/diagnose.js";

describe("AgriGuard inference stub", () => {
  it("identifies itself as mock inference", () => {
    expect(INFERENCE_MODE).toBe("mock");
  });

  it("rejects a missing image", async () => {
    await expect(diagnose(null)).rejects.toThrow(
      "An image is required for diagnosis.",
    );
  });

  it("returns a prediction in the expected format", async () => {
    const image = new Blob(["test image"]);
    const result = await diagnose(image);

    expect(result).toHaveProperty("class_id");
    expect(result).toHaveProperty("confidence");
    expect(result).toHaveProperty("status");
    expect(result).toHaveProperty("severity");
    expect(result).toHaveProperty("top_k");
    expect(result).toHaveProperty("model_version");
  });

  it("returns the expected demonstration prediction", async () => {
    const image = new Blob(["test image"]);
    const result = await diagnose(image);

    expect(result.class_id).toBe("maize__grey_leaf_spot");
    expect(result.status).toBe("confident");
  });
});