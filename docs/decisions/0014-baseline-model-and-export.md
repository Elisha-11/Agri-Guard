# 0014. Baseline model: EfficientNetB0, augmentation outside the graph, float16 TF.js export

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-21
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

Build Step 5 needs a first model that goes the whole way: images → training → TF.js → `register_model` → the PWA.
Accuracy doesn't matter yet; the pipeline does. The limits come from model-output.md and the backend: input
`[1, 224, 224, 3]` float32 in 0–255 with preprocessing inside the graph; softmax output in labels.json order;
shards of at most 4 MB; at most 15 MB in total; it must load in under 5 s on a 1 GB RAM phone.

## Decisions

1. **EfficientNetB0 from ImageNet, plus pooling, dropout and a softmax `Dense`.** Keras's EfficientNet contains its
   own Rescaling and Normalization layers, so the model takes 0–255 pixels as labels.json says, and the PWA does
   no maths before inference. About 4.1M parameters.
2. **Weights are quantised to float16.**
   - float32 is about 16 MB, over the 15 MB limit.
   - float16 is about 8 MB, with accuracy loss normally well under a percentage point.
   - int8 (`uint8` weight quantisation) is about 4 MB and would load faster, but EfficientNet's depthwise layers
     are known to lose noticeable accuracy with it.
   - Revisit int8 if the 5 s load target on a 1 GB phone is missed.
3. **Augmentation lives in the `tf.data` pipeline, never in the model.** The exported graph is only backbone +
   head. Keras random layers are no-ops at inference, but their ops (e.g. `ImageProjectiveTransformV3`) can
   still end up in a saved graph, and TF.js may not run them. `export_tfjs.py` fails if any augmentation op
   appears, and checks every op against a list of ops TF.js runs.
4. **Two training stages, with BatchNormalization frozen throughout.** Stage 1 trains the head with the backbone
   frozen (lr 1e-3). Stage 2 unfreezes block6, block7 and the top convolution at lr 1e-5, with early stopping. All
   BatchNormalization layers stay `trainable=False` and run in inference mode, so small, uneven batches of farm
   photos can't distort the ImageNet statistics.
5. **The output layer always has every labels.json class, in index order,** even classes with no images yet.
   They stay untrained (and the reports say "no data"), but the PWA and backend can rely on `N = 19`.
6. **The split is by farmer or field whenever metadata allows (ADR 0013).** A stratified random split is used
   only for public datasets, which have no farm information, and the run prints a warning.
7. **Baseline runs use a real calendar version (`2026.10.0`)**, so `register_model` accepts them unchanged. That
   it's a baseline goes in the release notes, and it is never made current.

## Alternatives considered

- **MobileNetV3:** smaller and faster, but EfficientNetB0 is the plan's model and fits the budget with float16.
  It's worth comparing in Step 6 if load time is a problem.
- **Preprocessing in JavaScript:** another place to get the maths wrong, and every model change would need a PWA
  release.
- **Keras preprocessing layers for augmentation, removed before export:** works, but it's easy to forget, and it
  depends on Keras internals. `tf.data` keeps training-only code out of the model entirely.

## Consequences

- The export is about 8 MB, leaving room under 15 MB but not for a much larger backbone.
- Temperature scaling (model-output.md §3) isn't in the baseline; it's added in Step 6.
- Public-dataset results (e.g. PlantVillage, lab photos) will look much better than field results. Only the
  farmer split says anything about real use.
