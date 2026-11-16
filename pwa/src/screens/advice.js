/**
 * Screen 4 — Advice (Figma node 71:24).
 *
 * The expanded form of the three result cards, plus the safety panel. Reached
 * by tapping a card on screen 3; `params.section` scrolls that card into view.
 *
 * The body copy is the placeholder wording from the design. Real treatment
 * instructions are pending agronomist sign-off (docs/class-taxonomy.md), and
 * this screen must not invent them.
 */

import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc, demoNote, backButton, severityBar, bindBack } from "../ui.js";
import { back } from "../router.js";
import { severityDisplay } from "../disease.js";
import { speak, stopSpeaking } from "../speech.js";
import { resolveSubject } from "./result.js";

const CARDS = [
  { key: "treat", icon: icons.droplet28, title: "advice.treat.title", body: "advice.treat.full" },
  {
    key: "prevent",
    icon: icons.shield28,
    title: "advice.prevent.title",
    body: "advice.prevent.full",
  },
  { key: "check", icon: icons.calendar28, title: "advice.check.title", body: "advice.check.full" },
];

export function render(params = {}) {
  const subject = resolveSubject(params);
  if (!subject) return "";

  const severity = severityDisplay(subject.severity);

  const cards = CARDS.map(
    (card) => `
      <article class="ag-advice__card" data-card="${esc(card.key)}">
        <div class="ag-advice__head">
          <span class="ag-advice__icon">
            <img src="${card.icon}" alt="" width="28" height="28" />
          </span>
          <h2 class="ag-advice__title">${esc(t(card.title))}</h2>
        </div>
        <p class="ag-advice__text">${esc(t(card.body))}</p>
      </article>
    `,
  ).join("");

  return `
    <section class="ag-screen">
      ${demoNote()}

      <div class="ag-screen__scroll">
        <div class="ag-advice__photo">
          <img src="${esc(subject.photo)}" alt="${esc(t("result.photoAlt"))}" />
          <span class="ag-result__back">${backButton()}</span>
        </div>

        <div class="ag-advice__body">
          <h1 class="ag-advice__name">${esc(subject.name)}</h1>
          ${severityBar(severity)}

          ${cards}

          <article class="ag-advice__card ag-advice__card--safety">
            <div class="ag-advice__head">
              <span class="ag-advice__icon">
                <img src="${icons.warning}" alt="" width="24" height="24" />
              </span>
              <h2 class="ag-advice__title">${esc(t("advice.safety.title"))}</h2>
            </div>
            <p class="ag-advice__text">${esc(t("advice.safety.body"))}</p>
          </article>
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

  if (params.section) {
    const card = root.querySelector(`[data-card="${CSS.escape(params.section)}"]`);
    if (card) card.scrollIntoView({ block: "center" });
  }

  const listen = root.querySelector("#ag-listen");

  listen.addEventListener("click", () => {
    const spoken = speak([
      subject.name,
      ...CARDS.flatMap((card) => [t(card.title), t(card.body)]),
      t("advice.safety.title"),
      t("advice.safety.body"),
    ]);

    if (!spoken) listen.querySelector("span").textContent = t("action.listenUnavailable");
  });

  return () => stopSpeaking();
}
