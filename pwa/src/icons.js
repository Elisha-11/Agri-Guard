/**
 * Icon and photo assets exported from the AgriGuard Screens Figma file.
 *
 * Vite resolves each import to a served URL, so the SVGs stay separate files
 * with their own intrinsic width/height instead of being inlined into markup.
 * Several icons appear at two sizes in the design (24px on one screen, 28px on
 * another); both are kept because the stroke weight differs between them.
 */

import arrowLeft from "./screens/assets/icons/arrow-left.svg";
import arrowLeft20 from "./screens/assets/icons/arrow-left-20.svg";
import arrowLeftHistory from "./screens/assets/icons/arrow-left-history.svg";
import arrowLeftRejected from "./screens/assets/icons/arrow-left-rejected.svg";
import arrowLeftSettings from "./screens/assets/icons/arrow-left-settings.svg";
import calendar from "./screens/assets/icons/calendar.svg";
import calendar28 from "./screens/assets/icons/calendar-28.svg";
import camera from "./screens/assets/icons/camera.svg";
import camera64 from "./screens/assets/icons/camera-64.svg";
import check from "./screens/assets/icons/check.svg";
import chevronRight from "./screens/assets/icons/chevron-right.svg";
import chevronRight20 from "./screens/assets/icons/chevron-right-20.svg";
import chevronUp from "./screens/assets/icons/chevron-up.svg";
import droplet from "./screens/assets/icons/droplet.svg";
import droplet28 from "./screens/assets/icons/droplet-28.svg";
import globe from "./screens/assets/icons/globe.svg";
import image from "./screens/assets/icons/image.svg";
import image20 from "./screens/assets/icons/image-20.svg";
import leaf from "./screens/assets/icons/leaf.svg";
import leafPlaceholder from "./screens/assets/icons/leaf-placeholder.svg";
import logout from "./screens/assets/icons/logout.svg";
import maximize from "./screens/assets/icons/maximize.svg";
import moon from "./screens/assets/icons/moon.svg";
import phone from "./screens/assets/icons/phone.svg";
import radioSelected from "./screens/assets/icons/radio-selected.svg";
import radioUnselected from "./screens/assets/icons/radio-unselected.svg";
import severityHigh from "./screens/assets/icons/severity-high.svg";
import severityModerate from "./screens/assets/icons/severity-moderate.svg";
import severityNone from "./screens/assets/icons/severity-none.svg";
import shield from "./screens/assets/icons/shield.svg";
import shield28 from "./screens/assets/icons/shield-28.svg";
import speaker from "./screens/assets/icons/speaker.svg";
import speakerAdvice from "./screens/assets/icons/speaker-advice.svg";
import voice from "./screens/assets/icons/voice.svg";
import warning from "./screens/assets/icons/warning.svg";

import capturePreview from "./screens/assets/capture-preview.png";
import resultPhoto from "./screens/assets/result-photo.png";
import uncertainPhoto from "./screens/assets/uncertain-photo.png";

export const icons = {
  arrowLeft,
  arrowLeft20,
  arrowLeftHistory,
  arrowLeftRejected,
  arrowLeftSettings,
  calendar,
  calendar28,
  camera,
  camera64,
  check,
  chevronRight,
  chevronRight20,
  chevronUp,
  droplet,
  droplet28,
  globe,
  image,
  image20,
  leaf,
  leafPlaceholder,
  logout,
  maximize,
  moon,
  phone,
  radioSelected,
  radioUnselected,
  severityHigh,
  severityModerate,
  severityNone,
  shield,
  shield28,
  speaker,
  speakerAdvice,
  voice,
  warning,
};

export const photos = {
  capturePreview,
  resultPhoto,
  uncertainPhoto,
};

/** Severity dot used on the history cards. */
export function severityDot(severity) {
  if (severity === "severe" || severity === "high") return icons.severityHigh;
  if (severity === "none") return icons.severityNone;
  return icons.severityModerate;
}
