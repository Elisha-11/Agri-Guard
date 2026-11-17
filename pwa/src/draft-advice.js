/**
 * DRAFT treatment advice for the classes model 2026.11.0 predicts, so the
 * result screen has something to show while no reviewed advice is published.
 *
 * NOT REVIEWED BY AN AGRONOMIST. This bends ADR 0008 (advice comes only from
 * the published advisory bundle) for a test/demo build, at the user's request
 * on 2026-11-17. Every screen that shows it labels it as a draft.
 *
 * - Published advice from the bundle always wins (advisory.js adviceFor()).
 * - Before farmers use the app: have the agronomist review this text, enter it
 *   in the admin so it is published with `reviewed_by`, and delete this file.
 * - No product names or doses on purpose: chemical advice must name approved
 *   products and carry a safety warning, which only the agronomist can sign.
 */

const draft = (entry) => ({
  lang: "en",
  local_name: null,
  reviewed_by: null,
  reviewed_at: null,
  draft: true,
  ...entry,
});

export const DRAFT_ADVICE = [
  draft({
    class_id: "maize__healthy",
    name: "Healthy maize",
    symptoms: ["No signs of disease were found on this leaf."],
    treatment: {
      title: "No treatment needed",
      steps: [
        "No treatment is needed for this plant.",
        "Do not spray chemicals on healthy plants.",
      ],
      audio_url: null,
    },
    prevention: {
      title: "Keep the crop healthy",
      steps: [
        "Keep the field free of weeds, especially grasses.",
        "Use certified seed of a recommended variety next season.",
        "Rotate maize with legumes such as beans or groundnuts.",
      ],
      audio_url: null,
    },
    follow_up: {
      title: "Check again",
      steps: [
        "Check your plants once a week, looking at both sides of the leaves.",
        "Take a new photo if you see spots, streaks or yellowing.",
      ],
      audio_url: null,
    },
    safety_warning: null,
  }),
  draft({
    class_id: "maize__lethal_necrosis",
    name: "Maize Lethal Necrosis (MLN)",
    symptoms: [
      "Yellow streaks and mottling on the leaves that dry from the edges inwards.",
      "Plants can die early, and cobs stay small or empty.",
    ],
    treatment: {
      title: "What to do now",
      steps: [
        "There is no cure: MLN is caused by viruses. Infected plants will not recover.",
        "Pull out plants with symptoms and bury or burn them away from the field.",
        "Report it to your extension officer quickly: MLN spreads fast between farms.",
        "Ask your extension officer how to control the insects that spread it (thrips, aphids and beetles).",
      ],
      audio_url: null,
    },
    prevention: {
      title: "Stop it coming back",
      steps: [
        "Do not plant maize in this field next season. Grow beans, groundnuts or cassava instead.",
        "Use certified seed, and an MLN-tolerant variety where available.",
        "Do not save seed from this field.",
        "Keep the field and its edges free of grass weeds.",
      ],
      audio_url: null,
    },
    follow_up: {
      title: "Check again",
      steps: [
        "Check the rest of the field every few days for new plants with symptoms.",
        "Tell neighbouring farmers so they can check their fields too.",
      ],
      audio_url: null,
    },
    safety_warning:
      "Only use insecticides your extension officer approves. Follow the label, wear gloves and a mask, and keep children and animals away.",
  }),
  draft({
    class_id: "maize__streak_virus",
    name: "Maize Streak Virus",
    symptoms: [
      "Thin yellow or white streaks along the leaf veins.",
      "Young plants infected early stay short and give poor cobs.",
    ],
    treatment: {
      title: "What to do now",
      steps: [
        "There is no cure: streak is caused by a virus spread by leafhoppers.",
        "Pull out young plants with many streaks early, and bury them away from the field.",
        "Older plants with only a few streaks can be left; they usually still yield.",
      ],
      audio_url: null,
    },
    prevention: {
      title: "Stop it coming back",
      steps: [
        "Plant a streak-resistant variety next season.",
        "Plant early, at the start of the rains, and at the same time as your neighbours.",
        "Do not plant new maize next to older maize.",
        "Keep grass weeds down in and around the field: leafhoppers live on them.",
      ],
      audio_url: null,
    },
    follow_up: {
      title: "Check again",
      steps: [
        "Check young plants every week for new streaks.",
        "If many young plants are affected, ask your extension officer about controlling leafhoppers.",
      ],
      audio_url: null,
    },
    safety_warning:
      "Only use insecticides your extension officer approves. Follow the label, wear gloves and a mask, and keep children and animals away.",
  }),
];

export function draftAdviceFor(classId) {
  return DRAFT_ADVICE.find((entry) => entry.class_id === classId) ?? null;
}
