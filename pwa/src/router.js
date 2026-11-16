/**
 * Hash router for the screen flow.
 *
 * Each screen module exports `render(params) -> html` and, optionally,
 * `mount(root, params) -> cleanup`. Hash routing keeps the PWA working from
 * `file://`, from a static host and inside an installed app shell without any
 * server-side rewrite rules.
 */

let routes = {};
let outlet = null;
let guard = null;
let cleanup = null;

// Params are handed over in memory rather than encoded in the URL: one of
// them is an object URL for a photo, which has no meaning on a reload.
let pendingParams = {};

export function defineRoutes(map) {
  routes = map;
}

/** `guardFn(path)` returns a replacement path, or null to allow the route. */
export function setGuard(guardFn) {
  guard = guardFn;
}

export function currentPath() {
  return window.location.hash.replace(/^#/, "") || "/";
}

export function go(path, params = {}) {
  pendingParams = params;
  if (currentPath() === path) {
    render();
  } else {
    window.location.hash = path;
  }
}

/** Replace the current entry instead of pushing a new one. */
export function replace(path, params = {}) {
  pendingParams = params;
  const url = `${window.location.pathname}${window.location.search}#${path}`;
  window.history.replaceState(null, "", url);
  render();
}

export function back(fallback = "/capture") {
  if (window.history.length > 1) {
    window.history.back();
  } else {
    go(fallback);
  }
}

function render() {
  const path = currentPath();
  const redirect = guard ? guard(path) : null;

  if (redirect && redirect !== path) {
    replace(redirect);
    return;
  }

  const screen = routes[path] ?? routes["*"];
  if (!screen) return;

  const params = pendingParams;
  pendingParams = {};

  if (cleanup) {
    cleanup();
    cleanup = null;
  }

  outlet.innerHTML = screen.render(params);
  window.scrollTo(0, 0);

  if (typeof screen.mount === "function") {
    cleanup = screen.mount(outlet, params) ?? null;
  }
}

export function start(element) {
  outlet = element;
  window.addEventListener("hashchange", render);
  render();
}
