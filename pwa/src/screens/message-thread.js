/**
 * The message thread on a request (screen 13), shown below the reply cards.
 *
 * The endpoints behind it are PROPOSED and only answered by the mock
 * (src/agrovet-api.js, VITE_AGROVET_MOCK) until the backend confirms them.
 *
 * - Messages in time order: the farmer's on the right, the agrovet's on the
 *   left. Each farmer message says "Waiting for signal", "Sending…", "Sent"
 *   or "Not sent". An agrovet message that fell back to English says so.
 * - Quick replies only fill the text box; the farmer can edit before sending.
 * - Empty and over-long messages are stopped with a line saying why.
 * - A farmer who did not share their phone number is asked before sending a
 *   message that looks like one.
 * - On a closed request the composer is gone and a note says why.
 *
 * No Figma frame exists for the thread yet: it uses frame 13's cards,
 * colours and buttons.
 */

import { t, currentLanguage } from "../i18n.js";
import { esc } from "../ui.js";
import { MESSAGE_MAX_LENGTH } from "../agrovet-api.js";
import {
  agrovetRequests,
  looksLikePhoneNumber,
  messageProblem,
  replyLanguageNote,
} from "../agrovet-requests.js";

export const QUICK_REPLIES = ["message.quick.price", "message.quick.visit", "message.quick.stock"];

/** The counter appears once a message gets this close to the limit. */
const COUNTER_FROM = MESSAGE_MAX_LENGTH - 100;

const STATUS_KEYS = {
  queued: "message.waiting",
  sending: "message.sending",
  sent: "message.sent",
  failed: "message.failed",
};

function timeOf(iso) {
  try {
    const locale = (typeof document !== "undefined" && document.documentElement.lang) || "en";
    return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(
      new Date(iso),
    );
  } catch {
    return "";
  }
}

export function messageBubble(message, lang = currentLanguage()) {
  const mine = message.sender === "farmer";
  const meta = [
    timeOf(message.created_at),
    mine && STATUS_KEYS[message.status] ? t(STATUS_KEYS[message.status]) : "",
    !mine && replyLanguageNote(message, lang) ? t("message.english") : "",
  ].filter(Boolean);

  return `
    <div class="ag-av-msg ag-av-msg--${mine ? "farmer" : "agrovet"}${
      mine && message.status !== "sent" ? " is-pending" : ""
    }" data-message="${esc(message.client_id ?? message.id)}" data-status="${esc(
      message.status ?? "sent",
    )}">
      <p class="ag-av-msg__text">${esc(message.text)}</p>
      <p class="ag-av-msg__meta">${esc(meta.join(" · "))}</p>
    </div>
  `;
}

/** The messages, oldest first. */
export function messagesHtml(request, lang = currentLanguage()) {
  return [...(request.messages ?? [])]
    .sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""))
    .map((message) => messageBubble(message, lang))
    .join("");
}

function composerHtml() {
  return `
    <div class="ag-av-quick" role="group" aria-label="${esc(t("message.quickTitle"))}">
      ${QUICK_REPLIES.map(
        (key) =>
          `<button type="button" class="ag-av-quick__chip" data-quick="${esc(key)}">${esc(
            t(key),
          )}</button>`,
      ).join("")}
    </div>
    <form class="ag-av-compose" id="ag-av-compose" novalidate>
      <label class="ag-visually-hidden" for="ag-av-message">${esc(t("message.placeholder"))}</label>
      <textarea id="ag-av-message" class="ag-av-compose__input" rows="2"
        placeholder="${esc(t("message.placeholder"))}"
        aria-describedby="ag-av-message-hint"></textarea>
      <button type="submit" class="ag-av-compose__send">${esc(t("message.send"))}</button>
    </form>
    <p class="ag-av-compose__hint" id="ag-av-message-hint" aria-live="polite"></p>
    <div class="ag-av-warning" id="ag-av-phone-warning" role="alert" hidden>
      <p class="ag-av-warning__text">${esc(t("message.phoneWarning"))}</p>
      <div class="ag-av-confirm__actions">
        <button type="button" class="ag-av-confirm__no" id="ag-av-edit-message">${esc(
          t("message.edit"),
        )}</button>
        <button type="button" class="ag-av-warning__send" id="ag-av-send-anyway">${esc(
          t("message.sendAnyway"),
        )}</button>
      </div>
    </div>
  `;
}

/** The whole thread block: messages, then the composer or the closed note. */
export function threadHtml(request, lang = currentLanguage()) {
  const closed = request.status === "closed";
  const canMessage = !closed && request.status !== "failed";
  return `
    <section class="ag-av-thread" aria-label="${esc(t("message.title"))}">
      <div class="ag-av-thread__list" id="ag-av-thread-list">${messagesHtml(request, lang)}</div>
      ${closed ? `<p class="ag-av-thread__closed">${esc(t("message.closed"))}</p>` : ""}
      ${canMessage ? composerHtml() : ""}
    </section>
  `;
}

/** The hint line under the box: why it cannot be sent, or a character count near the limit. */
export function hintFor(text, { submitted = false } = {}) {
  const problem = messageProblem(text);
  if (problem === "tooLong") {
    return { error: true, text: t("message.tooLong", { max: MESSAGE_MAX_LENGTH }) };
  }
  if (problem === "empty" && submitted) return { error: true, text: t("message.empty") };
  const length = String(text ?? "").trim().length;
  if (length >= COUNTER_FROM) {
    return {
      error: false,
      text: t("message.counter", { count: length, max: MESSAGE_MAX_LENGTH }),
    };
  }
  return { error: false, text: "" };
}

/**
 * Wire the composer for request `clientId`. `onSent` runs after a message is
 * saved (sent or queued).
 */
export function bindThread(root, clientId, { onSent = () => {} } = {}) {
  const form = root.querySelector("#ag-av-compose");
  if (!form) return;
  const input = root.querySelector("#ag-av-message");
  const hint = root.querySelector("#ag-av-message-hint");
  const warning = root.querySelector("#ag-av-phone-warning");

  const showHint = (submitted = false) => {
    const { error, text } = hintFor(input.value, { submitted });
    hint.textContent = text;
    hint.classList.toggle("is-error", error);
  };

  const sendNow = async () => {
    const text = input.value;
    if (messageProblem(text)) {
      showHint(true);
      return;
    }
    input.value = "";
    showHint();
    warning.hidden = true;
    form.hidden = false;
    await agrovetRequests.sendMessage(clientId, text);
    onSent();
  };

  root.querySelectorAll("[data-quick]").forEach((chip) => {
    chip.addEventListener("click", () => {
      input.value = t(chip.dataset.quick);
      showHint();
      input.focus();
      input.setSelectionRange?.(input.value.length, input.value.length);
    });
  });

  input.addEventListener("input", () => showHint());

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (messageProblem(input.value)) {
      showHint(true);
      input.focus();
      return;
    }
    const request = agrovetRequests.find(clientId);
    if (!request?.share_phone && looksLikePhoneNumber(input.value)) {
      form.hidden = true;
      warning.hidden = false;
      root.querySelector("#ag-av-edit-message").focus();
      return;
    }
    sendNow();
  });

  root.querySelector("#ag-av-send-anyway").addEventListener("click", sendNow);
  root.querySelector("#ag-av-edit-message").addEventListener("click", () => {
    warning.hidden = true;
    form.hidden = false;
    input.focus();
  });
}
