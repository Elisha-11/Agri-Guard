/**
 * Screen 8 — Sign In (Figma node 94:4).
 *
 * NOTE ON FIDELITY: the Figma MCP quota ran out before this frame's full
 * design context could be read, so the layout here is built from the frame's
 * structure (logo 64px, heading, SMS explanation, phone field with a fixed
 * +260 prefix and a divider, error line, 64px "Send code" button, at the
 * y-offsets in the file) using the tokens the other ten screens established.
 * Colours and exact copy should be re-checked against the frame.
 *
 * There is no auth endpoint in docs/api-contract.yaml yet, so no SMS is sent:
 * enter-code.js generates the code locally and shows it on screen.
 */

import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc } from "../ui.js";
import { go } from "../router.js";
import { state } from "../state.js";

/** Zambian mobile numbers are 9 digits after the +260 country code. */
const LOCAL_DIGITS = 9;

export function render() {
  return `
    <section class="ag-screen ag-auth">
      <img src="${icons.leaf}" alt="" class="ag-auth__logo" width="64" height="64" />

      <h1 class="ag-auth__heading">${esc(t("signIn.heading"))}</h1>
      <p class="ag-auth__sub">${esc(t("signIn.explain"))}</p>

      <div class="ag-phone">
        <span class="ag-phone__prefix">+260</span>
        <span class="ag-phone__divider"></span>
        <input
          type="tel"
          id="ag-phone"
          class="ag-phone__input"
          inputmode="numeric"
          autocomplete="tel-national"
          maxlength="${LOCAL_DIGITS}"
          placeholder="${esc(t("signIn.placeholder"))}"
          aria-label="${esc(t("signIn.phoneLabel"))}"
          value="${esc(state.phone)}"
        />
      </div>

      <p class="ag-error" id="ag-error" role="alert"></p>

      <button type="button" class="ag-btn" id="ag-send" style="margin-top: 16px">
        ${esc(t("signIn.send"))}
      </button>
    </section>
  `;
}

export function mount(root) {
  const input = root.querySelector("#ag-phone");
  const error = root.querySelector("#ag-error");
  const send = root.querySelector("#ag-send");

  input.addEventListener("input", () => {
    input.value = input.value.replace(/\D/g, "").slice(0, LOCAL_DIGITS);
    error.textContent = "";
  });

  const submit = () => {
    const digits = input.value.replace(/\D/g, "");

    if (digits.length !== LOCAL_DIGITS) {
      error.textContent = t("signIn.error");
      input.focus();
      return;
    }

    state.phone = digits;
    go("/code");
  };

  send.addEventListener("click", submit);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") submit();
  });

  return null;
}
