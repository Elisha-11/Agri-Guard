/**
 * Screen 2 — Processing (Figma node 43:3).
 *
 * Runs the photo quality check, then inference, then routes to whichever
 * result screen the outcome calls for:
 *
 *   quality check fails -> 3d. Result Rejected
 *   status "confident"  -> 3.  Result
 *   status "uncertain"  -> 3b. Result Uncertain
 *   status "consult"    -> 3c. Result Consult
 *
 * The status thresholds live in lib/prediction.js, per docs/model-output.md.
 */

import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc } from "../ui.js";
import { replace } from "../router.js";
import { session, addHistoryEntry } from "../state.js";
import { diagnose } from "../inference/diagnose.js";
import { checkImageQuality, makeThumbnail } from "../image-quality.js";
import { displayName } from "../disease.js";

/** Minimum time on screen, so the step reads as progress rather than a flash. */
const MIN_VISIBLE_MS = 900;

export function render() {
  return `
    <section class="ag-screen ag-processing">
      <div class="ag-processing__inner">
        <img src="${icons.leaf}" alt="" width="104" height="104" />

        <div class="ag-processing__status">
          <p class="ag-processing__text" role="status">${esc(t("processing.status"))}</p>
          <div
            class="ag-processing__track"
            role="progressbar"
            aria-label="${esc(t("processing.status"))}"
          >
            <div class="ag-processing__bar"></div>
          </div>
        </div>
      </div>
    </section>
  `;
}

export function mount() {
  let cancelled = false;

  async function run() {
    if (!session.imageBlob) {
      replace("/capture");
      return;
    }

    const startedAt = Date.now();

    try {
      const quality = await checkImageQuality(session.imageBlob);

      if (!quality.ok) {
        session.rejectReasons = quality.reasons;
        await settle(startedAt);
        if (!cancelled) replace("/rejected");
        return;
      }

      const prediction = await diagnose(session.imageBlob);
      session.prediction = prediction;

      // Only a usable reading is worth keeping; "consult" means the model
      // could not identify anything, so there is nothing to file.
      if (prediction.status !== "consult") {
        const thumb = await makeThumbnail(session.imageBlob);
        addHistoryEntry({
          classId: prediction.class_id,
          name: displayName(prediction.class_id),
          confidence: prediction.confidence,
          severity: prediction.severity,
          status: prediction.status,
          modelVersion: prediction.model_version,
          thumb,
        });
      }

      await settle(startedAt);
      if (cancelled) return;

      if (prediction.status === "confident") replace("/result");
      else if (prediction.status === "uncertain") replace("/uncertain");
      else replace("/consult");
    } catch (error) {
      // An unreadable file or a failed model load both leave the farmer with
      // no diagnosis, which is exactly what the consult screen is for.
      console.error("Diagnosis failed:", error);
      session.prediction = null;
      await settle(startedAt);
      if (!cancelled) replace("/consult");
    }
  }

  function settle(startedAt) {
    const remaining = MIN_VISIBLE_MS - (Date.now() - startedAt);
    return remaining > 0
      ? new Promise((resolve) => setTimeout(resolve, remaining))
      : Promise.resolve();
  }

  run();

  return () => {
    cancelled = true;
  };
}
