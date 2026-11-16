/**
 * Client-side photo quality check.
 *
 * Screen "3d. Result Rejected" lists three reasons a photo cannot be read —
 * too blurry, too dark, too small — so the app needs to decide when to show
 * it. This runs before inference and costs a single downscaled canvas pass.
 *
 * THRESHOLDS ARE PROVISIONAL. docs/photography-protocol.md section 2 says
 * minimum dimensions and automated quality thresholds "must be confirmed
 * against the actual validation script", which does not exist yet. They are
 * gathered here so they can be tuned in one place once the pilot settles
 * them, and are deliberately lenient: wrongly rejecting a usable field photo
 * is worse for a farmer than passing a marginal one to the model.
 */

export const THRESHOLDS = Object.freeze({
  /** Shortest side, in pixels. The model takes 224x224 (ml/labels.json). */
  minShortSide: 224,
  /** Mean luminance, 0-255. Below this the photo reads as unusably dark. */
  minMeanLuminance: 38,
  /** Variance of the Laplacian on the grey channel. Lower means softer. */
  minFocusVariance: 45,
});

/** Longest side the image is scaled to before measuring. Keeps the pass cheap. */
const SAMPLE_SIZE = 256;

async function toBitmap(blob) {
  if (typeof createImageBitmap === "function") return createImageBitmap(blob);

  // Safari fallback.
  const url = URL.createObjectURL(blob);
  try {
    return await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("The photo could not be read."));
      img.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Mean luminance and focus variance of a greyscale sample. */
function measure(data, width, height) {
  const grey = new Float32Array(width * height);
  let sum = 0;

  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    // Rec. 601 luma.
    const value = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    grey[p] = value;
    sum += value;
  }

  const mean = sum / grey.length;

  // Variance of the 4-neighbour Laplacian — the standard cheap focus measure.
  let lapSum = 0;
  let lapSumSq = 0;
  let count = 0;

  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x;
      const lap = 4 * grey[i] - grey[i - 1] - grey[i + 1] - grey[i - width] - grey[i + width];
      lapSum += lap;
      lapSumSq += lap * lap;
      count += 1;
    }
  }

  if (count === 0) return { mean, focusVariance: Number.POSITIVE_INFINITY };

  const lapMean = lapSum / count;
  return { mean, focusVariance: lapSumSq / count - lapMean * lapMean };
}

/**
 * Inspect a captured photo.
 *
 * @param {Blob} blob the captured or chosen image
 * @returns {Promise<{ok: boolean, reasons: string[], metrics: object}>}
 *   `reasons` holds any of "blurry", "dark", "small".
 */
export async function checkImageQuality(blob) {
  const bitmap = await toBitmap(blob);
  const width = bitmap.width || bitmap.naturalWidth;
  const height = bitmap.height || bitmap.naturalHeight;

  const reasons = [];
  if (Math.min(width, height) < THRESHOLDS.minShortSide) reasons.push("small");

  const scale = Math.min(1, SAMPLE_SIZE / Math.max(width, height));
  const sw = Math.max(3, Math.round(width * scale));
  const sh = Math.max(3, Math.round(height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = sw;
  canvas.height = sh;

  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(bitmap, 0, 0, sw, sh);
  if (typeof bitmap.close === "function") bitmap.close();

  const { mean, focusVariance } = measure(context.getImageData(0, 0, sw, sh).data, sw, sh);

  if (mean < THRESHOLDS.minMeanLuminance) reasons.push("dark");
  if (focusVariance < THRESHOLDS.minFocusVariance) reasons.push("blurry");

  return {
    ok: reasons.length === 0,
    reasons,
    metrics: { width, height, meanLuminance: mean, focusVariance },
  };
}

/**
 * Shrink a photo to a square thumbnail data URL for the history list.
 * Keeps localStorage small — full photos are never persisted.
 */
export async function makeThumbnail(blob, size = 112) {
  const bitmap = await toBitmap(blob);
  const width = bitmap.width || bitmap.naturalWidth;
  const height = bitmap.height || bitmap.naturalHeight;
  const side = Math.min(width, height);

  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;

  canvas
    .getContext("2d")
    .drawImage(bitmap, (width - side) / 2, (height - side) / 2, side, side, 0, 0, size, size);

  if (typeof bitmap.close === "function") bitmap.close();
  return canvas.toDataURL("image/jpeg", 0.7);
}
