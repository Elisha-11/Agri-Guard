/**
 * Screen 13 — Request detail (Figma node 108:91: replied state and inline
 * close confirmation).
 *
 * What the farmer sent, its status, and each reply: in stock or not, price,
 * a suggested product, whether the agrovet can visit the farm, and their
 * message. Replies arrive in the farmer's language when the agrovet used a
 * quick-reply template that has a translation; an English fallback is
 * labelled "Shown in English". Closing asks inline (never a browser dialog)
 * and works offline.
 *
 * Below the replies sits the message thread (./message-thread.js). Messages
 * are fetched when this screen opens, when the phone gets signal back and when
 * the app opens; there is no polling and no push.
 */

import { t, currentLanguage } from "../i18n.js";
import { esc, bindBack } from "../ui.js";
import { go, back, replace } from "../router.js";
import { AGROVETS_UPDATED } from "../agrovets.js";
import { agrovetRequests, cropOf, replyLanguageNote } from "../agrovet-requests.js";
import { mockBanner, avBack, statusChip, diagnosisLabel, isOnline } from "./agrovet-ui.js";
import { threadHtml, messagesHtml, bindThread } from "./message-thread.js";

function capitalised(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function priceLine(price) {
  if (price?.amount == null) return "";
  return !price.currency || price.currency === "ZMW"
    ? t("reply.price", { amount: price.amount })
    : t("reply.priceOther", { amount: price.amount, currency: price.currency });
}

export function replyCard(reply) {
  const stock =
    reply.in_stock === true
      ? `<span class="ag-av-chip ag-av-chip--lg ag-av-chip--replied">${esc(
          t("reply.inStock"),
        )}</span>`
      : reply.in_stock === false
        ? `<span class="ag-av-chip ag-av-chip--lg ag-av-chip--sent">${esc(
            t("reply.outOfStock"),
          )}</span>`
        : "";
  const lines = [
    priceLine(reply.price),
    reply.product?.name ? t("reply.product", { name: reply.product.name }) : "",
    reply.visit_farm ? t("reply.visitFarm") : "",
    reply.text ?? "",
  ].filter(Boolean);

  return `
    <article class="ag-av-box ag-av-card-block" data-reply="${esc(reply.id)}">
      <h2 class="ag-av-card-block__title">${esc(t("reply.title"))}</h2>
      ${stock ? `<div>${stock}</div>` : ""}
      ${lines.map((line) => `<p class="ag-av-card-block__line">${esc(line)}</p>`).join("")}
    </article>
  `;
}

/**
 * @param {{clientId?: string}} [params]
 * @param {{request?: object|null, lang?: string}} [view] for tests
 */
export function render(params = {}, view = {}) {
  const request = view.request !== undefined ? view.request : agrovetRequests.find(params.clientId);
  if (!request) return "";

  const lang = view.lang ?? currentLanguage();
  const replies = request.replies ?? [];
  const diagnosis = diagnosisLabel(request.class_id, request.prediction_status);
  const english = replies.some((reply) => replyLanguageNote(reply, lang));
  const closed = request.status === "closed";
  const agrovetWrote = (request.messages ?? []).some((message) => message.sender === "agrovet");

  const yours = [
    t("request.yourCrop", { crop: capitalised(request.crop || cropOf(null)) }),
    diagnosis ? t("request.yourDiagnosis", { name: diagnosis }) : "",
    request.district ? t("request.yourDistrict", { district: request.district }) : "",
    request.description ? t("request.yourDescription", { text: request.description }) : "",
  ].filter(Boolean);

  const notes = [
    request.status === "queued" ? t("request.willSend") : "",
    request.status === "failed" ? t("request.failed") : "",
    english ? t("reply.english") : "",
  ].filter(Boolean);

  return `
    <section class="ag-screen ag-av ag-av--split">
      <div class="ag-av__detail">
        ${mockBanner()}
        <div class="ag-av__nav">${avBack()}</div>
        <h1 class="ag-av__title">${esc(
          t("request.detailTitle", { name: request.agrovet_name }),
        )}</h1>
        <div>${statusChip(request.status, { large: true })}</div>

        <article class="ag-av-box ag-av-card-block">
          <h2 class="ag-av-card-block__title">${esc(t("request.yours"))}</h2>
          ${yours.map((line) => `<p class="ag-av-card-block__line">${esc(line)}</p>`).join("")}
          ${
            request.thumb
              ? `<img class="ag-av-card-block__photo" src="${esc(request.thumb)}" alt="${esc(
                  t("request.photoAlt"),
                )}" width="56" height="56" />`
              : ""
          }
        </article>

        ${
          replies.length
            ? replies.map(replyCard).join("")
            : closed || request.status === "queued" || request.status === "failed" || agrovetWrote
              ? ""
              : `<p class="ag-av-box ag-av-card-block ag-av-card-block__line ag-av-waiting">${esc(
                  t("reply.waiting"),
                )}</p>`
        }

        ${threadHtml(request, lang)}
      </div>

      <div class="ag-av__bottom">
        ${notes.map((note) => `<p class="ag-av__status">${esc(note)}</p>`).join("")}
        ${
          closed
            ? ""
            : `
              <button type="button" class="ag-av-close" id="ag-av-close">${esc(
                t("request.close"),
              )}</button>
              <div class="ag-av-confirm" id="ag-av-confirm" hidden>
                <p class="ag-av-confirm__question">${esc(t("request.closeConfirm"))}</p>
                <div class="ag-av-confirm__actions">
                  <button type="button" class="ag-av-confirm__yes" id="ag-av-close-yes">${esc(
                    t("request.closeYes"),
                  )}</button>
                  <button type="button" class="ag-av-confirm__no" id="ag-av-close-no">${esc(
                    t("request.closeNo"),
                  )}</button>
                </div>
              </div>`
        }
      </div>
    </section>
  `;
}

export function mount(root, params = {}) {
  const clientId = params.clientId;
  if (!agrovetRequests.find(clientId)) {
    replace("/requests");
    return null;
  }

  bindBack(root, () => back("/requests"));

  const input = () => root.querySelector("#ag-av-message");
  const confirm = root.querySelector("#ag-av-confirm");
  const confirming = () => Boolean(confirm && !confirm.hidden);

  const redraw = () =>
    go("/request", {
      ...params,
      redraw: true,
      focusMessage: document.activeElement === input(),
    });

  // ---- close, with an inline question
  const closeButton = root.querySelector("#ag-av-close");
  closeButton?.addEventListener("click", () => {
    closeButton.hidden = true;
    confirm.hidden = false;
    root.querySelector("#ag-av-close-no").focus();
  });
  root.querySelector("#ag-av-close-no")?.addEventListener("click", () => {
    confirm.hidden = true;
    closeButton.hidden = false;
    closeButton.focus();
  });
  root.querySelector("#ag-av-close-yes")?.addEventListener("click", async () => {
    await agrovetRequests.close(clientId);
    redraw();
  });

  // ---- messages
  const scrollToLatest = () =>
    root
      .querySelector("#ag-av-thread-list > :last-child")
      ?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });

  bindThread(root, clientId, { onSent: scrollToLatest });
  if (params.focusMessage) {
    input()?.focus();
    scrollToLatest();
  }

  // When something changes: redraw the screen, unless the farmer is typing
  // or answering the close question. Then only the messages are refreshed, so
  // nothing they typed is lost.
  const onUpdate = () => {
    if (confirming() || input()?.value) {
      const request = agrovetRequests.find(clientId);
      const list = root.querySelector("#ag-av-thread-list");
      if (request && list) list.innerHTML = messagesHtml(request);
      return;
    }
    redraw();
  };
  window.addEventListener(AGROVETS_UPDATED, onUpdate);

  // On open: send anything waiting, then fetch status, replies and this thread.
  if (!params.redraw && isOnline()) {
    agrovetRequests.sync().then(() => agrovetRequests.refreshMessages(clientId));
  }

  return () => window.removeEventListener(AGROVETS_UPDATED, onUpdate);
}
