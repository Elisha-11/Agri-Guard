/**
 * Screen 3 — Result (Figma node 45:19).
 *
 * Shown when the prediction comes back "confident". Also serves as the detail
 * view for a saved check, opened from the history list with `{ entryId }`.
 *
 * Each advice card opens screen 4 (Advice) for the full text; the chevron
 * inside the card collapses it in place without leaving the screen.
 */

import { icons, photos } from "../icons.js";
import { t } from "../i18n.js";
import { esc, demoNote, backButton, severityBar, bindBack } from "../ui.js";
import { go, back } from "../router.js";
import { session, findHistoryEntry } from "../state.js";
import { displayName, severityDisplay, confidencePercent, adviceSections } from "../disease.js";
import { speak, stopSpeaking } from "../speech.js";

const SECTION_ICONS = { treat: icons.droplet, prevent: icons.shield, check: icons.calendar };

/**
 * Resolve what to show: the check just run, or a saved history entry.
 * Returns null when neither is available.
 */
export function resolveSubject(params = {}) {
  if (params.entryId) {
    const entry = findHistoryEntry(params.entryId);
    if (!entry) return null;

    return {
      name: entry.name ?? displayName(entry.classId),
      confidence: entry.confidence,
      severity: entry.severity,
      photo: entry.thumb || photos.resultPhoto,
      fromHistory: true,
    };
  }

  if (session.prediction) {
    return {
      name: displayName(session.prediction.class_id),
      confidence: session.prediction.confidence,
      severity: session.prediction.severity,
      photo: session.imageUrl || photos.resultPhoto,
      fromHistory: false,
    };
  }

  return null;
}

export function render(params = {}) {
  const subject = resolveSubject(params);
  if (!subject) return "";

  const severity = severityDisplay(subject.severity);
  const sections = adviceSections()
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
            <span class="ag-section__body">${esc(section.body)}</span>
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

  return `
    <section class="ag-screen">
      ${demoNote()}

      <div class="ag-screen__scroll">
        <div class="ag-result__photo">
          <img src="${esc(subject.photo)}" alt="${esc(t("result.photoAlt"))}" />
          <span class="ag-result__back">${backButton()}</span>
        </div>

        <div class="ag-result__body">
          <h1 class="ag-result__name">${esc(subject.name)}</h1>
          <p class="ag-result__sure">
            ${esc(t("result.sure", { percent: confidencePercent(subject.confidence) }))}
          </p>

          ${severityBar(severity)}

          <div class="ag-sections">${sections}</div>
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

  root.querySelectorAll(".ag-section").forEach((card) => {
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
    const spoken = speak([
      subject.name,
      t("result.sure", { percent: confidencePercent(subject.confidence) }),
      ...adviceSections().flatMap((section) => [section.title, section.body]),
    ]);

    if (!spoken) listen.querySelector("span").textContent = t("action.listenUnavailable");
  };

  listen.addEventListener("click", onListen);

  return () => stopSpeaking();
}
