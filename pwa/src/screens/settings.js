/**
 * Screen 6 — Settings (Figma node 90:2).
 *
 * The API health line under the version is not in the design. It carries over
 * the /api/v1/health/ check that the previous single-screen build showed, so
 * the team keeps a way to see whether the PWA can reach Django.
 */

import { icons } from "../icons.js";
import { t, languageLabel } from "../i18n.js";
import { esc, backButton, bindBack } from "../ui.js";
import { go, back } from "../router.js";
import { state, signOut } from "../state.js";
import { stopSpeaking } from "../speech.js";
import pkg from "../../package.json";

export function render() {
  const phone = state.phone ? `+260 ${state.phone}` : t("settings.phoneUnset");

  return `
    <section class="ag-screen ag-settings">
      ${backButton({ icon: icons.arrowLeftSettings, bare: true })}

      <h1 class="ag-settings__title">${esc(t("settings.title"))}</h1>

      <div class="ag-settings__group">
        <button type="button" class="ag-row" id="ag-language-row">
          <span class="ag-row__icon"><img src="${
            icons.globe
          }" alt="" width="28" height="28" /></span>
          <span class="ag-row__label">${esc(t("settings.language"))}</span>
          <span class="ag-row__value">${esc(languageLabel())}</span>
          <img src="${icons.chevronRight20}" alt="" width="20" height="20" />
        </button>

        <div class="ag-row">
          <span class="ag-row__icon"><img src="${
            icons.voice
          }" alt="" width="28" height="28" /></span>
          <span class="ag-row__label" id="ag-voice-label">${esc(t("settings.voice"))}</span>
          <button
            type="button"
            class="ag-switch"
            id="ag-voice"
            role="switch"
            aria-checked="${state.voiceNarration}"
            aria-labelledby="ag-voice-label"
          ></button>
        </div>

        <div class="ag-row ag-row--stacked">
          <span class="ag-row__icon"><img src="${
            icons.phone
          }" alt="" width="28" height="28" /></span>
          <span class="ag-row__stack">
            <span class="ag-row__label">${esc(t("settings.phone"))}</span>
            <span class="ag-row__value" style="display: block">${esc(phone)}</span>
          </span>
        </div>
      </div>

      <div class="ag-settings__group">
        <button type="button" class="ag-row ag-row--signout" id="ag-signout">
          <span class="ag-row__icon"><img src="${
            icons.logout
          }" alt="" width="28" height="28" /></span>
          <span class="ag-row__label">${esc(t("settings.signOut"))}</span>
        </button>
      </div>

      <p class="ag-settings__version">
        ${esc(t("settings.version", { version: pkg.version }))}
      </p>
      <p class="ag-settings__api">${esc(t("settings.api"))} <span id="ag-api">…</span></p>
    </section>
  `;
}

export function mount(root) {
  bindBack(root, () => back("/capture"));

  root.querySelector("#ag-language-row").addEventListener("click", () => go("/language"));

  const voice = root.querySelector("#ag-voice");
  voice.addEventListener("click", () => {
    const next = voice.getAttribute("aria-checked") !== "true";
    voice.setAttribute("aria-checked", String(next));
    state.voiceNarration = next;
    if (!next) stopSpeaking();
  });

  root.querySelector("#ag-signout").addEventListener("click", () => {
    signOut();
    go("/sign-in");
  });

  const api = root.querySelector("#ag-api");
  let live = true;

  fetch("/api/v1/health/")
    .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
    .then((health) => {
      if (live) api.textContent = `${health.status} (v${health.version})`;
    })
    .catch(() => {
      if (live) api.textContent = t("settings.apiUnreachable");
    });

  return () => {
    live = false;
  };
}
