# 0002. Start with 0.70 / 0.40 confidence cut-offs, read from the model manifest

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-13
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

A wrong diagnosis can lead a farmer to spray the wrong chemical or miss a disease that spreads. The model will be
wrong sometimes, so the app needs to say when it isn't sure. There's no trained model yet to calibrate against.

## Decision

- Confidence ≥ 0.70 → `confident`: show the disease and full advice.
- 0.40 – 0.70 → `uncertain`: ask for another photo and show the top two candidates.
- Below 0.40 → `consult`: send the farmer to an extension officer, with no treatment advice.
- The PWA reads the cut-offs from `manifest.json` (`thresholds.confident`, `thresholds.uncertain`) and never
  hard-codes them, so a new model can ship new thresholds without an app release.

Details are in [model-output.md §4](../model-output.md).

## Alternatives considered

- **Always show the top answer:** simplest, but it presents low-confidence guesses as facts.
- **A single cut-off:** loses the "take a better photo" middle ground, which fixes many bad results cheaply.

## Consequences

- In Step 6, the ML owner (Agness) sets the final values from the calibration curve on the validation set and updates
  model-output.md in a contract PR, superseding this ADR's numbers.
