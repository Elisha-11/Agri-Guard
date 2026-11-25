/**
 * Network calls for the agrovet feature, behind ONE switch.
 *
 * MOCK MODE. The endpoints used here come from the agrovet request spec
 * (v2) that the backend is implementing as API contract 0.6.0. That contract
 * is NOT in docs/api-contract.yaml yet (the repo is at 0.5.0), so while
 * `AGROVET_MOCK` is on, every call is answered by the in-memory fake server
 * in src/agrovet-mock.js instead of the network. The fake uses only the
 * spec's field names.
 *
 *   npm run dev                          mock on (VITE_AGROVET_MOCK=false turns it off)
 *   vite build                           mock OFF: a release never has fake shops
 *   vite build --mode demo               mock on, for demo builds only
 *
 * Every agrovet screen shows a "Demo data" banner while the mock is on. The
 * fake server is loaded only through a dynamic import behind the switch, so a
 * release build leaves it, its fake shops and their dummy numbers out
 * entirely.
 *
 * Remove the mock once contract 0.6.0 is merged and staging serves it.
 */

import { apiUrl } from "./native.js";

// A build decides on PROD and MODE only: the bundler replaces both with
// literals, so in a release this folds to `false` and the mock module is never
// emitted. (An unset VITE_ variable is not a literal at that stage, which is
// why it is only read in development.)
export const AGROVET_MOCK = import.meta.env.PROD
  ? import.meta.env.MODE === "demo"
  : import.meta.env.VITE_AGROVET_MOCK !== "false";

/** Longest message a farmer can send (1,000 characters, confirmed by the project lead). */
export const MESSAGE_MAX_LENGTH = 1000;

/** The farmer's district in mock mode. The real app will read it from GET /me/. */
export const MOCK_DISTRICT = AGROVET_MOCK ? "Example District" : null;

/** `fetch` for agrovet endpoints: the fake server in mock mode, the network otherwise. */
export async function agrovetFetch(path, init = {}) {
  if (AGROVET_MOCK) {
    const { mockServer } = await import("./agrovet-mock.js");
    return mockServer.handle(path, init);
  }
  return fetch(apiUrl(path), init);
}
