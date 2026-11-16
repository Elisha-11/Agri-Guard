/**
 * AgriGuard AI — PWA entry point.
 *
 * Wires the twelve screens from the AgriGuard Screens Figma file into the
 * hash router, with a guard that keeps a signed-out user on the auth screens.
 *
 * Every prediction in this build comes from the mock stub in
 * inference/diagnose.js. The demonstration-mode notice on the result screens
 * must stay until real inference ships.
 */

import "bootstrap/dist/css/bootstrap.min.css";
import "./styles.css";

import { defineRoutes, setGuard, start } from "./router.js";
import { initI18n } from "./i18n.js";
import { state } from "./state.js";
import { registerServiceWorker, mountConnectionIndicator } from "./offline.js";

import * as capture from "./screens/capture.js";
import * as processing from "./screens/processing.js";
import * as result from "./screens/result.js";
import * as resultUncertain from "./screens/result-uncertain.js";
import * as resultConsult from "./screens/result-consult.js";
import * as resultRejected from "./screens/result-rejected.js";
import * as advice from "./screens/advice.js";
import * as history from "./screens/history.js";
import * as settings from "./screens/settings.js";
import * as language from "./screens/language.js";
import * as signIn from "./screens/sign-in.js";
import * as enterCode from "./screens/enter-code.js";

const AUTH_ROUTES = new Set(["/sign-in", "/code"]);

defineRoutes({
  "/": capture,
  "/capture": capture,
  "/processing": processing,
  "/result": result,
  "/uncertain": resultUncertain,
  "/consult": resultConsult,
  "/rejected": resultRejected,
  "/advice": advice,
  "/history": history,
  "/settings": settings,
  "/language": language,
  "/sign-in": signIn,
  "/code": enterCode,
  "*": capture,
});

setGuard((path) => {
  if (!state.signedIn && !AUTH_ROUTES.has(path)) return "/sign-in";
  if (state.signedIn && path === "/sign-in") return "/capture";
  return null;
});

registerServiceWorker();

initI18n(state.language).then(() => {
  start(document.querySelector("#app"));
  mountConnectionIndicator();
});
