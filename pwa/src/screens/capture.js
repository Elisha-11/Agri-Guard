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
 */

import { icons, photos } from "../icons.js";
import { t } from "../i18n.js";
import { esc } from "../ui.js";
import { go } from "../router.js";
import { setSessionImage } from "../state.js";
import { setDarkStatusBar } from "../native.js";

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
      </div>

      <div class="ag-capture__preview">
        <video id="ag-video" playsinline muted autoplay hidden></video>
        <img id="ag-still" src="${photos.capturePreview}" alt="" />
        <div class="ag-capture__guide"></div>
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
    } catch {
      // Permission denied, no camera, or an insecure origin. The still stays
      // on screen and the shutter opens the phone's own camera app instead.
      showHint(t("capture.noCamera"));
    }
  }

  function stopCamera() {
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

  return () => {
    stopCamera();
    setDarkStatusBar(false);
  };
}
