/**
 * Screen 3 — Result (Figma node 45:19).
 *
 * Shown when the prediction comes back "confident". Also serves as the detail
 * view for a saved check, opened from the history list with `{ entryId }`.
 *
 * Each advice card opens screen 4 (Advice) for the full text; the chevron
 * inside the card collapses it in place without leaving the screen.
 *
 * Card text comes only from published, agronomist-reviewed advice in the
 * advisory bundle (src/advisory.js); without it the screen says so.
 */

import { icons, photos } from "../icons.js";
import { t } from "../i18n.js";
import { esc, demoNote, backButton, severityBar, bindBack } from "../ui.js";
import { go, back } from "../router.js";
import { session, findHistoryEntry } from "../state.js";
import { displayName, severityDisplay, confidencePercent } from "../disease.js";
import { adviceFor, adviceCards, advisoryMessage } from "../advisory.js";
import { alertFor } from "../alerts.js";
import { speak, stopSpeaking } from "../speech.js";

const SECTION_ICONS = { treat: icons.droplet, prevent: icons.shield, check: icons.calendar };

/**
 * Resolve what to show: the check just run, or a saved history entry.
 * Returns null when neither is available.
 */
export function resolveSubject(params = {}) {
  // Opened from a nearby-outbreak alert: a disease, but no photo or diagnosis.
  if (params.classId) {
    return {
      classId: params.classId,
      name: displayName(params.classId),
      confidence: null,
      severity: null,
      photo: null,
      fromHistory: false,
      fromAlert: true,
    };
  }

  if (params.entryId) {
    const entry = findHistoryEntry(params.entryId);
    if (!entry) return null;

    return {
      classId: entry.classId,
      name: entry.name ?? displayName(entry.classId),
      confidence: entry.confidence,
      severity: entry.severity,
      photo: entry.thumb || photos.resultPhoto,
      fromHistory: true,
    };
  }

  if (session.prediction) {
    return {
      classId: session.prediction.class_id,
      name: displayName(session.prediction.class_id),
      confidence: session.prediction.confidence,
      severity: session.prediction.severity,
      photo: session.imageUrl || photos.resultPhoto,
      fromHistory: false,
    };
  }

  return null;
}

/** Published advice for the subject, its cards, and the name to show. */
export function adviceView(subject) {
  const advice = adviceFor(subject.classId);
  return {
    advice,
    cards: adviceCards(advice),
    name: advice?.local_name || advice?.name || subject.name,
  };
}

/**
 * "N farms within 10 km reported this in the last 7 days", when the disease
 * just diagnosed is an active nearby outbreak (cached alerts, ADR 0018).
 */
export function nearbyText(subject) {
  const alert = subject.fromAlert ? null : alertFor(subject.classId);
  return alert
    ? t("alerts.afterDiagnosis", {
        count: alert.farm_count,
        km: alert.distance_band_km,
        days: alert.window_days,
      })
    : "";
}

function nearbyBanner(subject) {
  const text = nearbyText(subject);
  return text
    ? `<p class="ag-nearby" role="note"><img src="${
        icons.warning
      }" alt="" width="18" height="18" /><span>${esc(text)}</span></p>`
    : "";
}

/** Collapsed card text: the first step, or the "not checked yet" message. */
function cardsHtml(cards) {
  if (!cards.length) {
    return `
      <div class="ag-section ag-section--static" data-section="none">
        <span class="ag-section__icon">
          <img src="${icons.warning}" alt="" width="24" height="24" />
        </span>
        <span class="ag-section__text">
          <span class="ag-section__body">${esc(advisoryMessage("no_advice"))}</span>
        </span>
      </div>
    `;
  }

  return cards
    .map(
      (section) => `
        <div
          class="ag-section"
          role="button"
          tabindex="0"
          data-section="${esc(section.key)}"
          data-collapsed="false"
        >
          <span class="ag-section__icon">
            <img src="${SECTION_ICONS[section.key]}" alt="" width="24" height="24" />
          </span>
          <span class="ag-section__text">
            <span class="ag-section__title">${esc(section.title)}</span>
            <span class="ag-section__body">${esc(section.steps[0])}</span>
          </span>
          <button
            type="button"
            class="ag-section__toggle"
            data-toggle="${esc(section.key)}"
            aria-label="${esc(t("action.collapse"))}"
          >
            <img src="${icons.chevronUp}" alt="" width="24" height="24" />
          </button>
        </div>
      `,
    )
    .join("");
}

export function render(params = {}) {
  const subject = resolveSubject(params);
  if (!subject) return "";

  const severity = severityDisplay(subject.severity);
  const view = adviceView(subject);

  return `
    <section class="ag-screen">
      ${demoNote()}

      <div class="ag-screen__scroll">
        <div class="ag-result__photo">
          <img src="${esc(subject.photo)}" alt="${esc(t("result.photoAlt"))}" />
          <span class="ag-result__back">${backButton()}</span>
        </div>

        <div class="ag-result__body">
          <h1 class="ag-result__name">${esc(view.name)}</h1>
          <p class="ag-result__sure">
            ${esc(t("result.sure", { percent: confidencePercent(subject.confidence) }))}
          </p>

          ${severityBar(severity)}
          ${nearbyBanner(subject)}

          <div class="ag-sections">${cardsHtml(view.cards)}</div>
        </div>
      </div>

      <div class="ag-screen__footer">
        <button type="button" class="ag-btn" id="ag-listen">
          <img src="${icons.speaker}" alt="" width="24" height="24" />
          <span>${esc(t("action.listen"))}</span>
        </button>
      </div>
    </section>
  `;
}

export function mount(root, params = {}) {
  const subject = resolveSubject(params);

  if (!subject) {
    go("/capture");
    return null;
  }

  bindBack(root, () => back(subject.fromHistory ? "/history" : "/capture"));

  root.querySelectorAll(".ag-section:not(.ag-section--static)").forEach((card) => {
    card.addEventListener("click", (event) => {
      const toggle = event.target.closest("[data-toggle]");

      if (toggle) {
        // Collapse in place; do not also open the advice screen.
        event.preventDefault();
        event.stopPropagation();
        const collapsed = card.dataset.collapsed === "true";
        card.dataset.collapsed = String(!collapsed);
        toggle.setAttribute("aria-label", collapsed ? t("action.collapse") : t("action.expand"));
        return;
      }

      go("/advice", { ...params, section: card.dataset.section });
    });

    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      if (event.target.closest("[data-toggle]")) return;
      event.preventDefault();
      go("/advice", { ...params, section: card.dataset.section });
    });
  });

  const listen = root.querySelector("#ag-listen");
  const onListen = () => {
    const view = adviceView(subject);
    const spoken = speak([
      view.name,
      t("result.sure", { percent: confidencePercent(subject.confidence) }),
      nearbyText(subject),
      ...(view.cards.length
        ? view.cards.flatMap((section) => [section.title, section.steps[0]])
        : [advisoryMessage("no_advice")]),
    ]);

    if (!spoken) listen.querySelector("span").textContent = t("action.listenUnavailable");
  };

  listen.addEventListener("click", onListen);

  return () => stopSpeaking();
}
