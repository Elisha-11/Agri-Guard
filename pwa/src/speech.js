/**
 * Voice narration for the "Listen" button on the result and advice screens.
 *
 * Uses the Web Speech API, which needs no network and no extra dependency.
 * Zambian language voices (Bemba, Nyanja, Tonga) are not shipped by any
 * current browser, so when the chosen language has no matching voice the
 * browser falls back to its default — the text is still read aloud. A real
 * recorded-audio path can replace this module without touching the screens.
 */

import { speechTag } from "./i18n.js";
import { state } from "./state.js";

export function speechSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

function pickVoice(tag) {
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  const base = tag.split("-")[0];
  return (
    voices.find((voice) => voice.lang.toLowerCase() === tag.toLowerCase()) ??
    voices.find((voice) => voice.lang.toLowerCase().startsWith(`${base}-`)) ??
    null
  );
}

/**
 * Read `lines` aloud, stopping anything already playing.
 * Returns false when narration is off or unsupported.
 */
export function speak(lines) {
  if (!speechSupported() || !state.voiceNarration) return false;

  const text = (Array.isArray(lines) ? lines : [lines]).filter(Boolean).join(". ");
  if (!text) return false;

  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  const tag = speechTag();
  const voice = pickVoice(tag);

  if (voice) utterance.voice = voice;
  utterance.lang = tag;
  // Farmers using this may be hearing the name of a disease for the first
  // time; a slightly slower rate measurably helps comprehension.
  utterance.rate = 0.95;

  window.speechSynthesis.speak(utterance);
  return true;
}

export function stopSpeaking() {
  if (speechSupported()) window.speechSynthesis.cancel();
}
