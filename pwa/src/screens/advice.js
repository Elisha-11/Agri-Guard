/**
 * Screen 4 — Advice (Figma node 71:24).
 *
 * The expanded form of the result cards. Reached by tapping a card on
 * screen 3; `params.section` scrolls that card into view.
 *
 * Everything shown comes from published advice in the advisory bundle
 * (src/advisory.js), which the backend only publishes once an agronomist is
 * recorded as reviewer. The safety warning, when there is one, comes before
 * the treatment steps (docs/backend/advisory-bundle.md). Without published
 * advice the screen shows the bundle's "not checked by an expert yet" message
 * and no treatment at all.
 */

import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc, demoNote, backButton, severityBar, bindBack } from "../ui.js";
import { back } from "../router.js";
import { severityDisplay } from "../disease.js";
import { advisoryMessage } from "../advisory.js";
import { speak, stopSpeaking } from "../speech.js";
import { resolveSubject, adviceView } from "./result.js";

const CARD_ICONS = { treat: icons.droplet28, prevent: icons.shield28, check: icons.calendar28 };

function card({ key, icon, title, steps, text, extraClass = "" }) {
  const body = steps
    ? `<ol class="ag-advice__steps">${steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol>`
    : `<p class="ag-advice__text">${esc(text)}</p>`;

  return `
    <article class="ag-advice__card ${extraClass}" data-card="${esc(key)}">
      <div class="ag-advice__head">
        <span class="ag-advice__icon">
          <img src="${icon}" alt="" width="28" height="28" />
        </span>
        ${title ? `<h2 class="ag-advice__title">${esc(title)}</h2>` : ""}
      </div>
      ${body}
    </article>
  `;
}

export function render(params = {}) {
  const subject = resolveSubject(params);
  if (!subject) return "";

  const severity = severityDisplay(subject.severity);
  const { advice, cards, name } = adviceView(subject);

  let content;
  if (!cards.length) {
    content = card({ key: "none", icon: icons.warning, text: advisoryMessage("no_advice") });
  } else {
    const safety = advice.safety_warning
      ? card({
          key: "safety",
          icon: icons.warning,
          title: t("advice.safety.title"),
          text: advice.safety_warning,
          extraClass: "ag-advice__card--safety",
        })
      : "";
    const sections = cards
      .map((section) => card({ ...section, icon: CARD_ICONS[section.key] }))
      .join("");
    const reviewed = advice.reviewed_by
      ? `<p class="ag-advice__reviewed">${esc(
          t("advice.reviewedBy", { name: advice.reviewed_by, date: advice.reviewed_at ?? "" }),
        )}</p>`
      : "";
    content = safety + sections + reviewed;
  }

  return `
    <section class="ag-screen">
      ${demoNote()}

      <div class="ag-screen__scroll">
        ${
          subject.photo
            ? `<div class="ag-advice__photo">
                <img src="${esc(subject.photo)}" alt="${esc(t("result.photoAlt"))}" />
                <span class="ag-result__back">${backButton()}</span>
              </div>`
            : `<div class="ag-advice__nophoto">${backButton()}</div>`
        }

        <div class="ag-advice__body">
          <h1 class="ag-advice__name">${esc(name)}</h1>
          ${subject.severity == null ? "" : severityBar(severity)}

          ${content}
        </div>
      </div>

      <div class="ag-screen__footer">
        <button type="button" class="ag-btn" id="ag-listen">
          <img src="${icons.speakerAdvice}" alt="" width="24" height="24" />
          <span>${esc(t("action.listen"))}</span>
        </button>
      </div>
    </section>
  `;
}

export function mount(root, params = {}) {
  const subject = resolveSubject(params);

  if (!subject) {
    back("/capture");
    return null;
  }

  bindBack(root, () => back(subject.fromHistory ? "/history" : "/capture"));
  // From an alert, "back" returns to the capture screen it was opened from.

  if (params.section) {
    const target = root.querySelector(`[data-card="${CSS.escape(params.section)}"]`);
    if (target) target.scrollIntoView({ block: "center" });
  }

  const listen = root.querySelector("#ag-listen");

  listen.addEventListener("click", () => {
    const { advice, cards, name } = adviceView(subject);
    const lines = cards.length
      ? [
          name,
          ...(advice.safety_warning ? [t("advice.safety.title"), advice.safety_warning] : []),
          ...cards.flatMap((section) => [section.title, ...section.steps]),
        ]
      : [name, advisoryMessage("no_advice")];

    if (!speak(lines)) listen.querySelector("span").textContent = t("action.listenUnavailable");
  });

  return () => stopSpeaking();
}
