/**
 * Screen 1 — Capture (Figma node 1:2).
 *
 * The design shows a live camera preview with a dashed framing guide, a
 * shutter button and an "Upload from gallery" button. Where getUserMedia is
 * unavailable or refused, the shutter falls back to the native camera via a
 * file input with `capture="environment"`, which is what most low-end Android
 * browsers handle best anyway.
 *
 * The capture screen doubles as the app's home, so History and Settings are
 * reached from the row above the instruction. That row is not in Figma —
 * no frame in the file provides another way into those screens.
 *
 * Live scanning: while the live camera runs, a frame is put through the model
 * every second or two and the top answer shown on the preview. It is only a
 * hint for framing the leaf; the farmer still takes a photo for the result
 * and advice. The pause between scans grows with how long a scan takes, so a
 * slow phone is never kept busy, and scanning stops in the background.
 *
 * Nearby outbreak alerts (ADR 0018) sit under the instruction: a short card
 * from src/alerts.js that works from its cached copy offline. Location is only
 * used after the farmer taps "Turn on nearby alerts".
 */

import { icons, photos } from "../icons.js";
import { t } from "../i18n.js";
import { esc } from "../ui.js";
import { go } from "../router.js";
import { setSessionImage, state } from "../state.js";
import {
  alertsCardHtml,
  alertsSpeech,
  cachedAlerts,
  alertsUnavailable,
  refreshAlerts,
  ALERTS_UPDATED,
} from "../alerts.js";
import { speak, stopSpeaking } from "../speech.js";
import { setDarkStatusBar } from "../native.js";
import { loadModel } from "../inference/model.js";
import { diagnose } from "../inference/diagnose.js";
import { displayName, confidencePercent } from "../disease.js";

/** Shortest pause between live scans, and the multiple of the last scan's time. */
const LIVE_MIN_GAP_MS = 1200;
const LIVE_GAP_FACTOR = 2;

function alertsCard() {
  return alertsCardHtml({
    consent: state.locationConsent,
    cache: cachedAlerts(),
    online: navigator.onLine,
    unavailable: alertsUnavailable(),
  });
}

export function render() {
  return `
    <section class="ag-screen ag-capture">
      <div>
        <nav class="ag-capture__nav">
          <button
            type="button"
            class="ag-capture__navbtn"
            data-nav="history"
            aria-label="${esc(t("nav.history"))}"
          >
            <img src="${icons.calendar}" alt="" />
          </button>
          <button
            type="button"
            class="ag-capture__navbtn"
            data-nav="settings"
            aria-label="${esc(t("nav.settings"))}"
          >
            <img src="${icons.globe}" alt="" />
          </button>
        </nav>
        <h1 class="ag-capture__instruction">${esc(t("capture.instruction"))}</h1>
        <div id="ag-alerts">${alertsCard()}</div>
      </div>

      <div class="ag-capture__preview">
        <video id="ag-video" playsinline muted autoplay hidden></video>
        <img id="ag-still" src="${photos.capturePreview}" alt="" />
        <div class="ag-capture__guide"></div>
        <p class="ag-capture__live" id="ag-live" role="status" aria-live="polite" hidden></p>
        <p class="ag-capture__hint" id="ag-hint" hidden></p>
      </div>

      <div class="ag-capture__controls">
        <button
          type="button"
          class="ag-capture__shutter"
          id="ag-shutter"
          aria-label="${esc(t("capture.button"))}"
        >
          <img src="${icons.camera}" alt="" width="40" height="40" />
        </button>

        <button type="button" class="ag-capture__upload" id="ag-upload">
          <img src="${icons.image}" alt="" />
          <span>${esc(t("capture.upload"))}</span>
        </button>
      </div>

      <input type="file" id="ag-file" accept="image/*" hidden />
      <input type="file" id="ag-file-camera" accept="image/*" capture="environment" hidden />
    </section>
  `;
}

export function mount(root) {
  const video = root.querySelector("#ag-video");
  const still = root.querySelector("#ag-still");
  const hint = root.querySelector("#ag-hint");
  const shutter = root.querySelector("#ag-shutter");
  const fileInput = root.querySelector("#ag-file");
  const cameraInput = root.querySelector("#ag-file-camera");

  let stream = null;
  let liveCamera = false;

  const live = root.querySelector("#ag-live");
  let liveTimer = null;
  let liveStopped = false;

  function scheduleLiveScan(delay) {
    clearTimeout(liveTimer);
    if (!liveStopped) liveTimer = setTimeout(liveScan, delay);
  }

  async function liveScan() {
    if (liveStopped || !liveCamera) return;
    if (document.hidden || !video.videoWidth) {
      scheduleLiveScan(LIVE_MIN_GAP_MS);
      return;
    }

    const startedAt = performance.now();
    try {
      // createImageBitmap takes the video element directly: the whole frame,
      // stretched to the model size, as the shutter photo will be.
      const prediction = await diagnose(video);
      if (liveStopped) return;
      live.hidden = false;
      live.dataset.status = prediction.status;
      live.textContent =
        prediction.status === "consult"
          ? t("capture.liveSearching")
          : t("capture.liveGuess", {
              name: displayName(prediction.class_id),
              percent: confidencePercent(prediction.confidence),
            });
    } catch {
      live.hidden = true; // model not ready or frame unreadable; try again shortly
    }
    const took = performance.now() - startedAt;
    scheduleLiveScan(Math.max(LIVE_MIN_GAP_MS, took * LIVE_GAP_FACTOR));
  }

  function stopLiveScan() {
    liveStopped = true;
    clearTimeout(liveTimer);
    live.hidden = true;
  }

  function showHint(message) {
    hint.textContent = message;
    hint.hidden = !message;
  }

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      showHint(t("capture.noCamera"));
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });

      video.srcObject = stream;
      video.hidden = false;
      still.hidden = true;
      liveCamera = true;
      showHint("");
      scheduleLiveScan(LIVE_MIN_GAP_MS);
    } catch {
      // Permission denied, no camera, or an insecure origin. The still stays
      // on screen and the shutter opens the phone's own camera app instead.
      showHint(t("capture.noCamera"));
    }
  }

  function stopCamera() {
    stopLiveScan();
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
  }

  function useImage(blob) {
    if (!blob) return;
    stopCamera();
    setSessionImage(blob);
    go("/processing");
  }

  function grabFrame() {
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) return;

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").drawImage(video, 0, 0, width, height);
    canvas.toBlob((blob) => useImage(blob), "image/jpeg", 0.92);
  }

  const onShutter = () => {
    if (liveCamera) grabFrame();
    else cameraInput.click();
  };

  const onUpload = () => fileInput.click();
  const onFile = (event) => useImage(event.target.files?.[0]);

  const onNav = (event) => {
    const target = event.currentTarget.dataset.nav;
    stopCamera();
    go(target === "history" ? "/history" : "/settings");
  };

  shutter.addEventListener("click", onShutter);
  root.querySelector("#ag-upload").addEventListener("click", onUpload);
  fileInput.addEventListener("change", onFile);
  cameraInput.addEventListener("change", onFile);
  root.querySelectorAll("[data-nav]").forEach((button) => {
    button.addEventListener("click", onNav);
  });

  startCamera();
  setDarkStatusBar(true); // the capture screen is deep green

  // Load and warm up the model while the farmer frames the leaf. A failure
  // here is retried when the photo is taken, so it is not reported now.
  loadModel().catch(() => {});

  // ---- nearby outbreak alerts -------------------------------------------
  const alertsBox = root.querySelector("#ag-alerts");
  let mounted = true;

  function drawAlerts() {
    if (!mounted) return;
    alertsBox.innerHTML = alertsCard();
  }

  alertsBox.addEventListener("click", async (event) => {
    if (event.target.closest("#ag-alerts-enable")) {
      state.locationConsent = true; // the farmer's explicit choice
      drawAlerts();
      await refreshAlerts(); // the OS asks for location permission here
      drawAlerts();
      return;
    }
    if (event.target.closest("#ag-alerts-listen")) {
      speak(alertsSpeech(cachedAlerts()));
      return;
    }
    const item = event.target.closest("[data-alert]");
    if (item) {
      stopCamera();
      go("/advice", { classId: item.dataset.alert });
    }
  });

  // Refreshing is app-wide (startAlertSync in main.js); this card just redraws.
  const onConnectivity = () => drawAlerts();
  window.addEventListener("online", onConnectivity);
  window.addEventListener("offline", onConnectivity);
  window.addEventListener(ALERTS_UPDATED, onConnectivity);

  return () => {
    mounted = false;
    window.removeEventListener("online", onConnectivity);
    window.removeEventListener("offline", onConnectivity);
    window.removeEventListener(ALERTS_UPDATED, onConnectivity);
    stopSpeaking();
    stopCamera();
    setDarkStatusBar(false);
  };
}
