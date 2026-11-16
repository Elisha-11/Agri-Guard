/**
 * Screen 9 — Enter Code (Figma node 94:5).
 *
 * NOTE ON FIDELITY: like sign-in.js, this frame's full design context could
 * not be read before the Figma MCP quota ran out. The structure follows the
 * frame (back button, heading, code destination, six 48px digit boxes with
 * an 8px gap, expiry countdown, a disabled "Send again" with its cooldown
 * line, a wrong-code error line and a 64px "Sign in" button) using the
 * established tokens. Copy and colours want a re-check against the frame.
 *
 * No SMS gateway exists yet, so the code is generated in the browser and
 * shown on screen behind a clearly marked demo note.
 */

import { t } from "../i18n.js";
import { esc, backButton, bindBack } from "../ui.js";
import { go, back } from "../router.js";
import { state } from "../state.js";

const CODE_LENGTH = 6;
const EXPIRY_SECONDS = 300;
const RESEND_COOLDOWN_SECONDS = 30;

function generateCode() {
  const buffer = new Uint32Array(1);
  crypto.getRandomValues(buffer);
  return String(buffer[0] % 10 ** CODE_LENGTH).padStart(CODE_LENGTH, "0");
}

function formatClock(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

export function render() {
  const boxes = Array.from(
    { length: CODE_LENGTH },
    (_, index) => `
      <input
        type="text"
        class="ag-code__digit"
        inputmode="numeric"
        maxlength="1"
        autocomplete="${index === 0 ? "one-time-code" : "off"}"
        data-index="${index}"
        aria-label="${esc(t("code.digitLabel", { position: index + 1 }))}"
      />
    `,
  ).join("");

  return `
    <section class="ag-screen ag-auth">
      ${backButton()}

      <h1 class="ag-auth__heading">${esc(t("code.heading"))}</h1>
      <p class="ag-auth__sub">${esc(t("code.sentTo", { phone: `+260 ${state.phone}` }))}</p>

      <div class="ag-code">${boxes}</div>

      <p class="ag-auth__meta" id="ag-expiry"></p>

      <button type="button" class="ag-auth__resend" id="ag-resend" disabled>
        ${esc(t("code.resend"))}
      </button>
      <p class="ag-auth__meta" id="ag-cooldown" style="margin-top: 8px"></p>

      <p class="ag-error" id="ag-error" role="alert"></p>

      <p class="ag-auth__devnote" id="ag-devnote"></p>

      <div style="flex: 1 1 auto"></div>

      <button type="button" class="ag-btn" id="ag-signin">${esc(t("code.signIn"))}</button>
    </section>
  `;
}

export function mount(root) {
  if (!state.phone) {
    go("/sign-in");
    return null;
  }

  bindBack(root, () => back("/sign-in"));

  const digits = [...root.querySelectorAll(".ag-code__digit")];
  const expiry = root.querySelector("#ag-expiry");
  const cooldown = root.querySelector("#ag-cooldown");
  const resend = root.querySelector("#ag-resend");
  const error = root.querySelector("#ag-error");
  const devnote = root.querySelector("#ag-devnote");

  let code = generateCode();
  let secondsLeft = EXPIRY_SECONDS;
  let cooldownLeft = RESEND_COOLDOWN_SECONDS;

  const showCode = () => {
    devnote.textContent = t("code.demoNote", { code });
  };

  const tick = () => {
    secondsLeft = Math.max(0, secondsLeft - 1);
    cooldownLeft = Math.max(0, cooldownLeft - 1);

    expiry.textContent =
      secondsLeft > 0 ? t("code.expires", { time: formatClock(secondsLeft) }) : t("code.expired");

    if (cooldownLeft > 0) {
      cooldown.textContent = t("code.cooldown", { seconds: cooldownLeft });
      resend.disabled = true;
    } else {
      cooldown.textContent = "";
      resend.disabled = false;
    }
  };

  const timer = setInterval(tick, 1000);
  tick();
  showCode();

  digits.forEach((box, index) => {
    box.addEventListener("input", () => {
      box.value = box.value.replace(/\D/g, "").slice(0, 1);
      error.textContent = "";
      if (box.value && index < digits.length - 1) digits[index + 1].focus();
    });

    box.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !box.value && index > 0) digits[index - 1].focus();
      if (event.key === "Enter") submit();
    });

    box.addEventListener("paste", (event) => {
      const pasted = (event.clipboardData?.getData("text") ?? "").replace(/\D/g, "");
      if (!pasted) return;

      event.preventDefault();
      pasted
        .slice(0, digits.length - index)
        .split("")
        .forEach((char, offset) => {
          digits[index + offset].value = char;
        });
      digits[Math.min(index + pasted.length, digits.length - 1)].focus();
    });
  });

  function submit() {
    const entered = digits.map((box) => box.value).join("");

    if (entered.length !== CODE_LENGTH) {
      error.textContent = t("code.incomplete");
      return;
    }

    if (secondsLeft === 0) {
      error.textContent = t("code.expired");
      return;
    }

    if (entered !== code) {
      error.textContent = t("code.wrong");
      return;
    }

    state.signedIn = true;
    go("/capture");
  }

  resend.addEventListener("click", () => {
    code = generateCode();
    secondsLeft = EXPIRY_SECONDS;
    cooldownLeft = RESEND_COOLDOWN_SECONDS;
    digits.forEach((box) => {
      box.value = "";
    });
    error.textContent = "";
    digits[0].focus();
    showCode();
    tick();
  });

  root.querySelector("#ag-signin").addEventListener("click", submit);
  digits[0].focus();

  return () => clearInterval(timer);
}
