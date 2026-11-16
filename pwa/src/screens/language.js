/**
 * Screen 7 — Language (Figma node 90:3).
 *
 * The four options match public/locales/. Only `en` is populated today, so
 * picking Bemba, Nyanja or Tonga currently shows English text — i18n.js falls
 * back per string. The choice is still stored and applied, so the screens
 * will switch over as soon as the translation files are filled in.
 */

import { icons } from "../icons.js";
import { t, setLanguage, currentLanguage, LANGUAGES } from "../i18n.js";
import { esc, backButton, bindBack } from "../ui.js";
import { back } from "../router.js";
import { state } from "../state.js";
import { refreshAdvisory } from "../advisory.js";

export function render() {
  const active = currentLanguage();

  const options = LANGUAGES.map(
    (language) => `
      <li>
        <button
          type="button"
          class="ag-language__option"
          role="radio"
          aria-checked="${language.code === active}"
          data-lang="${esc(language.code)}"
        >
          <span>${esc(language.label)}</span>
          <img
            src="${language.code === active ? icons.radioSelected : icons.radioUnselected}"
            alt=""
            width="28"
            height="28"
          />
        </button>
      </li>
    `,
  ).join("");

  return `
    <section class="ag-screen">
      <div class="ag-screen__scroll">
        <div class="ag-language__head">
          ${backButton()}
          <h1 class="ag-language__title">${esc(t("language.title"))}</h1>
        </div>

        <ul class="ag-language__list" role="radiogroup" aria-label="${esc(t("language.title"))}">
          ${options}
        </ul>
      </div>

      <div class="ag-screen__footer">
        <button type="button" class="ag-btn" id="ag-done">${esc(t("language.done"))}</button>
      </div>
    </section>
  `;
}

export function mount(root) {
  bindBack(root, () => back("/settings"));

  root.querySelectorAll("[data-lang]").forEach((option) => {
    option.addEventListener("click", async () => {
      const code = option.dataset.lang;
      state.language = code;
      await setLanguage(code);
      refreshAdvisory(code); // advice in the new language, in the background

      // Re-render in the newly chosen language.
      root.innerHTML = render();
      mount(root);
    });
  });

  root.querySelector("#ag-done").addEventListener("click", () => back("/settings"));

  return null;
}
