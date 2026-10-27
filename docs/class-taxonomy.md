# Disease Class Taxonomy (DRAFT v0.1)

> **Status: DRAFT, not signed off.** Build Step 2 requires an agronomist (ZARI / extension officer) to confirm this
> list before labelling starts in Week 3. Until then, treat class ids as provisional. Renaming is cheap now and
> expensive after Label Studio import.

## Rules

- Class id format: `<crop>__<condition>` in lowercase snake_case, e.g. `maize__grey_leaf_spot`.
- Every crop has a `__healthy` class. The model must be able to say "this leaf looks fine".
- The integer index used by the model is the row order in `ml/labels.json` (generated from this file). **Never reorder.**
  Retired classes stay listed with `retired: true` so old indices keep their meaning.
- A class is only trainable once it has **≥ 300 expert-reviewed images** after the train/val/test split
  (plan target: 6,000+ raw images over ~18 classes).

## Proposed classes

Source column: **P** = named in the AgriGuard proposal / concept note; **D** = proposed by the dev team as a common
disease of that crop in Zambia. Every **D** row needs agronomist confirmation.

| # | Class id | Crop | Condition | Pathogen type | Source | Notes for agronomist |
|---|----------|------|-----------|---------------|--------|----------------------|
| 0 | `maize__healthy` | Maize | Healthy | n/a | P | |
| 1 | `maize__northern_leaf_blight` | Maize | Northern Leaf Blight | Fungal | P | |
| 2 | `maize__grey_leaf_spot` | Maize | Grey Leaf Spot | Fungal | P | |
| 3 | `maize__common_rust` | Maize | Common Rust | Fungal | D | Large open datasets exist |
| 4 | `maize__lethal_necrosis` | Maize | Maize Lethal Necrosis (MLN) | Viral complex | P | Confirm field prevalence in ZM; images may be scarce |
| 5 | `maize__streak_virus` | Maize | Maize Streak Virus | Viral | D | |
| 6 | `groundnut__healthy` | Groundnut | Healthy | n/a | P | |
| 7 | `groundnut__rosette` | Groundnut | Groundnut Rosette Disease | Viral | P | |
| 8 | `groundnut__early_leaf_spot` | Groundnut | Early Leaf Spot | Fungal | D | Visually close to late leaf spot: merge? |
| 9 | `groundnut__late_leaf_spot` | Groundnut | Late Leaf Spot | Fungal | D | See above |
| 10 | `cassava__healthy` | Cassava | Healthy | n/a | P | |
| 11 | `cassava__mosaic_disease` | Cassava | Cassava Mosaic Disease | Viral | P | |
| 12 | `cassava__brown_streak` | Cassava | Cassava Brown Streak Disease | Viral | D | |
| 13 | `soybean__healthy` | Soybean | Healthy | n/a | P | |
| 14 | `soybean__rust` | Soybean | Soybean Rust | Fungal | D | Confirm vs. frogeye as #2 priority |
| 15 | `soybean__frogeye_leaf_spot` | Soybean | Frogeye Leaf Spot | Fungal | D | |
| 16 | `cotton__healthy` | Cotton | Healthy | n/a | P | |
| 17 | `cotton__bacterial_blight` | Cotton | Bacterial Blight | Bacterial | D | |
| 18 | `cotton__alternaria_leaf_spot` | Cotton | Alternaria Leaf Spot | Fungal | D | |

**Total: 19 classes** (5 healthy + 14 disease).

## Questions for the agronomist (Week 2)

1. Which **D** rows are common enough in Zambia to justify a class in the MVP? Which are missing?
2. Should early and late leaf spot on groundnut be one class for farmers (same treatment)?
3. MLN: is it present enough in our collection zones to photograph ≥ 300 examples by 28 October?
4. Are pests with leaf symptoms (e.g. Fall Armyworm damage) in scope, or disease only?
5. For each class, what are the **severity stages** (early / mid / advanced) and how are they recognised on a leaf?
   This feeds the severity band in [`model-output.md`](model-output.md).
6. After the five crops, we plan to add **common beans**, then sunflower or tomato ([ADR 0018](decisions/0018-finish-five-crops-then-add-beans.md),
   evidence in [crop-priorities.md](crop-priorities.md)). Do you agree? Which bean, sunflower and tomato diseases
   matter most in Zambia?
7. Does ZARI hold labelled leaf photos we could use, especially groundnut rosette, beans or tomato?

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Agronomist | | | |
| ML & model delivery | Agness | | |
| API & infrastructure | Elisha Lungu | | |
| PWA & field UX | Robert Ng'onga Chishangila | | |
