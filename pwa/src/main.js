import "bootstrap/dist/css/bootstrap.min.css";
import "./styles.css";

const app = document.querySelector("#app");

app.innerHTML = `
  <nav class="navbar" style="background: var(--ag-green)">
    <div class="container">
      <span class="navbar-brand text-white fw-semibold">AgriGuard AI</span>
      <span id="net" class="badge"></span>
    </div>
  </nav>
  <main class="container py-4 d-grid gap-3">
    <p class="lead mb-0">Photograph a leaf to check for disease.</p>
    <button class="btn btn-success btn-capture" disabled>Take photo (coming in Step 9)</button>
    <p class="small text-body-secondary mb-0">API: <span id="api">checking…</span></p>
  </main>
`;

function renderNetwork() {
  const net = document.querySelector("#net");
  net.textContent = navigator.onLine ? "Online" : "Offline";
  net.className = `badge ${navigator.onLine ? "text-bg-light" : "text-bg-warning"}`;
}
window.addEventListener("online", renderNetwork);
window.addEventListener("offline", renderNetwork);
renderNetwork();

// Hello-world check against the backend (Step 1 exit condition).
fetch("/api/v1/health/")
  .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
  .then((h) => (document.querySelector("#api").textContent = `${h.status} (v${h.version})`))
  .catch(() => (document.querySelector("#api").textContent = "not reachable"));
