import "bootstrap/dist/css/bootstrap.min.css";
import "./styles.css";
import { diagnose } from "./inference/diagnose.js";

const app = document.querySelector("#app");

app.innerHTML = `
  <nav class="navbar" style="background: var(--ag-green)">
    <div class="container">
      <span class="navbar-brand text-white fw-semibold">
        AgriGuard AI
      </span>
      <span id="net" class="badge"></span>
    </div>
  </nav>

  <main class="container py-4 d-grid gap-3">
    <h4>Crop Disease Detection</h4>

    <p class="lead">
      Select a leaf photograph to receive a demonstration prediction.
    </p>

    <input
      id="leaf-image"
      type="file"
      accept="image/*"
      class="form-control"
    />

    <button
      id="diagnose-btn"
      class="btn btn-success"
      disabled
    >
      Analyse Image
    </button>

    <div id="result" class="alert alert-light">
      Select an image to begin.
    </div>

    <p class="small text-body-secondary">
      API: <span id="api">checking…</span>
    </p>

    <p class="small text-warning">
      Demonstration mode: predictions are simulated, not real diagnoses.
    </p>
  </main>
`;

const imageInput = document.querySelector("#leaf-image");
const diagnoseButton = document.querySelector("#diagnose-btn");
const result = document.querySelector("#result");

imageInput.addEventListener("change", () => {
  diagnoseButton.disabled = !imageInput.files.length;
  result.textContent = imageInput.files.length
    ? "Image selected. Click Analyse Image."
    : "Select an image to begin.";
});

diagnoseButton.addEventListener("click", async () => {
  const image = imageInput.files[0];

  if (!image) return;

  diagnoseButton.disabled = true;
  result.textContent = "Processing image...";

  try {
    const prediction = await diagnose(image);

    result.innerHTML = `
      <h5>Demonstration Prediction</h5>
      <p><strong>Class:</strong> ${prediction.class_id}</p>
      <p><strong>Confidence:</strong> ${prediction.confidence}</p>
      <p><strong>Status:</strong> ${prediction.status}</p>
      <p><strong>Severity:</strong> ${prediction.severity}</p>
      <p><strong>Model version:</strong> ${prediction.model_version}</p>
    `;
  } catch (error) {
    result.textContent = `Error: ${error.message}`;
  } finally {
    diagnoseButton.disabled = false;
  }
});

function renderNetwork() {
  const net = document.querySelector("#net");

  net.textContent = navigator.onLine ? "Online" : "Offline";
  net.className = `badge ${
    navigator.onLine ? "text-bg-light" : "text-bg-warning"
  }`;
}

window.addEventListener("online", renderNetwork);
window.addEventListener("offline", renderNetwork);
renderNetwork();

fetch("/api/v1/health/")
  .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
  .then((h) => {
    document.querySelector("#api").textContent =
      `${h.status} (v${h.version})`;
  })
  .catch(() => {
    document.querySelector("#api").textContent = "not reachable";
  });