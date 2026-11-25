/**
 * AgriGuard AI — PWA entry point.
 *
 * Wires the twelve screens from the AgriGuard Screens Figma file into the
 * hash router, with a guard that keeps a signed-out user on the auth screens.
 *
 * Predictions come from the on-device model (inference/diagnose.js) and
 * treatment advice from the published advisory bundle (advisory.js). The
 * "early test model" notice stays on result screens while the model is the
 * baseline release.
 */

import "bootstrap/dist/css/bootstrap.min.css";
import "./styles.css";

import { defineRoutes, setGuard, start } from "./router.js";
import { initI18n } from "./i18n.js";
import { state } from "./state.js";
import { registerServiceWorker, mountConnectionIndicator } from "./offline.js";
import { startAdvisorySync } from "./advisory.js";
import { startAlertSync } from "./alerts.js";
import { startModelUpdates } from "./inference/model.js";
import { startAgrovetSync } from "./agrovet-requests.js";

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
import * as agrovets from "./screens/agrovets.js";
import * as agrovetRequest from "./screens/agrovet-request.js";
import * as requests from "./screens/requests.js";
import * as requestDetail from "./screens/request-detail.js";

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
  "/agrovets": agrovets,
  "/agrovet-request": agrovetRequest,
  "/requests": requests,
  "/request": requestDetail,
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
  startAdvisorySync();
  startAlertSync();
  startModelUpdates();
  startAgrovetSync();
});
