# 0018. Finish the five crops before adding more; common beans are next

- **Status:** Proposed (confirm with the ZARI agronomist at the M1 sign-off, then mark Accepted)
- **Date:** 2026-10-27
- **Deciders:** Elisha Lungu, Agness, Robert Ng'onga Chishangila

## Context

AgriGuard covers maize, groundnut, cassava, soybean and cotton (19 classes in `ml/labels.json`). We asked which
crops to add next, using official figures rather than impressions. The evidence is in
[crop-priorities.md](../crop-priorities.md).

At the same time, the first five are not finished: the baseline model is trained on public data only, field photos
have not been collected, and M1 (agronomist sign-off of the class list) is overdue. Each new crop needs at least
300 expert-reviewed photos per class (see [class-taxonomy.md](../class-taxonomy.md)), agronomist review and advice
text in every language.

## Decision

1. **No new crop in model version 1.** Version 1 is the five current crops, proven on Zambian field photos.
2. **Common beans are the first crop of version 2.** In 2023/24, 117,737 smallholder households grew mixed beans in
   at least 7 provinces (IAS 2024, Table 3.5). A Zambian survey found angular leaf spot in every field it visited,
   and the main bean diseases show on leaves.
3. **Collect bean leaf photos on the version 1 field trips** where beans grow alongside our crops, with the same
   routine and metadata ([field-data.md](../ml/field-data.md)). This costs little and does not commit us to a schedule.
4. **Sunflower or tomato comes after beans**, decided with ZARI. Sunflower is grown by more households (216,604) but
   has weak Zambian disease evidence; tomato has the strongest loss evidence (Tuta absoluta) but no household count.

## Alternatives considered

- **Add beans now, alongside the five.** More classes to photograph, label and review before M1 is even signed
  off; risks finishing nothing well.
- **Rank by production volume.** Favours crops grown by large farms (wheat, soybean) over crops many smallholders
  depend on. We weighted the number of smallholder households highest.
- **Sunflower first** (most households after our five crops). Not chosen until an agronomist confirms which sunflower
  diseases matter in Zambia.

## Consequences

- The class list stays at 19 for version 1; `labels.json` is unchanged. Bean classes will be appended later, never
  reordered (see the taxonomy rules).
- The field team photographs beans on trips where beans grow, and the photo batches carry `crop = beans` once the
  checker accepts it. Until then, keep bean photos in a separate batch folder.
- The ranking rests on a drought year (2023/24) and on assumed scores for vegetables. Revisit it with the 2024/25
  Crop Forecast Survey microdata from ZamStats NADA, and with FAOSTAT for crops the survey does not cover.
