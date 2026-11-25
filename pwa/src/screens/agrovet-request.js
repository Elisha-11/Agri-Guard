/**
 * Screen 11 — Ask agrovet (Figma node 108:46).
 *
 * The request form. Crop and diagnosis come from the check the farmer pressed
 * "Find agrovet" on, the district only when the app knows it. The farmer adds
 * their own description and chooses what to share: photo, diagnosis and
 * district start on, the phone number starts off. Anything switched off is
 * left out of the request (src/agrovet-requests.js, buildRequestPayload).
 *
 * Sending saves the request first; with no signal it waits in the outbox and
 * goes out by itself later.
 */

import { t } from "../i18n.js";
import { esc, bindBack } from "../ui.js";
import { back, replace } from "../router.js";
import { session } from "../state.js";
import { makeThumbnail } from "../image-quality.js";
import { findAgrovet, knownDistrict } from "../agrovets.js";
import { agrovetRequests, cropOf, requestContext } from "../agrovet-requests.js";
import { mockBanner, avBack, diagnosisLabel, isOnline } from "./agrovet-ui.js";

function hasPhoto(context) {
  return Boolean(context?.thumb || (context?.useSessionPhoto && session.imageBlob));
}

function toggle(key, label, { on, hint = "" }) {
  return `
    <label class="ag-av-toggle">
      <span class="ag-av-toggle__row">
        <span class="ag-av-toggle__label">${esc(label)}</span>
        <input type="checkbox" role="switch" class="ag-av-toggle__input" data-share="${key}"
          ${on ? "checked" : ""} />
        <span class="ag-av-toggle__switch" aria-hidden="true"></span>
      </span>
      ${hint ? `<span class="ag-av-toggle__hint">${esc(hint)}</span>` : ""}
    </label>
  `;
}

/**
 * @param {{agrovetId?: string}} [params]
 * @param {{agrovet?: object|null, context?: object|null, district?: string|null, online?: boolean}} [view] for tests
 */
export function render(params = {}, view = {}) {
  const agrovet = view.agrovet !== undefined ? view.agrovet : findAgrovet(params.agrovetId);
  if (!agrovet) return "";

  const context = view.context !== undefined ? view.context : requestContext();
  const district = view.district !== undefined ? view.district : knownDistrict();
  const online = view.online ?? isOnline();
  const diagnosis = diagnosisLabel(context?.classId, context?.predictionStatus);
  const crop = cropOf(context?.classId);

  return `
    <section class="ag-screen ag-av ag-av--split">
      <div class="ag-av__form">
        ${mockBanner()}
        <div class="ag-av__nav">${avBack()}</div>

        <h1 class="ag-av__title ag-av__title--form">${esc(
          t("request.title", { name: agrovet.name }),
        )}</h1>

        <div class="ag-av-box ag-av-readonly">
          <p><span>${esc(t("request.crop"))}</span><strong>${esc(
            crop.charAt(0).toUpperCase() + crop.slice(1),
          )}</strong></p>
          ${
            diagnosis
              ? `<p><span>${esc(t("request.diagnosis"))}</span><strong>${esc(
                  diagnosis,
                )}</strong></p>`
              : ""
          }
          ${
            district
              ? `<p><span>${esc(t("request.district"))}</span><strong>${esc(district)}</strong></p>`
              : ""
          }
        </div>

        <label class="ag-av-field">
          <span class="ag-av-field__label">${esc(t("request.describe"))}</span>
          <textarea id="ag-av-description" class="ag-av-field__input" rows="4" maxlength="1000"
            placeholder="${esc(t("request.describePlaceholder"))}"></textarea>
        </label>

        <div class="ag-av-share">
          <h2 class="ag-av__subtitle">${esc(t("request.shareTitle"))}</h2>
          <div class="ag-av-box ag-av-share__options">
            ${hasPhoto(context) ? toggle("photo", t("request.sharePhoto"), { on: true }) : ""}
            ${diagnosis ? toggle("diagnosis", t("request.shareDiagnosis"), { on: true }) : ""}
            ${district ? toggle("district", t("request.shareDistrict"), { on: true }) : ""}
            ${toggle("phone", t("request.sharePhone"), { on: false, hint: t("request.phoneHint") })}
          </div>
        </div>
      </div>

      <div class="ag-av__bottom">
        <p class="ag-av__status" id="ag-av-status" role="status">${
          online ? "" : esc(t("request.offlineHint"))
        }</p>
        <button type="button" class="ag-av-btn" id="ag-av-send">${esc(t("request.send"))}</button>
      </div>
    </section>
  `;
}

export function mount(root, params = {}) {
  const agrovet = findAgrovet(params.agrovetId);
  if (!agrovet) {
    replace("/agrovets");
    return null;
  }

  bindBack(root, () => back("/agrovets"));

  const context = requestContext();
  const send = root.querySelector("#ag-av-send");
  const status = root.querySelector("#ag-av-status");

  const shared = (key) => {
    const input = root.querySelector(`[data-share="${key}"]`);
    return input ? input.checked : false;
  };

  const onlineChange = () => {
    if (!send.disabled) status.textContent = isOnline() ? "" : t("request.offlineHint");
  };
  window.addEventListener("online", onlineChange);
  window.addEventListener("offline", onlineChange);

  send.addEventListener("click", async () => {
    send.disabled = true;
    const share = {
      photo: shared("photo"),
      diagnosis: shared("diagnosis"),
      district: shared("district"),
      phone: shared("phone"),
    };

    let thumb = null;
    if (share.photo) {
      try {
        thumb =
          context?.thumb ??
          (context?.useSessionPhoto && session.imageBlob
            ? await makeThumbnail(session.imageBlob)
            : null);
      } catch {
        thumb = null; // a photo the browser cannot decode is simply not attached
      }
    }

    const saved = await agrovetRequests.send({
      agrovet,
      classId: context?.classId ?? null,
      predictionStatus: context?.predictionStatus ?? null,
      district: knownDistrict(),
      description: root.querySelector("#ag-av-description").value,
      share,
      thumb,
    });

    // The detail screen says "Saved. It will send when you have signal." when it is still queued.
    replace("/request", { clientId: saved.client_id });
  });

  return () => {
    window.removeEventListener("online", onlineChange);
    window.removeEventListener("offline", onlineChange);
  };
}
